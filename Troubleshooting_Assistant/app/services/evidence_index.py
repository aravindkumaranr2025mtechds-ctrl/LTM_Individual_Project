"""Create and validate draft ABB evidence spans; no model or diagnosis calls.

Version 1 indexes source fields for later condition annotation. It does not
contain reviewed conditions or establish applicability to a particular motor.
Offsets refer to the prepared parent text, not to PDF bytes or rendered pages.
"""

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREPARED_DIRECTORY = PROJECT_ROOT / "data" / "embedding_documents"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "condition_evidence"
STRATEGY = "abb_source_evidence_draft_v1"
FIELDS = (
    ("symptom", "Symptom", "symptom"),
    ("possible_cause", "Possible cause", "cause"),
    ("manufacturer_guidance", "Manufacturer guidance", "remedy"),
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _filename(value):
    _require(
        _text(value) and value == value.strip()
        and not any(c in value for c in '/\\:')
        and not any(ord(c) < 32 for c in value)
        and Path(value).suffix.lower() == ".json",
        "Provide a JSON filename inside the data folder, not a path.",
    )
    return value


def _input_path(directory, filename):
    path = directory / _filename(filename)
    _require(path.resolve().parent == directory.resolve(), "Input escapes its data folder.")
    if not path.is_file():
        raise FileNotFoundError(f"File not found in {directory.name}: {filename}")
    return path


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def _decode(raw):
    value = json.loads(
        raw.decode("utf-8-sig"), object_pairs_hook=_unique_keys,
        parse_constant=_reject_constant,
    )
    _require(isinstance(value, dict), "The JSON must contain an object.")
    _canonical(value)  # Also reject overflow such as 1e999 in any nested field.
    return value


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _by_id(items, key):
    _require(isinstance(items, list) and bool(items), f"Missing {key} list.")
    result = {}
    for item in items:
        _require(isinstance(item, dict), f"Invalid {key} entry.")
        identifier = item.get(key)
        _require(_text(identifier) and identifier not in result, f"Missing or duplicate {key}.")
        result[identifier] = item
    return result


def _validate_cell(cell, value, pages):
    _require(isinstance(cell, dict), "Missing source cell.")
    _require(
        _text(value) and _text(cell.get("raw_text"))
        and value == " ".join(cell["raw_text"].split()),
        "A field differs from its whitespace-normalized source cell.",
    )
    _require(
        type(cell.get("pdf_page")) is int and cell["pdf_page"] in pages
        and type(cell.get("printed_page")) is int and cell["printed_page"] > 0,
        "Source-cell pages do not match the record.",
    )
    bbox = cell.get("bbox")
    _require(
        isinstance(bbox, list) and len(bbox) == 4
        and all(type(n) in (int, float) and math.isfinite(n) for n in bbox)
        and 0 <= bbox[0] < bbox[2] and 0 <= bbox[1] < bbox[3],
        "Invalid source-cell coordinates.",
    )


def build_abb_evidence_index(prepared_bytes, prepared_filename):
    """Bind exact field spans to the supplied prepared JSON bytes.

    These are consistency checks against the prepared source. PDF extraction
    and vector-store integrity remain the responsibilities of their services.
    """
    _filename(prepared_filename)
    document = _decode(prepared_bytes)
    preparation, usage = document.get("preparation"), document.get("usage")
    _require(
        document.get("manufacturer") == "ABB"
        and isinstance(preparation, dict)
        and preparation.get("strategy") == "abb_complete_records_v1"
        and preparation.get("one_complete_record_per_chunk") is True,
        "Expected an ABB complete-record prepared document.",
    )
    _require(
        isinstance(usage, dict)
        and usage.get("condition_annotation_status") == "not_reviewed"
        and usage.get("machine_applicability") == "not_assessed"
        and usage.get("approved_for_automatic_execution") is False,
        "Expected the existing unreviewed ABB usage metadata.",
    )
    identity_fields = (
        "document_id", "source_filename", "source_sha256", "manufacturer",
        "document_reference", "revision", "printed_revision_date",
    )
    _require(all(_text(document.get(k)) for k in identity_fields), "Missing document identity.")
    fingerprint = document["source_sha256"]
    _require(
        len(fingerprint) == 64 and all(c in "0123456789abcdef" for c in fingerprint),
        "Invalid stored PDF fingerprint.",
    )
    records = _by_id(document.get("records"), "record_id")
    parents = _by_id(document.get("parents"), "parent_id")
    chunks = _by_id(document.get("chunks"), "parent_id")
    groups = _by_id(document.get("symptom_groups"), "symptom_id")
    contexts = _by_id(document.get("contexts"), "context_id")
    _require(set(records) == set(parents) == set(chunks), "Record, parent or chunk links differ.")
    for count, expected in (
        ("total_records", len(records)), ("total_sections", len(parents)),
        ("total_chunks", len(chunks)), ("total_symptom_groups", len(groups)),
    ):
        _require(type(document.get(count)) is int and document[count] == expected, f"Invalid {count}.")
    _require(all(_text(c.get("text_layout")) for c in contexts.values()), "Missing source context text.")

    linked_ids = []
    for group in groups.values():
        ids = group.get("record_ids")
        _require(isinstance(ids, list) and bool(ids), "Missing symptom-group record links.")
        for record_id in ids:
            _require(isinstance(record_id, str) and record_id in records, "Unknown group record ID.")
            record = records[record_id]
            _require(
                record.get("symptom_id") == group["symptom_id"]
                and record.get("symptom") == group.get("symptom"),
                "Symptom grouping differs from the records.",
            )
        linked_ids.extend(ids)
    _require(
        len(linked_ids) == len(records) and set(linked_ids) == set(records),
        "Missing, duplicated or ungrouped records.",
    )

    entries = []
    for record_id, record in records.items():
        parent, chunk = parents[record_id], chunks[record_id]
        _require(
            all(_canonical(parent.get(k)) == _canonical(v) for k, v in record.items()),
            f"Prepared parent differs from source record: {record_id}",
        )
        _require(
            all(parent.get(k) == document[k] for k in identity_fields if k != "source_sha256")
            and _canonical(parent.get("usage")) == _canonical(usage),
            f"Parent document identity or usage differs: {record_id}",
        )
        pages, context_ids = record.get("page_numbers"), record.get("context_ids")
        _require(
            isinstance(pages, list) and bool(pages)
            and all(type(p) is int and p > 0 for p in pages),
            "Invalid record pages.",
        )
        _require(
            isinstance(context_ids, list) and bool(context_ids)
            and all(isinstance(cid, str) and cid in contexts for cid in context_ids)
            and len(context_ids) == len(set(context_ids)),
            "Missing or duplicated source-context links.",
        )
        _require(isinstance(record.get("source_cells"), dict), "Missing source cells.")
        text = (
            f"Source: ABB low voltage motors manual, {document['document_reference']}, "
            f"Rev {document['revision']} ({document['printed_revision_date']}).\n"
        )
        spans = []
        for field, label, cell_name in FIELDS:
            value, cell = record.get(field), record["source_cells"].get(cell_name)
            _validate_cell(cell, value, pages)
            text += f"{label}: "
            start = len(text)
            text += value
            spans.append({
                "evidence_id": f"{record_id}:{field}", "field": field,
                "quote": value, "start": start, "end": len(text),
                "source_cell": deepcopy(cell),
            })
            if field != "manufacturer_guidance":
                text += "\n"
        _require(
            parent.get("text") == text and chunk.get("text") == text
            and chunk.get("record_id") == record_id
            and chunk.get("symptom_id") == record["symptom_id"]
            and chunk.get("page_numbers") == pages
            and chunk.get("context_ids") == context_ids,
            f"Prepared text or chunk links changed: {record_id}",
        )
        entries.append({
            "record_id": record_id, "parent_id": record_id,
            "symptom_id": record["symptom_id"],
            "row_number_on_page": record.get("row_number_on_page"),
            "symptom_inherited": record.get("symptom_inherited"),
            "parent_text_sha256": _sha256(text.encode("utf-8")),
            "page_numbers": list(pages), "page_numbers_scope": "source_record",
            "context_ids": list(context_ids), "spans": spans,
            "condition_annotation_status": "not_reviewed",
            "condition_annotations": [],
        })

    return {
        "schema_version": 1, "strategy": STRATEGY, "status": "draft",
        "source": {
            **{k: document[k] for k in identity_fields},
            "prepared_filename": prepared_filename,
            "prepared_sha256": _sha256(prepared_bytes),
        },
        "span_coordinates": "Python Unicode code points; 0-based; end-exclusive; prepared parent text",
        "source_cell_coordinates": "PDF points [x0, top, x1, bottom]; origin top-left",
        "quote_normalization": "whitespace_only; raw PDF cell text retained separately",
        "source_verification_scope": "consistency_with_prepared_json; PDF not re-extracted",
        "usage": deepcopy(usage),
        "total_records": len(entries), "total_spans": len(entries) * len(FIELDS),
        "total_symptom_groups": len(groups), "reviewed_condition_count": 0,
        "symptom_groups": deepcopy(document["symptom_groups"]),
        "contexts": deepcopy(document["contexts"]), "entries": entries,
    }


def create_abb_evidence_index(prepared_filename):
    """Write one new draft sidecar. Existing output is never overwritten."""
    source = _input_path(PREPARED_DIRECTORY, prepared_filename)
    output = OUTPUT_DIRECTORY / f"{Path(prepared_filename).stem}_evidence_v1.json"
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Evidence index already exists: {output.name}")
    original = source.read_bytes()
    index = build_abb_evidence_index(original, prepared_filename)
    payload = json.dumps(index, ensure_ascii=False, indent=2, allow_nan=False)
    _require(source.read_bytes() == original, "Prepared source changed; no index saved.")
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    handle = output.open("x", encoding="utf-8", newline="\n")
    try:
        with handle:
            handle.write(payload)
        _require(source.read_bytes() == original, "Prepared source changed while saving.")
    except BaseException:
        output.unlink(missing_ok=True)  # Only the new file created by this call.
        raise
    return {
        "index_filename": output.name, "saved_location": str(output),
        "strategy": STRATEGY, "status": index["status"],
        "total_records": index["total_records"], "total_spans": index["total_spans"],
        "reviewed_condition_count": 0,
    }


def load_abb_evidence_index(index_filename):
    """Read and validate a v1 draft against its current prepared source.

    V1 permits only unreviewed, empty condition annotations. A reviewed schema
    and a condition-verification policy are subsequent, separate steps.
    """
    path = _input_path(OUTPUT_DIRECTORY, index_filename)
    index = _decode(path.read_bytes())
    reference = index.get("source")
    _require(isinstance(reference, dict), "Missing evidence source reference.")
    prepared_filename = reference.get("prepared_filename")
    source = _input_path(PREPARED_DIRECTORY, prepared_filename)
    original = source.read_bytes()
    _require(
        _sha256(original) == reference.get("prepared_sha256"),
        "Prepared source fingerprint changed. Keep both files and review the difference.",
    )
    expected = build_abb_evidence_index(original, prepared_filename)
    _require(
        _canonical(index) == _canonical(expected),
        "Evidence index differs from its source or supported draft schema.",
    )
    _require(source.read_bytes() == original, "Prepared source changed during validation.")
    return index
