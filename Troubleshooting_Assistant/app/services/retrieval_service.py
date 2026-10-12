"""Read-only retrieval from stores created by embedding_service.py."""

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from app.services import registry_backend

from app.services.embedding_preparer import (
    MODEL_NAME, MODEL_TOKEN_LIMIT, count_tokens, get_tokenizer,
)
from app.services.embedding_service import (
    EMBEDDING_DIMENSION, EMBEDDING_LOCK, VECTOR_DIRECTORY,
    get_embedding_model, validate_vectors,
)


QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def normalize_alarm_number(value):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,8}", value.strip()):
        raise ValueError("alarm_number must contain 1 to 8 digits, for example '1001'.")
    return str(int(value.strip()))


def valid_pages(pages):
    return (
        isinstance(pages, list) and bool(pages)
        and all(type(page) is int and page > 0 for page in pages)
    )


def validate_store(vectors, chunk_ids, metadata):
    if not isinstance(metadata, dict):
        raise ValueError("Vector-store metadata must be a JSON object.")
    for key in ("document_id", "source_filename"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f"Invalid store {key}.")
    info = metadata.get("embedding")
    expected = {
        "schema_version": 1, "model_name": MODEL_NAME,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "model_token_limit": MODEL_TOKEN_LIMIT,
        "dtype": "float32", "document_prompt": "",
    }
    if not isinstance(info, dict) or any(info.get(k) != v for k, v in expected.items()):
        raise ValueError("The vector store is incompatible with this local BGE model.")
    if info.get("normalized") is not True:
        raise ValueError("The store must contain normalized embeddings.")
    chunks, parent_list = metadata.get("chunks"), metadata.get("parents")
    if not isinstance(chunks, list) or not chunks or not isinstance(parent_list, list) or not parent_list:
        raise ValueError("The store must contain chunks and full parent sections.")
    if metadata.get("total_chunks") != len(chunks):
        raise ValueError("Stored chunk counts do not match.")
    if vectors.dtype != np.float32:
        raise ValueError("Expected float32 embeddings.")
    vectors = validate_vectors(vectors, len(chunks))
    if chunk_ids.shape != (len(chunks),) or chunk_ids.dtype.kind != "U":
        raise ValueError("Invalid chunk-ID array.")

    parents = {}
    for parent in parent_list:
        pid = parent.get("parent_id") if isinstance(parent, dict) else None
        if not isinstance(pid, str) or not pid.strip() or pid in parents:
            raise ValueError("Missing or duplicate parent_id in the store.")
        if not isinstance(parent.get("text"), str) or not parent["text"].strip():
            raise ValueError(f"Missing parent text: {pid}")
        if not valid_pages(parent.get("page_numbers")):
            raise ValueError(f"Invalid parent pages: {pid}")
        for key in ("document_id", "source_filename"):
            if parent.get(key) != metadata[key]:
                raise ValueError(f"Mismatched parent {key}: {pid}")
        if parent.get("alarm_number") is not None:
            normalize_alarm_number(parent["alarm_number"])
        parents[pid] = parent

    seen_ids, referenced_parents = set(), set()
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError("Every stored chunk must be a JSON object.")
        cid, pid = chunk.get("chunk_id"), chunk.get("parent_id")
        if not isinstance(cid, str) or not cid.strip() or cid in seen_ids:
            raise ValueError("Missing or duplicate chunk_id in the store.")
        seen_ids.add(cid)
        if chunk.get("vector_index") != index or cid != chunk_ids[index]:
            raise ValueError(f"Vector-to-chunk mapping mismatch at row {index}.")
        if not isinstance(pid, str) or pid not in parents:
            raise ValueError(f"Missing parent for chunk: {cid}")
        referenced_parents.add(pid)
        if not isinstance(chunk.get("text"), str) or not chunk["text"].strip():
            raise ValueError(f"Missing chunk text: {cid}")
        if not valid_pages(chunk.get("page_numbers")):
            raise ValueError(f"Invalid chunk pages: {cid}")
        if not set(chunk["page_numbers"]).issubset(parents[pid]["page_numbers"]):
            raise ValueError(f"Chunk pages fall outside its parent: {cid}")
        for key in ("document_id", "source_filename", "alarm_number"):
            if chunk.get(key) != parents[pid].get(key):
                raise ValueError(f"Mismatched chunk {key}: {cid}")
        count = chunk.get("token_count")
        if type(count) is not int or not 0 < count <= MODEL_TOKEN_LIMIT:
            raise ValueError(f"Invalid stored token count: {cid}")
    if referenced_parents != set(parents):
        raise ValueError("Some parent sections have no indexed chunks.")
    vectors.setflags(write=False)
    return vectors, metadata, parents


@lru_cache(maxsize=2)
def _load_store_cached(path, modified_ns, size_bytes):
    # Timestamp and size are cache keys, not additional files to read.
    store = np.load(path, allow_pickle=False)
    if not isinstance(store, np.lib.npyio.NpzFile):
        raise ValueError("Expected a .npz archive, not a single NumPy array.")
    with store:
        if set(store.files) != {"embeddings", "chunk_ids", "metadata_utf8"}:
            raise ValueError("Unexpected arrays in the vector store.")
        vectors, chunk_ids = store["embeddings"], store["chunk_ids"]
        raw_metadata = store["metadata_utf8"]
        if raw_metadata.dtype != np.uint8 or raw_metadata.ndim != 1:
            raise ValueError("Invalid metadata encoding in the vector store.")
        metadata = json.loads(raw_metadata.tobytes().decode("utf-8"))
    return validate_store(vectors, chunk_ids, metadata)


def load_vector_store(vector_store_filename):
    if (
        not isinstance(vector_store_filename, str)
        or any(c in vector_store_filename for c in '/\\:\x00')
        or Path(vector_store_filename).suffix.lower() != ".npz"
    ):
        raise ValueError("Provide only the .npz filename, not a folder path.")
    path = (VECTOR_DIRECTORY / vector_store_filename).resolve()
    if path.parent != VECTOR_DIRECTORY.resolve():
        raise ValueError("The file must be inside vector_store.")
    if not path.is_file():
        raise FileNotFoundError("Vector store not found.")
    stat = path.stat()
    return _load_store_cached(str(path), stat.st_mtime_ns, stat.st_size)


def make_result(parent, rank, chunk=None, score=None):
    return {
        "rank": rank,
        "parent_id": parent["parent_id"],
        "document_id": parent["document_id"],
        "source_filename": parent["source_filename"],
        "alarm_number": parent.get("alarm_number"),
        "alarm_title": parent.get("alarm_title"),
        "page_numbers": list(parent["page_numbers"]),
        "text": parent["text"],
        "cosine_similarity": None if score is None else round(float(np.clip(score, -1, 1)), 6),
        "matched_chunk_id": None if chunk is None else chunk["chunk_id"],
        "matched_chunk_text": None if chunk is None else chunk["text"],
        "matched_chunk_pages": [] if chunk is None else list(chunk["page_numbers"]),
        "matched_chunk_pages_scope": None if chunk is None else chunk.get("page_numbers_scope", "source_chunk"),
    }



# === ENTERPRISE METADATA-AWARE RETRIEVAL V1 ===

ENTERPRISE_RETRIEVAL_FILTER_FIELDS = (
    "plant_id",
    "department",
    "equipment_id",
    "equipment_type",
    "manufacturer",
    "model",
    "document_family_id",
    "document_type",
    "revision",
    "document_status",
)


def _normalize_retrieval_filters(
    metadata_filters=None,
):
    """
    Validate optional enterprise metadata filters.

    Missing metadata is not inferred.
    """
    if metadata_filters is None:
        return {}

    if not isinstance(metadata_filters, dict):
        raise ValueError(
            "metadata_filters must be an object or null."
        )

    unknown = sorted(
        set(metadata_filters)
        - set(ENTERPRISE_RETRIEVAL_FILTER_FIELDS)
    )

    if unknown:
        raise ValueError(
            "Unsupported metadata filter field(s): "
            + ", ".join(unknown)
        )

    normalized = {}

    for field in ENTERPRISE_RETRIEVAL_FILTER_FIELDS:

        value = metadata_filters.get(field)

        if value is None:
            continue

        if not isinstance(value, str):
            raise ValueError(
                f"{field} filter must be a string or null."
            )

        value = value.strip()

        if not value:
            continue

        if len(value) > 255:
            raise ValueError(
                f"{field} filter exceeds 255 characters."
            )

        normalized[field] = value

    return normalized


def _enterprise_metadata_matches(
    enterprise_metadata,
    metadata_filters,
):
    """
    Require every explicit filter to match.

    Legacy chunks remain eligible only when no enterprise
    filters were supplied.
    """
    if not metadata_filters:
        return True

    if not isinstance(enterprise_metadata, dict):
        return False

    for field, expected in metadata_filters.items():

        actual = enterprise_metadata.get(field)

        if not isinstance(actual, str):
            return False

        if (
            actual.strip().casefold()
            != expected.casefold()
        ):
            return False

    return True



# === REGISTRY-DRIVEN MULTI-DOCUMENT RETRIEVAL V1 ===

ENTERPRISE_NPZ_CANDIDATE_LIMIT = 25


def _sha256_registered_vector_file(
    path: Path,
) -> str:
    """
    Calculate the SHA-256 fingerprint of one vector artifact.
    """
    path = Path(path)

    hasher = hashlib.sha256()

    with path.open("rb") as handle:

        while True:

            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            hasher.update(block)

    return hasher.hexdigest()


def _load_registered_vector_artifact(
    artifact: dict,
):
    """
    Verify one registry-bound NPZ artifact before retrieval.

    Missing or changed artifacts fail closed.
    """
    if not isinstance(artifact, dict):
        raise ValueError(
            "Registered vector artifact must be an object."
        )

    required = (
        "document_id",
        "vector_store_filename",
        "vector_store_sha256",
        "prepared_sha256",
        "embedding_model",
        "embedding_dimension",
        "vector_count",
    )

    missing = [
        key
        for key in required
        if key not in artifact
    ]

    if missing:
        raise ValueError(
            "Registered vector artifact is missing "
            f"fields: {missing}"
        )

    filename = artifact[
        "vector_store_filename"
    ]

    if (
        not isinstance(filename, str)
        or not filename.strip()
        or any(
            character in filename
            for character in "/\\:\x00"
        )
        or Path(filename).name != filename
        or Path(filename).suffix.lower() != ".npz"
    ):
        raise ValueError(
            "Registered vector filename is invalid."
        )

    filename = filename.strip()

    path = (
        VECTOR_DIRECTORY
        / filename
    ).resolve()

    if (
        path.parent
        != VECTOR_DIRECTORY.resolve()
    ):
        raise ValueError(
            "Registered vector artifact resolves "
            "outside vector_store."
        )

    if not path.is_file():
        raise FileNotFoundError(
            "A registered vector artifact is missing."
        )

    actual_sha256 = (
        _sha256_registered_vector_file(
            path
        )
    )

    if (
        actual_sha256
        != artifact[
            "vector_store_sha256"
        ]
    ):
        raise ValueError(
            "Registered vector artifact SHA-256 mismatch."
        )

    vectors, metadata, parents = (
        load_vector_store(
            filename
        )
    )

    if (
        metadata.get("document_id")
        != artifact["document_id"]
    ):
        raise ValueError(
            "Vector-store document_id differs from "
            "the enterprise artifact registry."
        )

    if (
        vectors.shape[0]
        != artifact["vector_count"]
    ):
        raise ValueError(
            "Vector count differs from the "
            "enterprise artifact registry."
        )

    embedding = metadata.get(
        "embedding"
    )

    if not isinstance(
        embedding,
        dict,
    ):
        raise ValueError(
            "Vector store has invalid embedding metadata."
        )

    if (
        embedding.get("model_name")
        != artifact["embedding_model"]
    ):
        raise ValueError(
            "Embedding model differs from the "
            "enterprise artifact registry."
        )

    if (
        embedding.get(
            "embedding_dimension"
        )
        != artifact[
            "embedding_dimension"
        ]
    ):
        raise ValueError(
            "Embedding dimension differs from the "
            "enterprise artifact registry."
        )

    if (
        embedding.get(
            "prepared_sha256"
        )
        != artifact[
            "prepared_sha256"
        ]
    ):
        raise ValueError(
            "Prepared-document SHA-256 differs from "
            "the enterprise artifact registry."
        )

    return (
        vectors,
        metadata,
        parents,
    )


def _enterprise_search_response_base(
    *,
    query,
    alarm,
    filters,
    discovery,
):
    ambiguous = discovery.get(
        "ambiguous_documents",
        [],
    )

    return {
        "backend":
            "registry_npz_bridge",

        "query":
            query,

        "alarm_number":
            alarm,

        "metadata_filters":
            filters,

        "metadata_filter_applied":
            bool(filters),

        "documents_with_registered_artifacts":
            discovery.get(
                "documents_with_artifacts",
                0,
            ),

        "registered_artifacts_count":
            discovery.get(
                "artifacts_count",
                0,
            ),

        "ambiguous_documents":
            ambiguous,

        "ambiguous_documents_count":
            len(ambiguous),

        "automatic_artifact_selection":
            False,

        "authorization_enforced":
            False,

        "production_scale_claimed":
            False,
    }


def retrieve_enterprise_sections(
    query="",
    alarm_number=None,
    top_k=5,
    metadata_filters=None,
    *,
    database_path=None,
    candidate_limit=ENTERPRISE_NPZ_CANDIDATE_LIMIT,
):
    """
    Search across registry-discovered NPZ vector artifacts.

    This is a bounded development bridge before the persistent
    enterprise vector backend.

    Documents containing multiple registered vector artifacts
    are withheld rather than automatically selecting one.
    """
    if (
        not isinstance(query, str)
        or len(query) > 4000
    ):
        raise ValueError(
            "query must be a string of at most 4000 characters."
        )

    if (
        type(top_k) is not int
        or not 1 <= top_k <= 10
    ):
        raise ValueError(
            "top_k must be an integer between 1 and 10."
        )

    if (
        type(candidate_limit) is not int
        or not 1 <= candidate_limit <= 100
    ):
        raise ValueError(
            "candidate_limit must be an integer "
            "between 1 and 100."
        )

    query = query.strip()

    alarm = (
        None
        if alarm_number is None
        else normalize_alarm_number(
            alarm_number
        )
    )

    if (
        alarm is None
        and not query
    ):
        raise ValueError(
            "Provide a query or an explicit alarm_number."
        )

    filters = (
        _normalize_retrieval_filters(
            metadata_filters
        )
    )

    if database_path is None:
        database_path = (
            Path(database_path)
            if database_path is not None
            else None
        )

    discovery = (
        registry_backend
        .discover_enterprise_vector_artifacts(
            filters,
            database_path=database_path,
        )
    )

    candidates = list(
        discovery.get(
            "single_artifact_candidates",
            [],
        )
    )

    ambiguous = list(
        discovery.get(
            "ambiguous_documents",
            [],
        )
    )

    response = (
        _enterprise_search_response_base(
            query=query,
            alarm=alarm,
            filters=filters,
            discovery=discovery,
        )
    )

    mode = (
        "exact_alarm"
        if alarm is not None
        else "semantic"
    )


    # --------------------------------------------------------
    # Bounded NPZ bridge.
    # --------------------------------------------------------

    if len(candidates) > candidate_limit:

        return {
            **response,

            "mode":
                mode,

            "status":
                "narrow_filters_required",

            "candidate_limit":
                candidate_limit,

            "eligible_single_artifact_documents":
                len(candidates),

            "artifacts_searched":
                0,

            "search_complete":
                False,

            "message":
                (
                    "Too many NPZ artifacts match this "
                    "development query. Provide narrower "
                    "enterprise metadata filters."
                ),

            "results_count":
                0,

            "results":
                [],
        }


    # --------------------------------------------------------
    # Nothing safely searchable.
    # --------------------------------------------------------

    if not candidates:

        if ambiguous:

            status = (
                "incomplete_due_to_artifact_ambiguity"
            )

            search_complete = False

            message = (
                "Matching documents have multiple "
                "registered vector artifacts. "
                "No artifact was selected automatically."
            )

        else:

            status = "not_found"
            search_complete = True

            message = (
                "No registered single-artifact enterprise "
                "documents matched the supplied metadata."
            )

        return {
            **response,

            "mode":
                mode,

            "status":
                status,

            "candidate_limit":
                candidate_limit,

            "eligible_single_artifact_documents":
                0,

            "artifacts_searched":
                0,

            "search_complete":
                search_complete,

            "message":
                message,

            "results_count":
                0,

            "results":
                [],
        }


    # ========================================================
    # EXACT ALARM MODE
    # ========================================================

    if alarm is not None:

        combined = []
        artifacts_searched = 0

        for artifact in candidates:

            _, _, parents = (
                _load_registered_vector_artifact(
                    artifact
                )
            )

            artifacts_searched += 1

            for parent in parents.values():

                parent_alarm = parent.get(
                    "alarm_number"
                )

                if parent_alarm is None:
                    continue

                if (
                    normalize_alarm_number(
                        parent_alarm
                    )
                    != alarm
                ):
                    continue

                result = make_result(
                    parent,
                    0,
                )

                result[
                    "vector_artifact_id"
                ] = artifact.get(
                    "vector_artifact_id"
                )

                result[
                    "vector_store_filename"
                ] = artifact[
                    "vector_store_filename"
                ]

                combined.append(
                    result
                )

        # Deterministic ordering only.
        # It is not confidence or artifact preference.
        combined.sort(
            key=lambda item: (
                str(
                    item.get(
                        "document_id",
                        "",
                    )
                ),
                str(
                    item.get(
                        "parent_id",
                        "",
                    )
                ),
                str(
                    item.get(
                        "vector_store_filename",
                        "",
                    )
                ),
            )
        )

        selected = combined[
            :top_k
        ]

        for rank, result in enumerate(
            selected,
            start=1,
        ):
            result["rank"] = rank

        if ambiguous:

            status = (
                "partial_found"
                if selected
                else
                "incomplete_due_to_artifact_ambiguity"
            )

            search_complete = False

            message = (
                "Exact alarm lookup searched eligible "
                "single-artifact documents. Documents "
                "with multiple artifacts were withheld."
            )

        else:

            status = (
                "found"
                if selected
                else "not_found"
            )

            search_complete = True

            message = (
                "Exact alarm lookup across eligible "
                "registered enterprise artifacts. "
                "No semantic fallback was used."
            )

        return {
            **response,

            "mode":
                "exact_alarm",

            "status":
                status,

            "candidate_limit":
                candidate_limit,

            "eligible_single_artifact_documents":
                len(candidates),

            "artifacts_searched":
                artifacts_searched,

            "search_complete":
                search_complete,

            "message":
                message,

            "total_matching_sections":
                len(combined),

            "has_more":
                len(combined) > len(selected),

            "results_count":
                len(selected),

            "results":
                selected,
        }


    # ========================================================
    # QUERY EMBEDDING ? CREATED ONCE
    # ========================================================

    with EMBEDDING_LOCK:

        query_tokens = count_tokens(
            QUERY_PREFIX + query,
            get_tokenizer(),
        )

        if (
            query_tokens
            > MODEL_TOKEN_LIMIT
        ):
            raise ValueError(
                "Query plus search instruction exceeds "
                "512 tokens. Shorten the query."
            )

        model = get_embedding_model()

        encoded = model.encode(
            [query],
            prompt=QUERY_PREFIX,
            batch_size=1,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        query_vector = validate_vectors(
            encoded,
            1,
        )[0]


    # ========================================================
    # SEMANTIC SEARCH ACROSS ARTIFACTS
    # ========================================================

    global_candidates = []
    artifacts_searched = 0

    for artifact in candidates:

        vectors, metadata, parents = (
            _load_registered_vector_artifact(
                artifact
            )
        )

        artifacts_searched += 1

        scores = (
            vectors
            @ query_vector
        )

        local_parents = set()
        local_results = 0

        for raw_index in np.argsort(
            -scores,
            kind="stable",
        ):

            index = int(
                raw_index
            )

            chunk = metadata[
                "chunks"
            ][index]

            parent_id = chunk[
                "parent_id"
            ]

            if parent_id in local_parents:
                continue

            local_parents.add(
                parent_id
            )

            global_candidates.append(
                {
                    "score":
                        float(
                            scores[index]
                        ),

                    "artifact":
                        artifact,

                    "parent":
                        parents[parent_id],

                    "chunk":
                        chunk,
                }
            )

            local_results += 1

            if local_results == top_k:
                break


    # ========================================================
    # GLOBAL CROSS-DOCUMENT RANKING
    # ========================================================

    global_candidates.sort(
        key=lambda item: (
            -item["score"],

            str(
                item[
                    "artifact"
                ].get(
                    "document_id",
                    "",
                )
            ),

            str(
                item[
                    "parent"
                ].get(
                    "parent_id",
                    "",
                )
            ),

            str(
                item[
                    "artifact"
                ].get(
                    "vector_store_filename",
                    "",
                )
            ),
        )
    )

    selected_candidates = (
        global_candidates[
            :top_k
        ]
    )

    results = []

    for rank, item in enumerate(
        selected_candidates,
        start=1,
    ):

        artifact = item[
            "artifact"
        ]

        result = make_result(
            item["parent"],
            rank,
            item["chunk"],
            item["score"],
        )

        result[
            "vector_artifact_id"
        ] = artifact.get(
            "vector_artifact_id"
        )

        result[
            "vector_store_filename"
        ] = artifact[
            "vector_store_filename"
        ]

        results.append(
            result
        )


    if ambiguous:

        status = (
            "partial_candidates"
            if results
            else
            "incomplete_due_to_artifact_ambiguity"
        )

        search_complete = False

        message = (
            "Ranked source candidates from eligible "
            "single-artifact documents. Documents "
            "with multiple artifacts were withheld. "
            "Similarity is not confidence."
        )

    else:

        status = (
            "candidates"
            if results
            else "not_found"
        )

        search_complete = True

        message = (
            "Ranked source candidates across eligible "
            "registered enterprise artifacts. "
            "Similarity is not confidence."
        )

    return {
        **response,

        "mode":
            "semantic",

        "status":
            status,

        "query_tokens":
            query_tokens,

        "candidate_limit":
            candidate_limit,

        "eligible_single_artifact_documents":
            len(candidates),

        "artifacts_searched":
            artifacts_searched,

        "search_complete":
            search_complete,

        "message":
            message,

        "results_count":
            len(results),

        "results":
            results,
    }


def retrieve_sections(vector_store_filename, query="", alarm_number=None, top_k=5, metadata_filters=None):
    """Explicit alarm_number selects exact lookup; query-only calls use semantic search."""
    if not isinstance(query, str) or len(query) > 4000:
        raise ValueError("query must be a string of at most 4000 characters.")
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError("top_k must be an integer between 1 and 10.")
    query = query.strip()
    alarm = None if alarm_number is None else normalize_alarm_number(alarm_number)
    if alarm is None and not query:
        raise ValueError("Provide a query or an explicit alarm_number.")

    filters = _normalize_retrieval_filters(
        metadata_filters
    )

    vectors, metadata, parents = load_vector_store(
        vector_store_filename
    )
    response = {
        "document_id": metadata["document_id"],
        "source_filename": metadata["source_filename"],
        "query": query,
        "alarm_number": alarm,
        "metadata_filters": filters,
        "metadata_filter_applied": bool(filters),
    }

    if alarm is not None:
        # Do not substitute similar alarm codes or invent a similarity score.
        matches = [
            parent for parent in parents.values()
            if parent.get("alarm_number") is not None
            and normalize_alarm_number(
                parent["alarm_number"]
            ) == alarm
            and _enterprise_metadata_matches(
                parent.get("enterprise_metadata"),
                filters,
            )
        ]
        results = [make_result(parent, i + 1) for i, parent in enumerate(matches[:top_k])]
        return {
            **response,
            "mode": "exact_alarm",
            "status": "found" if matches else "not_found",
            "total_matching_sections": len(matches),
            "has_more": len(matches) > len(results),
            "message": "Exact alarm lookup only; no semantic fallback was used.",
            "results_count": len(results),
            "results": results,
        }

    with EMBEDDING_LOCK:
        query_tokens = count_tokens(QUERY_PREFIX + query, get_tokenizer())
        if query_tokens > MODEL_TOKEN_LIMIT:
            raise ValueError("Query plus search instruction exceeds 512 tokens. Shorten the query.")
        model = get_embedding_model()
        encoded = model.encode(
            [query], prompt=QUERY_PREFIX, batch_size=1,
            normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False,
        )
        query_vector = validate_vectors(encoded, 1)[0]

    scores = vectors @ query_vector
    results, selected_parents = [], set()
    for raw_index in np.argsort(-scores, kind="stable"):
        index = int(raw_index)
        chunk = metadata["chunks"][index]

        if not _enterprise_metadata_matches(
            chunk.get("enterprise_metadata"),
            filters,
        ):
            continue

        pid = chunk["parent_id"]
        if pid in selected_parents:
            continue
        selected_parents.add(pid)
        results.append(make_result(parents[pid], len(results) + 1, chunk, scores[index]))
        if len(results) == top_k:
            break
    return {
        **response,
        "mode": "semantic",
        "status": "candidates",
        "query_tokens": query_tokens,
        "message": "Ranked source candidates, not verified answers. Similarity is not confidence.",
        "results_count": len(results),
        "results": results,
    }


def retrieve_enterprise_sections_qdrant(
    client,
    query="",
    alarm_number=None,
    top_k=5,
    metadata_filters=None,
    *,
    collection_name="industrial_knowledge_dense_v1",
    database_path=None,
    candidate_limit=25,
):
    """
    Parallel enterprise retrieval using Registry eligibility
    followed by Qdrant semantic ranking.

    Development/parity path only.

    The existing enterprise retrieval path remains unchanged.
    """

    import hashlib

    from app.services import (
        qdrant_store,
        registry_backend,
    )


    # --------------------------------------------------------
    # Input validation
    # --------------------------------------------------------

    if (
        not isinstance(
            query,
            str,
        )
        or len(query) > 4000
    ):
        raise ValueError(
            "query must be a string of at most 4000 characters."
        )


    if (
        type(top_k) is not int
        or not 1 <= top_k <= 10
    ):
        raise ValueError(
            "top_k must be an integer between 1 and 10."
        )


    if (
        type(candidate_limit) is not int
        or not 1 <= candidate_limit <= 25
    ):
        raise ValueError(
            "candidate_limit must be an integer between 1 and 25."
        )


    query = query.strip()


    alarm = (
        None
        if alarm_number is None
        else normalize_alarm_number(
            alarm_number
        )
    )


    if (
        alarm is None
        and not query
    ):
        raise ValueError(
            "Provide a query or an explicit alarm_number."
        )


    # --------------------------------------------------------
    # Exact alarm remains deterministic.
    # Qdrant is not used for exact-code lookup.
    # --------------------------------------------------------

    if alarm is not None:

        result = (
            retrieve_enterprise_sections(
                query=query,
                alarm_number=alarm,
                top_k=top_k,
                metadata_filters=
                    metadata_filters,
                database_path=
                    database_path,
                candidate_limit=
                    candidate_limit,
            )
        )


        return {
            **result,

            "vector_backend":
                "deterministic_npz_exact",

            "qdrant_used":
                False,

            "automatic_artifact_selection":
                False,
        }


    # --------------------------------------------------------
    # Registry eligibility must run first.
    # --------------------------------------------------------

    discovery = (
        registry_backend
        .discover_enterprise_vector_artifacts(
            metadata_filters,
            database_path=
                database_path,
        )
    )


    candidates = list(
        discovery.get(
            "single_artifact_candidates",
            [],
        )
    )


    ambiguous = list(
        discovery.get(
            "ambiguous_documents",
            [],
        )
    )


    # The cap is deterministic only.
    # It does not choose between artifacts belonging
    # to one document because ambiguous documents are withheld.
    candidates = (
        candidates[
            :candidate_limit
        ]
    )


    safe_ambiguous = [
        {
            "document_id":
                item.get(
                    "document_id"
                ),

            "artifact_count":
                item.get(
                    "artifact_count"
                ),
        }

        for item
        in ambiguous
    ]


    base_response = {
        "query":
            query,

        "alarm_number":
            None,

        "mode":
            "semantic_qdrant",

        "vector_backend":
            "qdrant",

        "metadata_filters":
            discovery.get(
                "metadata_filters",
                {},
            ),

        "metadata_filter_applied":
            discovery.get(
                "metadata_filter_applied",
                False,
            ),

        "documents_with_artifacts":
            discovery.get(
                "documents_with_artifacts",
                0,
            ),

        "registered_artifacts_count":
            discovery.get(
                "artifacts_count",
                0,
            ),

        "eligible_artifacts_count":
            len(candidates),

        "ambiguous_documents":
            safe_ambiguous,

        "automatic_artifact_selection":
            False,

        "authorization_enforced":
            False,

        "qdrant_used":
            False,
    }


    if not candidates:

        return {
            **base_response,

            "status":
                (
                    "ambiguous"
                    if safe_ambiguous
                    else "not_found"
                ),

            "query_tokens":
                None,

            "results_count":
                0,

            "results":
                [],

            "message":
                (
                    "No unambiguous registered vector artifact "
                    "is eligible for Qdrant ranking."
                ),
        }


    # --------------------------------------------------------
    # Validate every Registry-eligible NPZ artifact first.
    # --------------------------------------------------------

    artifact_context = {}


    vector_directory = (
        Path(
            VECTOR_DIRECTORY
        ).resolve()
    )


    for candidate in candidates:

        if not isinstance(
            candidate,
            dict,
        ):
            raise ValueError(
                "Registry returned an invalid artifact candidate."
            )


        artifact_id = (
            candidate.get(
                "vector_artifact_id"
            )
        )


        document_id = (
            candidate.get(
                "document_id"
            )
        )


        vector_filename = (
            candidate.get(
                "vector_store_filename"
            )
        )


        if (
            not isinstance(
                artifact_id,
                str,
            )
            or not artifact_id.strip()
        ):
            raise ValueError(
                "Registry candidate lacks vector_artifact_id."
            )


        if (
            not isinstance(
                document_id,
                str,
            )
            or not document_id.strip()
        ):
            raise ValueError(
                "Registry candidate lacks document_id."
            )


        if (
            not isinstance(
                vector_filename,
                str,
            )
            or not vector_filename.strip()
        ):
            raise ValueError(
                "Registry candidate lacks vector_store_filename."
            )


        vector_path = (
            vector_directory
            / vector_filename
        ).resolve()


        if (
            vector_path.parent
            != vector_directory
        ):
            raise ValueError(
                "Registered vector artifact escapes vector_store."
            )


        if not vector_path.is_file():
            raise FileNotFoundError(
                "Registered vector artifact file is missing."
            )


        digest = hashlib.sha256()


        with vector_path.open(
            "rb"
        ) as stream:

            while True:

                block = stream.read(
                    1024 * 1024
                )

                if not block:
                    break

                digest.update(
                    block
                )


        actual_sha256 = (
            digest.hexdigest()
        )


        if (
            actual_sha256
            != candidate.get(
                "vector_store_sha256"
            )
        ):
            raise ValueError(
                "Registered vector artifact SHA-256 mismatch."
            )


        vectors, metadata, parents = (
            load_vector_store(
                vector_filename
            )
        )


        if (
            metadata.get(
                "document_id"
            )
            != document_id
        ):
            raise ValueError(
                "Validated vector document_id differs "
                "from Registry candidate."
            )


        if (
            metadata.get(
                "source_filename"
            )
            != candidate.get(
                "stored_filename"
            )
        ):
            raise ValueError(
                "Validated vector source filename differs "
                "from Registry candidate."
            )


        if (
            metadata.get(
                "source_sha256"
            )
            != candidate.get(
                "source_sha256"
            )
        ):
            raise ValueError(
                "Validated vector source SHA-256 differs "
                "from Registry candidate."
            )


        embedding = (
            metadata.get(
                "embedding"
            )
        )


        if not isinstance(
            embedding,
            dict,
        ):
            raise ValueError(
                "Validated vector metadata lacks embedding provenance."
            )


        provenance_checks = (
            (
                embedding.get(
                    "prepared_filename"
                ),
                candidate.get(
                    "prepared_filename"
                ),
                "prepared_filename",
            ),

            (
                embedding.get(
                    "prepared_sha256"
                ),
                candidate.get(
                    "prepared_sha256"
                ),
                "prepared_sha256",
            ),

            (
                embedding.get(
                    "model_name"
                ),
                candidate.get(
                    "embedding_model"
                ),
                "embedding_model",
            ),

            (
                embedding.get(
                    "embedding_dimension"
                ),
                candidate.get(
                    "embedding_dimension"
                ),
                "embedding_dimension",
            ),

            (
                embedding.get(
                    "created_at_utc"
                ),
                candidate.get(
                    "embedding_created_at_utc"
                ),
                "embedding_created_at_utc",
            ),
        )


        for (
            actual,
            expected,
            field,
        ) in provenance_checks:

            if actual != expected:

                raise ValueError(
                    "Validated vector "
                    + field
                    + " differs from Registry candidate."
                )


        if (
            embedding.get(
                "normalized"
            )
            is not True
        ):
            raise ValueError(
                "Validated vectors are not marked normalized."
            )


        if (
            vectors.shape[0]
            != candidate.get(
                "vector_count"
            )
        ):
            raise ValueError(
                "Validated vector count differs "
                "from Registry candidate."
            )


        chunks = (
            metadata.get(
                "chunks"
            )
        )


        if (
            not isinstance(
                chunks,
                list,
            )
            or len(chunks)
            != vectors.shape[0]
        ):
            raise ValueError(
                "Validated chunk metadata is inconsistent."
            )


        chunk_by_id = {}


        for expected_index, chunk in enumerate(
            chunks
        ):

            if not isinstance(
                chunk,
                dict,
            ):
                raise ValueError(
                    "Validated chunk metadata is invalid."
                )


            chunk_id = (
                chunk.get(
                    "chunk_id"
                )
            )


            if (
                not isinstance(
                    chunk_id,
                    str,
                )
                or not chunk_id.strip()
            ):
                raise ValueError(
                    "Validated chunk lacks chunk_id."
                )


            if (
                chunk.get(
                    "vector_index"
                )
                != expected_index
            ):
                raise ValueError(
                    "Validated chunk vector_index ordering changed."
                )


            if (
                chunk_id
                in chunk_by_id
            ):
                raise ValueError(
                    "Validated chunk IDs are not unique."
                )


            chunk_by_id[
                chunk_id
            ] = chunk


        artifact_context[
            artifact_id
        ] = {
            "candidate":
                candidate,

            "metadata":
                metadata,

            "parents":
                parents,

            "chunk_by_id":
                chunk_by_id,
        }


    eligible_artifact_ids = list(
        artifact_context
    )


    # --------------------------------------------------------
    # Encode the semantic query exactly once.
    # --------------------------------------------------------

    with EMBEDDING_LOCK:

        query_tokens = count_tokens(
            QUERY_PREFIX + query,
            get_tokenizer(),
        )


        if (
            query_tokens
            > MODEL_TOKEN_LIMIT
        ):
            raise ValueError(
                "Query plus search instruction exceeds "
                "512 tokens. Shorten the query."
            )


        model = (
            get_embedding_model()
        )


        encoded = model.encode(
            [
                query
            ],

            prompt=
                QUERY_PREFIX,

            batch_size=
                1,

            normalize_embeddings=
                True,

            convert_to_numpy=
                True,

            show_progress_bar=
                False,
        )


        query_vector = (
            validate_vectors(
                encoded,
                1,
            )[0]
        )


    # --------------------------------------------------------
    # Qdrant semantic ranking only inside exact
    # Registry-eligible vector_artifact_ids.
    #
    # Parent-level results require adaptive raw-candidate depth.
    # One parent may own many highly ranked chunks, so applying
    # parent deduplication after a fixed 15-point truncation can
    # under-fill top_k even when valid distinct parents exist.
    # --------------------------------------------------------

    total_eligible_vectors = sum(
        int(
            context[
                "candidate"
            ][
                "vector_count"
            ]
        )

        for context
        in artifact_context.values()
    )


    if total_eligible_vectors <= 0:
        raise RuntimeError(
            "Registry-eligible artifacts contain no vectors."
        )


    maximum_raw_candidates = min(
        total_eligible_vectors,
        1000,
    )


    raw_candidate_limit = min(
        maximum_raw_candidates,
        max(
            15,
            top_k * 3,
        ),
    )


    candidate_expansions = 0


    while True:

        ranked = (
            qdrant_store
            .query_eligible_artifacts_deep(
                client,

                query_vector=
                    query_vector,

                eligible_vector_artifact_ids=
                    eligible_artifact_ids,

                limit=
                    raw_candidate_limit,

                collection_name=
                    collection_name,
            )
        )


        candidate_expansions += 1


        distinct_parent_identities = set()


        for item in ranked.get(
            "results",
            [],
        ):

            artifact_id = item.get(
                "vector_artifact_id"
            )


            context = artifact_context.get(
                artifact_id
            )


            if context is None:
                raise RuntimeError(
                    "Qdrant returned an artifact outside "
                    "the Registry-eligible set."
                )


            chunk = (
                context[
                    "chunk_by_id"
                ].get(
                    item.get(
                        "chunk_id"
                    )
                )
            )


            if chunk is None:
                raise RuntimeError(
                    "Qdrant returned an unknown chunk_id "
                    "during candidate-depth evaluation."
                )


            parent_id = chunk.get(
                "parent_id"
            )


            if (
                not isinstance(
                    parent_id,
                    str,
                )
                or not parent_id
            ):
                raise RuntimeError(
                    "Validated chunk lacks parent_id."
                )


            distinct_parent_identities.add(
                (
                    artifact_id,
                    parent_id,
                )
            )


            if (
                len(
                    distinct_parent_identities
                )
                >= top_k
            ):
                break


        enough_distinct_parents = (
            len(
                distinct_parent_identities
            )
            >= top_k
        )


        qdrant_exhausted = (
            ranked.get(
                "results_count",
                0,
            )
            < raw_candidate_limit
            or raw_candidate_limit
            >= total_eligible_vectors
        )


        if (
            enough_distinct_parents
            or qdrant_exhausted
        ):
            break


        if (
            raw_candidate_limit
            >= maximum_raw_candidates
        ):

            raise RuntimeError(
                "Qdrant candidate expansion reached "
                "the bounded 1000-point limit before "
                "top_k distinct parents were found. "
                "No NPZ fallback was used."
            )


        next_limit = min(
            maximum_raw_candidates,
            max(
                raw_candidate_limit * 2,
                raw_candidate_limit + top_k,
            ),
        )


        if (
            next_limit
            <= raw_candidate_limit
        ):
            raise RuntimeError(
                "Qdrant candidate expansion made no progress."
            )


        raw_candidate_limit = (
            next_limit
        )


    # --------------------------------------------------------
    # Hydrate Qdrant identities from validated NPZ evidence.
    # --------------------------------------------------------

    results = []

    selected_parents = set()


    for item in ranked.get(
        "results",
        [],
    ):

        artifact_id = (
            item.get(
                "vector_artifact_id"
            )
        )


        context = (
            artifact_context.get(
                artifact_id
            )
        )


        if context is None:
            raise RuntimeError(
                "Qdrant returned an artifact outside "
                "the Registry-eligible set."
            )


        expected_document_id = (
            context[
                "candidate"
            ].get(
                "document_id"
            )
        )


        if (
            item.get(
                "document_id"
            )
            != expected_document_id
        ):
            raise RuntimeError(
                "Qdrant document_id differs from "
                "the validated Registry artifact."
            )


        chunk_id = (
            item.get(
                "chunk_id"
            )
        )


        chunk = (
            context[
                "chunk_by_id"
            ].get(
                chunk_id
            )
        )


        if chunk is None:
            raise RuntimeError(
                "Qdrant returned an unknown chunk_id."
            )


        if (
            item.get(
                "vector_index"
            )
            != chunk.get(
                "vector_index"
            )
        ):
            raise RuntimeError(
                "Qdrant vector_index differs from "
                "validated chunk metadata."
            )


        parent_id = (
            chunk.get(
                "parent_id"
            )
        )


        parent = (
            context[
                "parents"
            ].get(
                parent_id
            )
        )


        if parent is None:
            raise RuntimeError(
                "Validated parent evidence is missing."
            )


        parent_identity = (
            artifact_id,
            parent_id,
        )


        if (
            parent_identity
            in selected_parents
        ):
            continue


        selected_parents.add(
            parent_identity
        )


        result = make_result(
            parent,
            len(results) + 1,
            chunk,
            item.get(
                "cosine_similarity"
            ),
        )


        result[
            "vector_artifact_id"
        ] = artifact_id


        result[
            "similarity_is_confidence"
        ] = False


        results.append(
            result
        )


        if (
            len(results)
            == top_k
        ):
            break


    return {
        **base_response,

        "qdrant_used":
            True,

        "status":
            (
                "candidates"
                if results
                else "not_found"
            ),

        "query_tokens":
            query_tokens,

        "eligible_vector_artifact_ids":
            eligible_artifact_ids,

        "qdrant_ranked_points_count":
            ranked.get(
                "results_count",
                0,
            ),

        "qdrant_raw_candidate_limit_used":
            raw_candidate_limit,

        "qdrant_candidate_expansions":
            candidate_expansions,

        "qdrant_parent_dedup_strategy":
            "adaptive_raw_candidate_expansion_v1",

        "results_count":
            len(results),

        "results":
            results,

        "message": (
            "Ranked source candidates from Registry-eligible "
            "Qdrant vectors. Similarity is not confidence. "
            "No diagnosis or automatic action is approved."
        ),
    }


def retrieve_enterprise_sections_configured(
    query="",
    alarm_number=None,
    top_k=5,
    metadata_filters=None,
    *,
    database_path=None,
    candidate_limit=25,
):
    """
    Dispatch enterprise retrieval using trusted process configuration.

    The caller does not select the backend, Qdrant storage path,
    or Qdrant collection.

    NPZ remains the default reference/migration backend.
    There is no silent Qdrant-to-NPZ fallback.
    """

    from app.services import qdrant_store


    backend = (
        qdrant_store.get_vector_retrieval_backend()
    )


    if backend == "npz":

        return retrieve_enterprise_sections(
            query=query,
            alarm_number=alarm_number,
            top_k=top_k,
            metadata_filters=metadata_filters,
            database_path=database_path,
            candidate_limit=candidate_limit,
        )


    if backend == "qdrant":

        client = (
            qdrant_store.get_application_qdrant_client()
        )

        collection_name = (
            qdrant_store
            .get_application_qdrant_collection_name()
        )


        return retrieve_enterprise_sections_qdrant(
            client,
            query=query,
            alarm_number=alarm_number,
            top_k=top_k,
            metadata_filters=metadata_filters,
            collection_name=collection_name,
            database_path=database_path,
            candidate_limit=candidate_limit,
        )


    raise RuntimeError(
        "Unsupported trusted vector retrieval backend."
    )
