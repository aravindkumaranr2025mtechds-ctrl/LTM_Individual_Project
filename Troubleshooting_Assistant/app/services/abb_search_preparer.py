"""Prepare complete ABB table records for BGE; do not generate vectors."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from app.services import embedding_preparer as embeddings
from app.services.abb_document_extractor import (
    EXPECTED_PDF_BYTES,
    build_abb_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRUCTURED_DIRECTORY = PROJECT_ROOT / "data" / "structured_documents"
RAW_DIRECTORY = PROJECT_ROOT / "data" / "raw_documents"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "embedding_documents"
STRATEGY = "abb_complete_records_v1"


def _validate_filename(filename, suffix):
    if (
        not isinstance(filename, str)
        or not filename
        or filename != filename.strip()
        or any(c in filename for c in '/\\:')
        or any(ord(c) < 32 for c in filename)
        or Path(filename).suffix.lower() != suffix
    ):
        raise ValueError(f"Provide only a {suffix} filename, not a path.")


def _input_path(directory, filename, suffix):
    _validate_filename(filename, suffix)
    path = (directory / filename).resolve()
    if path.parent != directory.resolve():
        raise ValueError(f"The input must be inside {directory.name}.")
    if not path.is_file():
        raise FileNotFoundError(f"File not found in {directory.name}: {filename}")
    return path


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _canonical(document):
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def build_abb_search_document(document, pdf_bytes, tokenizer):
    """Verify the source, then make one complete passage per table record."""
    if not isinstance(document, dict):
        raise ValueError("The structured document must be a JSON object.")
    if (
        embeddings.MODEL_NAME != "BAAI/bge-small-en-v1.5"
        or embeddings.MODEL_TOKEN_LIMIT != 512
    ):
        raise ValueError("The existing BGE configuration changed. Review it first.")

    # Checks the PDF fingerprint and rebuilds the reviewed table extraction.
    # Compare all fields, including context, coordinates and extractor version.
    reference = build_abb_document(pdf_bytes, document.get("source_filename"))
    if _canonical(document) != _canonical(reference):
        raise ValueError(
            "Structured JSON differs from the reviewed PDF extraction or "
            "the extractor code has changed. Keep the files and review the "
            "difference; do not bypass this check."
        )

    prepared = deepcopy(document)
    parents, chunks = [], []
    identity = {
        key: document[key]
        for key in (
            "document_id", "source_filename", "manufacturer",
            "document_reference", "revision", "printed_revision_date",
        )
    }

    for record in prepared["records"]:
        text = (
            f"Source: ABB low voltage motors manual, "
            f"{document['document_reference']}, Rev {document['revision']} "
            f"({document['printed_revision_date']}).\n"
            f"Symptom: {record['symptom']}\n"
            f"Possible cause: {record['possible_cause']}\n"
            f"Manufacturer guidance: {record['manufacturer_guidance']}"
        )
        token_count = embeddings.count_tokens(text, tokenizer)
        if not 0 < token_count <= embeddings.MODEL_TOKEN_LIMIT:
            raise ValueError(
                f"Record {record['record_id']} has {token_count} tokens. "
                "It cannot be kept complete within 512 tokens. "
                "No truncation or automatic splitting was performed."
            )

        parents.append({
            **deepcopy(record),
            **identity,
            "parent_id": record["record_id"],
            "section_type": "troubleshooting_record",
            "alarm_number": None,
            "alarm_title": None,
            "text": text,
            "usage": deepcopy(document["usage"]),
        })
        chunks.append({
            **identity,
            "chunk_id": f"{record['record_id']}_c001",
            "parent_id": record["record_id"],
            "record_id": record["record_id"],
            "symptom_id": record["symptom_id"],
            "section_type": "troubleshooting_record",
            "alarm_number": None,
            "alarm_title": None,
            "page_numbers": list(record["page_numbers"]),
            "page_numbers_scope": "source_record",
            "context_ids": list(record["context_ids"]),
            "text": text,
            "word_count": len(text.split()),
            "token_count": token_count,
        })

    prepared.update({
        "parents": parents,
        "chunks": chunks,
        "total_sections": len(parents),
        "alarm_sections": 0,
        "total_chunks": len(chunks),
        "preparation": {
            "strategy": STRATEGY,
            "embedding_model": embeddings.MODEL_NAME,
            "max_tokens": embeddings.MODEL_TOKEN_LIMIT,
            "token_counts_include_special_tokens": True,
            "document_prompt": "",
            "overlap_tokens": 0,
            "input_records": len(prepared["records"]),
            "output_chunks": len(chunks),
            "maximum_output_tokens": max(c["token_count"] for c in chunks),
            "one_complete_record_per_chunk": True,
            "text_format": "labels_plus_whitespace_normalized_source_cells",
            "source_verification": "exact_match_to_reextracted_reviewed_pdf",
            "context_handling": "retained_in_metadata_not_embedded",
        },
    })
    return prepared


def prepare_abb_search_document(structured_filename):
    """Save a separate embedding-ready JSON; never overwrite an existing file."""
    input_path = _input_path(STRUCTURED_DIRECTORY, structured_filename, ".json")
    output_path = OUTPUT_DIRECTORY / f"{Path(structured_filename).stem}_ready.json"
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"Prepared file already exists: {output_path.name}")

    structured_bytes = input_path.read_bytes()
    document = json.loads(
        structured_bytes.decode("utf-8-sig"), object_pairs_hook=_unique_keys,
    )
    if not isinstance(document, dict):
        raise ValueError("The structured document must be a JSON object.")
    pdf_path = _input_path(RAW_DIRECTORY, document.get("source_filename"), ".pdf")
    if pdf_path.stat().st_size != EXPECTED_PDF_BYTES:
        raise ValueError("Unexpected PDF size; use the reviewed ABB source.")
    pdf_bytes = pdf_path.read_bytes()

    # Loads only the existing local tokenizer, not model weights or a new model.
    prepared = build_abb_search_document(
        document, pdf_bytes, embeddings.get_tokenizer(),
    )
    prepared["preparation"].update({
        "structured_filename": structured_filename,
        "structured_sha256": hashlib.sha256(structured_bytes).hexdigest(),
        "preparer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "tokenizer_helper_sha256": hashlib.sha256(
            Path(embeddings.__file__).read_bytes()
        ).hexdigest(),
    })
    payload = json.dumps(prepared, ensure_ascii=False, indent=2, allow_nan=False)
    for path, original in ((input_path, structured_bytes), (pdf_path, pdf_bytes)):
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(original).digest():
            raise ValueError("An input changed during preparation. No output was saved.")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    handle = output_path.open("x", encoding="utf-8", newline="\n")
    try:
        with handle:
            handle.write(payload)
    except BaseException:
        output_path.unlink(missing_ok=True)  # Only our incomplete new output.
        raise

    return {
        "document_id": prepared["document_id"],
        "source_filename": prepared["source_filename"],
        "source_sha256": prepared["source_sha256"],
        "total_symptom_groups": prepared["total_symptom_groups"],
        "total_records": prepared["total_records"],
        "total_sections": prepared["total_sections"],
        **prepared["preparation"],
        "prepared_filename": output_path.name,
        "saved_location": str(output_path),
    }