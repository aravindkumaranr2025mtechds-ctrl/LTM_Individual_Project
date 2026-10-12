"""Extract the reviewed ABB Rev H PDF; do not generate diagnoses or vectors."""

import hashlib
import io
import json
from pathlib import Path

import pdfplumber


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIRECTORY = PROJECT_ROOT / "data" / "raw_documents"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "structured_documents"
STRATEGY = "abb_lv_motor_tables_v1"
EXPECTED_PDF_SHA256 = (
    "90dca734e4b5699ff37901e18cdb90275e77"
    "ded8b355359130c493820d2fa913"
)
EXPECTED_PDF_BYTES = 4669415
EXPECTED_GROUPS = {
    25: [
        ("Motor fails to start", 9),
        ("Motor stalls", 5),
        ("Motor runs and then dies down", 1),
        ("Motor does not accelerate up to nominal speed", 5),
    ],
    26: [
        ("Motor takes too long to accelerate and/or draws high current", 4),
        ("Wrong rotation direction", 1),
        ("Motor overheats while running", 5),
        ("Motor vibrates", 10),
        ("Scraping noise", 2),
        ("Noisy operation", 2),
        ("Hot bearings", 10),
    ],
}


def _normalize(text):
    """Normalize whitespace only; retain source wording and punctuation."""
    return " ".join((text or "").split())


def _validate_filename(filename):
    if (
        not isinstance(filename, str)
        or not filename
        or filename != filename.strip()
        or any(c in filename for c in '/\\:')
        or any(ord(c) < 32 for c in filename)
        or Path(filename).suffix.lower() != ".pdf"
    ):
        raise ValueError("Provide only the stored PDF filename, not a path.")


def _source_cell(raw_text, bbox, page_number):
    if not _normalize(raw_text) or bbox is None:
        raise ValueError(f"Missing source text or cell on page {page_number}.")
    return {
        "pdf_page": page_number,
        "printed_page": page_number,
        "bbox": list(bbox),
        "raw_text": raw_text,
    }


def _find_table(page, page_number):
    """Use header positions and ruling lines, not guessed text separators."""
    words = page.extract_words()
    headers = []
    for label in ("TROUBLE", "CAUSE", "WHAT"):
        matches = [word for word in words if word["text"] == label]
        if len(matches) != 1:
            raise ValueError(f"Unexpected table header on page {page_number}.")
        headers.append(matches[0])
    if max(w["top"] for w in headers) - min(w["top"] for w in headers) > 2:
        raise ValueError(f"Misaligned table header on page {page_number}.")

    xs = [word["x0"] for word in headers]
    edges = [
        edge for edge in page.edges
        if edge.get("orientation") == "h"
        and edge["top"] > headers[0]["top"] - 10
        and edge["x1"] - edge["x0"] > 50
    ]
    if not edges:
        raise ValueError(f"Missing table boundaries on page {page_number}.")
    right = max(edge["x1"] for edge in edges)
    top = min(edge["top"] for edge in edges)
    bottom = max(edge["top"] for edge in edges)
    if not 0 <= xs[0] < xs[1] < xs[2] < right <= page.width:
        raise ValueError(f"Invalid table columns on page {page_number}.")

    cropped = page.crop((xs[0] - 1, top - 1, right + 1, bottom + 1))
    tables = cropped.find_tables({
        "vertical_strategy": "explicit",
        "explicit_vertical_lines": [*xs, right],
        "horizontal_strategy": "lines",
        "snap_tolerance": 2,
        "intersection_tolerance": 3,
    })
    if len(tables) != 1:
        raise ValueError(f"Expected exactly one table on page {page_number}.")
    table = tables[0]
    rows = table.extract(x_tolerance=3, y_tolerance=3)
    expected_rows = sum(count for _, count in EXPECTED_GROUPS[page_number])
    if (
        not rows
        or [_normalize(cell) for cell in rows[0]] != ["TROUBLE", "CAUSE", "WHAT TO DO"]
        or len(rows) != expected_rows + 1
        or len(table.rows) != len(rows)
        or any(len(row) != 3 for row in rows)
    ):
        raise ValueError(f"Table structure changed on page {page_number}.")
    return table, rows


def build_abb_document(pdf_bytes, stored_filename):
    """Build an auditable JSON object without reading or writing project data."""
    _validate_filename(stored_filename)
    if (
        len(pdf_bytes) != EXPECTED_PDF_BYTES
        or hashlib.sha256(pdf_bytes).hexdigest() != EXPECTED_PDF_SHA256
    ):
        raise ValueError(
            "This is not the exact ABB PDF reviewed for this extractor. "
            "Stop and review the source; do not change the fingerprint to bypass this check."
        )
    if pdfplumber.__version__ != "0.11.8":
        raise RuntimeError("This extractor requires the tested pdfplumber==0.11.8.")

    document_id = Path(stored_filename).stem
    groups, records, contexts = [], [], []
    context_ids = [f"{document_id}_context_p{n:03d}" for n in (5, 6, 9, 25)]
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if len(pdf.pages) != 32:
            raise ValueError("Expected 32 PDF pages.")
        edition = "".join((pdf.pages[4].extract_text() or "").split())
        if "3GZF500730-85REVHEN06-2022" not in edition:
            raise ValueError("The printed document reference or revision does not match.")

        table_top = None
        for page_number in (25, 26):
            page = pdf.pages[page_number - 1]
            table, rows = _find_table(page, page_number)
            if page_number == 25:
                table_top = table.bbox[1]
            page_groups = []
            current = None
            for row_number, row in enumerate(rows[1:], start=1):
                boxes = table.rows[row_number].cells
                symptom_raw, cause_raw, remedy_raw = row
                if _normalize(symptom_raw):
                    current = {
                        "symptom_id": f"{document_id}_s{len(groups) + 1:03d}",
                        "symptom": _normalize(symptom_raw),
                        "source_cell": _source_cell(symptom_raw, boxes[0], page_number),
                        "record_ids": [],
                    }
                    groups.append(current)
                    page_groups.append(current)
                elif boxes[0] is not None:
                    raise ValueError("An empty symptom cell is not a verified merged cell.")
                if current is None:
                    raise ValueError("A table row has no preceding symptom.")

                symptom_cell = current["source_cell"]
                cause_cell = _source_cell(cause_raw, boxes[1], page_number)
                remedy_cell = _source_cell(remedy_raw, boxes[2], page_number)
                bounds = symptom_cell["bbox"]
                if any(
                    box[1] < bounds[1] - 0.01 or box[3] > bounds[3] + 0.01
                    for box in (boxes[1], boxes[2])
                ):
                    raise ValueError("A cause/remedy row lies outside its symptom group.")
                record_id = f"{document_id}_r{len(records) + 1:03d}"
                current["record_ids"].append(record_id)
                records.append({
                    "record_id": record_id,
                    "symptom_id": current["symptom_id"],
                    "symptom": current["symptom"],
                    "possible_cause": _normalize(cause_raw),
                    "manufacturer_guidance": _normalize(remedy_raw),
                    "page_numbers": [page_number],
                    "row_number_on_page": row_number,
                    "symptom_inherited": not bool(_normalize(symptom_raw)),
                    "source_cells": {
                        "symptom": _source_cell(
                            symptom_cell["raw_text"], bounds, page_number
                        ),
                        "cause": cause_cell,
                        "remedy": remedy_cell,
                    },
                    "context_ids": list(context_ids),
                })
            observed = [(g["symptom"], len(g["record_ids"])) for g in page_groups]
            if observed != EXPECTED_GROUPS[page_number]:
                raise ValueError(f"Symptom grouping changed on page {page_number}.")

        # Retain selected original context, not invented applicability/safety rules.
        for page_number, purpose in (
            (5, "Document scope, section 1.2, and special-application limitations"),
            (6, "General safety considerations"),
            (9, "Installation context including isolation/lockout warning"),
            (25, "Troubleshooting preamble and qualified-personnel requirement"),
        ):
            page = pdf.pages[page_number - 1]
            bbox = (0, 0, page.width, table_top if page_number == 25 else page.height)
            text = page.crop(bbox).extract_text(layout=True) or ""
            if not text.strip():
                raise ValueError(f"Missing source context on page {page_number}.")
            contexts.append({
                "context_id": f"{document_id}_context_p{page_number:03d}",
                "purpose": purpose,
                "pdf_page": page_number,
                "printed_page": page_number,
                "bbox": list(bbox),
                "text_layout": text,
            })

    return {
        "schema_version": 1,
        "strategy": STRATEGY,
        "document_id": document_id,
        "source_filename": stored_filename,
        "source_sha256": EXPECTED_PDF_SHA256,
        "source_size_bytes": len(pdf_bytes),
        "manufacturer": "ABB",
        "document_reference": "3GZF500730-85",
        "revision": "H",
        "language": "en",
        "printed_revision_date": "06-2022",
        "total_pdf_pages": 32,
        "table_pages": [25, 26],
        "total_symptom_groups": len(groups),
        "total_records": len(records),
        "extraction": {
            "pdfplumber_version": pdfplumber.__version__,
            "extractor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "text_normalization": "whitespace_only; original cell text retained",
            "bbox_coordinates": "PDF points [x0, top, x1, bottom]; origin top-left",
            "cell_text_membership": "character centres; left/top inclusive, right/bottom exclusive",
            "page_numbering": "1-based PDF pages; matching printed pages verified for this source",
        },
        "usage": {
            "record_type": "manufacturer_possible_cause_and_guidance",
            "condition_annotation_status": "not_reviewed",
            "machine_applicability": "not_assessed",
            "approved_for_automatic_execution": False,
            "note": (
                "These are source records, not confirmed diagnoses or successful repair cases. "
                "Selected context is not a complete safety assessment. Consult the full manual "
                "and any required supplementary instructions with qualified personnel."
            ),
        },
        "contexts": contexts,
        "symptom_groups": groups,
        "records": records,
    }


def extract_abb_document(stored_filename):
    """Read raw_documents and create a new JSON; never overwrite existing data."""
    _validate_filename(stored_filename)
    source = (RAW_DIRECTORY / stored_filename).resolve()
    if source.parent != RAW_DIRECTORY.resolve():
        raise ValueError("The PDF must be inside raw_documents.")
    if not source.is_file():
        raise FileNotFoundError("ABB PDF not found in raw_documents.")
    if source.stat().st_size != EXPECTED_PDF_BYTES:
        raise ValueError("Unexpected PDF size; this extractor requires the reviewed ABB PDF.")
    output = OUTPUT_DIRECTORY / f"{Path(stored_filename).stem}_structured_v1.json"
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Structured output already exists: {output.name}")

    document = build_abb_document(source.read_bytes(), stored_filename)
    payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
    if hashlib.sha256(source.read_bytes()).hexdigest() != document["source_sha256"]:
        raise ValueError("The source PDF changed during extraction. No output was saved.")
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    handle = output.open("x", encoding="utf-8", newline="\n")
    try:
        with handle:
            handle.write(payload)
    except BaseException:
        output.unlink(missing_ok=True)  # Only the incomplete file created by this call.
        raise

    return {
        "document_id": document["document_id"],
        "source_filename": stored_filename,
        "source_sha256": document["source_sha256"],
        "strategy": STRATEGY,
        "total_pdf_pages": document["total_pdf_pages"],
        "table_pages": document["table_pages"],
        "total_symptom_groups": document["total_symptom_groups"],
        "total_records": document["total_records"],
        "structured_filename": output.name,
        "saved_location": str(output),
    }