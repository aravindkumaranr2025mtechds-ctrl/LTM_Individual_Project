"""Evaluate the frozen v2 development pilot through the local FastAPI server."""

import hashlib
import http.client
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_HASH = "147f9c3b045113dfbbb1f5f43cd253634331c95c0957c27835f0b9a2f8c0d749"
API_PATH = "/documents/search"
METRICS = ["known_positive_hit_at_1", "known_positive_hit_at_3",
           "known_positive_hit_at_5", "known_positive_mrr_at_5"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def input_file(root, folder, name, suffix):
    require(isinstance(name, str) and bool(name)
            and not any(c in name for c in "/\\:\x00")
            and Path(name).suffix.lower() == suffix, "Invalid input filename.")
    directory = (root / "data" / folder).resolve()
    path = (directory / name).resolve()
    require(path.parent == directory, "Input file escapes its data folder.")
    return path


def load_cases(path):
    config = json.loads(path.read_bytes().decode("utf-8-sig"))
    require(canonical_hash(config) == CASES_HASH,
            "Evaluation cases differ from the verified pilot. Review the file.")
    return config


def preflight(root, config):
    source = config["source"]
    prepared_path = input_file(root, "embedding_documents",
                               source["prepared_filename"], ".json")
    store_path = input_file(root, "vector_store",
                            source["vector_store_filename"], ".npz")
    raw = prepared_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == source["prepared_sha256"],
            "Prepared file fingerprint mismatch.")
    prepared = json.loads(raw.decode("utf-8-sig"))
    require(canonical_hash(prepared) == source["canonical_content_sha256"],
            "Prepared JSON content mismatch.")
    require(prepared["document_id"] == source["document_id"]
            and prepared["strategy"] == source["chunking_strategy"],
            "Wrong prepared document or chunking strategy.")
    parents = {p["parent_id"]: p for p in prepared["parents"]}
    chunks = {c["chunk_id"]: c for c in prepared["chunks"]}
    alarms = [str(p["alarm_number"]) for p in parents.values()
              if p["alarm_number"] is not None]
    require(len(parents) == len(prepared["parents"]) == source["expected_parent_records"]
            and len(chunks) == len(prepared["chunks"]) == source["expected_prepared_chunks"]
            and len(set(alarms)) == len(alarms) == source["expected_detected_alarm_numbers"],
            "Source counts or unique identifiers differ.")
    before = file_hash(store_path)
    with np.load(store_path, allow_pickle=False) as store:
        require(set(store.files) == {"embeddings", "chunk_ids", "metadata_utf8"},
                "Unexpected vector-store arrays.")
        vectors, ids, encoded = store["embeddings"], store["chunk_ids"], store["metadata_utf8"]
        require(encoded.dtype == np.uint8 and encoded.ndim == 1,
                "Invalid vector-store metadata encoding.")
        metadata = json.loads(encoded.tobytes().decode("utf-8"))
    require(vectors.dtype == np.float32 and vectors.shape == (len(chunks), 384)
            and np.isfinite(vectors).all()
            and np.allclose(np.linalg.norm(vectors, axis=1), 1.0, rtol=0, atol=1e-5),
            "Invalid vector shape, type, values or normalization.")
    require(ids.dtype.kind == "U" and ids.shape == (len(chunks),)
            and ids.tolist() == list(chunks), "Vector/chunk ID alignment failed.")
    info = metadata["embedding"]
    expected = {"schema_version": 1, "model_name": "BAAI/bge-small-en-v1.5",
                "embedding_dimension": 384, "dtype": "float32", "document_prompt": "",
                "model_token_limit": 512,
                "maximum_input_tokens": max(c["token_count"] for c in chunks.values()),
                "prepared_filename": source["prepared_filename"],
                "prepared_sha256": source["prepared_sha256"]}
    require(all(info.get(k) == v for k, v in expected.items())
            and info.get("normalized") is True, "Incompatible embedding metadata.")
    expected_metadata = {**prepared, "embedding": info, "chunks": [
        {**chunk, "vector_index": i} for i, chunk in enumerate(prepared["chunks"])]}
    require(metadata == expected_metadata, "Store text/metadata differs from prepared JSON.")
    require(file_hash(store_path) == before, "Vector store changed while being read.")
    return {"prepared": prepared, "parents": parents, "chunks": chunks,
            "embedding": info, "files": {prepared_path: source["prepared_sha256"],
                                         store_path: before}}


def make_request(config, case, exact=False):
    # Expected semantic answers are deliberately NOT sent to the API.
    return {"vector_store_filename": config["source"]["vector_store_filename"],
            "query": "" if exact else case["query"],
            "alarm_number": case["alarm_number"] if exact else None,
            "top_k": config["search"]["top_k"]}


def post_search(payload):
    connection = http.client.HTTPConnection("127.0.0.1", 8000, timeout=120)
    try:
        connection.request("POST", API_PATH,
                           body=json.dumps(payload).encode("utf-8"),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read(2_000_001)
        require(len(raw) <= 2_000_000, "API response exceeds the size limit.")
        require(response.status == 200,
                f"HTTP {response.status}: {raw[:500].decode('utf-8', errors='replace')}")
        return json.loads(raw.decode("utf-8"))
    finally:
        connection.close()


def validate_response(response, payload, context):
    require(isinstance(response, dict), "API response must be an object.")
    prepared, parents, chunks = context["prepared"], context["parents"], context["chunks"]
    exact = payload["alarm_number"] is not None
    require(response.get("document_id") == prepared["document_id"]
            and response.get("source_filename") == prepared["source_filename"]
            and response.get("query") == payload["query"]
            and response.get("alarm_number") == payload["alarm_number"],
            "API returned a different source or request.")
    require(response.get("mode") == ("exact_alarm" if exact else "semantic")
            and response.get("status") == ("found" if exact else "candidates"),
            "Unexpected retrieval mode/status.")
    results = response.get("results")
    require(isinstance(results, list) and len(results) <= payload["top_k"]
            and type(response.get("results_count")) is int
            and response["results_count"] == len(results), "Invalid result count.")
    if exact:
        require(len(results) == 1 and type(response.get("total_matching_sections")) is int
                and response["total_matching_sections"] == 1
                and response.get("has_more") is False, "Exact lookup must return one section.")
    else:
        require(type(response.get("query_tokens")) is int
                and 0 < response["query_tokens"] <= 512, "Invalid query token count.")
    seen = set()
    for rank, item in enumerate(results, 1):
        require(isinstance(item, dict), "Invalid result record.")
        pid = item.get("parent_id")
        require(isinstance(pid, str) and pid in parents and pid not in seen,
                "Unknown or duplicate parent section.")
        seen.add(pid)
        require(type(item.get("rank")) is int and item["rank"] == rank,
                "Result ranks are not sequential.")
        require(all(item.get(k) == parents[pid].get(k) for k in
                    ("document_id", "source_filename", "alarm_number", "alarm_title",
                     "page_numbers", "text")), "Returned section differs from the verified source.")
        score = item.get("cosine_similarity")
        if exact:
            require(item["alarm_number"] == payload["alarm_number"] and score is None
                    and item.get("matched_chunk_id") is None
                    and item.get("matched_chunk_text") is None
                    and item.get("matched_chunk_pages") == []
                    and item.get("matched_chunk_pages_scope") is None,
                    "Exact lookup contains unexpected matching data.")
        else:
            require(type(score) in (int, float) and math.isfinite(score) and -1 <= score <= 1,
                    "Invalid similarity score.")
            cid = item.get("matched_chunk_id")
            require(isinstance(cid, str) and cid in chunks, "Unknown matching chunk.")
            chunk = chunks[cid]
            require(chunk["parent_id"] == pid and item.get("matched_chunk_text") == chunk["text"]
                    and item.get("matched_chunk_pages") == chunk["page_numbers"]
                    and item.get("matched_chunk_pages_scope") == chunk["page_numbers_scope"],
                    "Matching passage differs from the verified chunk.")
    return results


def score_results(results, positives, document_id):
    first = next((i for i, item in enumerate(results[:5], 1)
                  if item["document_id"] == document_id
                  and str(item["alarm_number"]) in positives), None)
    return {"first_known_positive_rank": first,
            **{f"known_positive_hit_at_{k}": int(first is not None and first <= k)
               for k in (1, 3, 5)},
            "known_positive_rr_at_5": 0.0 if first is None else 1.0 / first}


def aggregate(records, expected_count):
    scored = [r for r in records if r["category"] == "specific_semantic_cases"]
    require(len(scored) == expected_count and expected_count > 0
            and all(r["status"] == "completed" for r in scored),
            "Cannot calculate metrics for an incomplete scored set.")
    metrics = {name: sum(r["score"][name] for r in scored) / expected_count
               for name in METRICS[:3]}
    metrics[METRICS[3]] = sum(r["score"]["known_positive_rr_at_5"] for r in scored) / expected_count
    return {"scored_questions": expected_count, **metrics}


def run_cases(config, context, records, search=post_search):
    groups = ("section_completeness_checks", "specific_semantic_cases", "ambiguous_review_cases")
    for group in groups:
        exact = group == "section_completeness_checks"
        for case in config[group]:
            payload = make_request(config, case, exact)
            record = {"id": case["id"], "category": group, "status": "started", "request": payload}
            records.append(record)
            start = time.perf_counter()
            try:
                record["response"] = search(payload)
                results = validate_response(record["response"], payload, context)
                if exact:
                    require(results[0]["page_numbers"] == case["expected_page_numbers"]
                            and all(t in results[0]["text"] for t in case["required_text"]),
                            "Repaired-section regression failed.")
                    message = "regression passed"
                else:
                    record["known_positive_alarm_numbers"] = case["known_positive_alarm_numbers"]
                    if group == "specific_semantic_cases":
                        record["score"] = score_results(results, case["known_positive_alarm_numbers"],
                                                        config["source"]["document_id"])
                        message = f"first known-positive rank: {record['score']['first_known_positive_rank']}"
                    else:
                        message = "saved for qualitative review; excluded from metrics"
                record["status"] = "completed"
                print(f"{case['id']}: {message}", flush=True)
            except Exception as error:
                record.update(status="failed", error=f"{type(error).__name__}: {error}")
                raise
            except KeyboardInterrupt:
                record["status"] = "interrupted"
                raise
            finally:
                record["elapsed_seconds"] = round(time.perf_counter() - start, 4)


def save_report(root, report):
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    directory = root / "evaluation" / "results"
    require(directory.resolve().is_relative_to(root.resolve()), "Report folder escapes the project.")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    path = directory / f"retrieval_{stamp}_{uuid4().hex[:8]}.json"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    return path


def main(root=PROJECT_ROOT, search=post_search):
    report = {"schema_version": 1, "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "running", "metrics": None, "cases": [],
              "interpretation": "Known-positive development retrieval indicators, not diagnostic accuracy, exhaustive recall or calibrated confidence. Unlisted results are unjudged.",
              "timing_scope": "Per-request wall time includes HTTP, validation and possible model/cache loading; not a controlled latency benchmark.",
              "backend_loaded_code_verified": False, "python_version": sys.version.split()[0]}
    try:
        path = root / "evaluation" / "retrieval_cases_v2.json"
        cases_before = file_hash(path)
        config = load_cases(path)
        report.update(evaluation_id=config["evaluation_id"], evaluation_config=config,
                      endpoint="http://127.0.0.1:8000" + API_PATH)
        context = preflight(root, config)
        watched = {path: cases_before, **context["files"]}
        for relative in ("evaluation/evaluate_retrieval.py", "app/main.py",
                         "app/services/retrieval_service.py", "app/services/embedding_service.py",
                         "app/services/embedding_preparer.py"):
            candidate = root / relative
            if candidate.is_file():
                watched[candidate] = file_hash(candidate)
        report["local_files_sha256"] = {str(p.relative_to(root)): h for p, h in watched.items()}
        report["store_embedding_metadata"] = context["embedding"]
        print("Source and vector-store checks passed. Calling FastAPI...", flush=True)
        run_cases(config, context, report["cases"], search)
        require(all(file_hash(p) == h for p, h in watched.items()), "A local input/code file changed during evaluation.")
        report["metrics"] = aggregate(report["cases"], len(config["specific_semantic_cases"]))
        report["status"] = "completed"
    except KeyboardInterrupt:
        report.update(status="interrupted", metrics=None,
                      error="Evaluation interrupted; no aggregate metrics reported.")
    except Exception as error:
        report.update(status="failed", metrics=None, error=f"{type(error).__name__}: {error}")
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    try:
        saved = save_report(root, report)
    except Exception as error:
        print(f"Could not save the report: {error}")
        return 1
    print("Report:", saved)
    if report["status"] != "completed":
        print("Evaluation stopped:", report["error"])
        return 1
    print(json.dumps(report["metrics"], indent=2))
    print("Evaluation completed. Review unjudged results before changing labels or ranking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())