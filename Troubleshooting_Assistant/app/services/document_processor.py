import json
from pathlib import Path

from fastapi import HTTPException
from pypdf import PdfReader
import hashlib
from app.services.document_service import (
    ENTERPRISE_METADATA_FIELDS,
    REGISTRY_SCHEMA_VERSION,
)
from app.services.registry_backend import get_enterprise_document


RAW_DIRECTORY = Path("data/raw_documents")
PROCESSED_DIRECTORY = Path("data/processed_documents")


def clean_extracted_text(text: str) -> str:
    """
    Remove unnecessary empty lines and spaces from extracted PDF text.
    """

    cleaned_lines = []

    for line in text.splitlines():
        cleaned_line = line.strip()

        if cleaned_line:
            cleaned_lines.append(cleaned_line)

    return "\n".join(cleaned_lines)



# === ENTERPRISE METADATA PROPAGATION V1 ===

def _sha256_file(path: Path) -> str:
    """
    Calculate a streaming SHA-256 for source-integrity validation.
    """
    hasher = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)

            if not block:
                break

            hasher.update(block)

    return hasher.hexdigest()


def _enterprise_metadata_snapshot(
    document_id: str,
    stored_filename: str,
    raw_path: Path,
    *,
    database_path: Path | None = None,
) -> dict | None:
    """
    Bind a raw source file to its enterprise registry metadata.

    Legacy documents that have never been registered remain supported
    and return None.

    If a registry record exists, the stored filename and SHA-256 must
    still match the raw source before that metadata is trusted.
    """
    lookup_arguments = {}

    if database_path is not None:
        lookup_arguments["database_path"] = database_path

    record = get_enterprise_document(
        document_id,
        **lookup_arguments,
    )

    if record is None:
        return None

    if record.get("stored_filename") != stored_filename:
        raise ValueError(
            "Enterprise registry stored_filename does not "
            "match the raw document being processed."
        )

    expected_sha256 = record.get("source_sha256")

    if not isinstance(expected_sha256, str):
        raise ValueError(
            "Enterprise registry source_sha256 is missing."
        )

    actual_sha256 = _sha256_file(raw_path)

    if actual_sha256 != expected_sha256:
        raise ValueError(
            "Raw document SHA-256 differs from its registered "
            "source fingerprint."
        )

    snapshot = {
        "registry_schema_version": REGISTRY_SCHEMA_VERSION,
        "document_id": record["document_id"],
        "source_sha256": expected_sha256,
        "ingested_at_utc": record.get(
            "ingested_at_utc"
        ),
        "metadata_updated_at_utc": record.get(
            "metadata_updated_at_utc"
        ),
    }

    for field in ENTERPRISE_METADATA_FIELDS:
        snapshot[field] = record.get(field)

    return snapshot


def process_pdf_document(stored_filename: str) -> dict:
    """
    Extract text page by page from a stored PDF and save it as JSON.
    """

    safe_filename = Path(stored_filename).name

    if stored_filename != safe_filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid document filename."
        )

    if Path(safe_filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF processing is supported at this stage."
        )

    pdf_path = RAW_DIRECTORY / safe_filename

    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="The requested PDF was not found in raw_documents."
        )

    PROCESSED_DIRECTORY.mkdir(parents=True, exist_ok=True)

    try:
        pdf_reader = PdfReader(str(pdf_path))

        extracted_pages = []
        total_characters = 0

        for page_index, page in enumerate(pdf_reader.pages, start=1):
            page_text = page.extract_text() or ""
            cleaned_text = clean_extracted_text(page_text)

            if cleaned_text:
                extracted_pages.append(
                    {
                        "page_number": page_index,
                        "text": cleaned_text
                    }
                )

                total_characters += len(cleaned_text)

        if not extracted_pages:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No searchable text could be extracted. "
                    "The PDF may contain scanned images."
                )
            )

        document_id = pdf_path.stem
        enterprise_metadata = _enterprise_metadata_snapshot(
            document_id,
            safe_filename,
            pdf_path,
        )
        output_filename = f"{document_id}.json"
        output_path = PROCESSED_DIRECTORY / output_filename

        processed_document = {
            "document_id": document_id,
            "source_filename": safe_filename,
            "enterprise_metadata": enterprise_metadata,
            "file_type": ".pdf",
            "total_pdf_pages": len(pdf_reader.pages),
            "pages_with_text": len(extracted_pages),
            "total_characters": total_characters,
            "pages": extracted_pages
        }

        with output_path.open(
            mode="w",
            encoding="utf-8"
        ) as output_file:
            json.dump(
                processed_document,
                output_file,
                ensure_ascii=False,
                indent=2
            )

        return {
            "document_id": document_id,
            "source_filename": safe_filename,
            "processed_filename": output_filename,
            "total_pdf_pages": len(pdf_reader.pages),
            "pages_with_text": len(extracted_pages),
            "total_characters": total_characters,
            "saved_location": str(output_path)
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(error)}"
        ) from error