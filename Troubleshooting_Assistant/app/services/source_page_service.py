from __future__ import annotations

import hashlib

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from app.services.registry_backend import (
    get_enterprise_document,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

RAW_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "raw_documents"
)


@dataclass(frozen=True)
class SourcePagePreview:
    content: bytes
    page_number: int
    total_pages: int


def _clean_document_id(
    document_id: str,
) -> str:

    if not isinstance(
        document_id,
        str,
    ):
        raise ValueError(
            "document_id must be a non-empty string."
        )

    document_id = document_id.strip()

    if not document_id:
        raise ValueError(
            "document_id must be a non-empty string."
        )

    if len(document_id) > 255:
        raise ValueError(
            "document_id is too long."
        )

    return document_id


def _clean_page_number(
    page_number: int,
) -> int:

    if (
        type(page_number) is not int
        or page_number < 1
    ):
        raise ValueError(
            "page_number must be a positive 1-based integer."
        )

    return page_number


def _registered_source_path(
    document: dict,
) -> Path:

    stored_filename = document.get(
        "stored_filename"
    )

    if (
        not isinstance(
            stored_filename,
            str,
        )
        or not stored_filename.strip()
    ):
        raise PermissionError(
            "Registered document has no valid stored filename."
        )

    stored_filename = stored_filename.strip()

    candidate_name = Path(
        stored_filename
    )

    if (
        candidate_name.name
        != stored_filename
        or candidate_name.suffix.lower()
        != ".pdf"
    ):
        raise PermissionError(
            "Registered source filename is not an eligible PDF filename."
        )

    raw_root = RAW_DIRECTORY.resolve()

    source_path = (
        raw_root
        / stored_filename
    ).resolve()

    if source_path.parent != raw_root:
        raise PermissionError(
            "Registered source resolved outside raw_documents."
        )

    if not source_path.is_file():
        raise FileNotFoundError(
            "Registered source PDF was not found."
        )

    return source_path


def _sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as source:

        while True:

            block = source.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def _verify_registered_source(
    document: dict,
    source_path: Path,
) -> None:

    expected_sha256 = document.get(
        "source_sha256"
    )

    if (
        not isinstance(
            expected_sha256,
            str,
        )
        or len(
            expected_sha256.strip()
        ) != 64
    ):
        raise PermissionError(
            "Registered source SHA-256 is unavailable or invalid."
        )

    expected_sha256 = (
        expected_sha256
        .strip()
        .lower()
    )

    actual_sha256 = _sha256_file(
        source_path
    )

    if actual_sha256 != expected_sha256:
        raise PermissionError(
            "Registered source PDF failed SHA-256 verification."
        )


def build_registered_source_page(
    document_id: str,
    page_number: int,
) -> SourcePagePreview:

    """
    Return one exact source-PDF page from a trusted registered document.

    Security/provenance rules:
    - caller supplies document_id, never a filesystem path;
    - document must exist in the active enterprise registry;
    - stored filename comes only from the registry;
    - source must remain inside data/raw_documents;
    - source SHA-256 must match the registered value;
    - page numbering is 1-based;
    - no document/vector preference is inferred;
    - no diagnosis or automatic action is performed.
    """

    document_id = _clean_document_id(
        document_id
    )

    page_number = _clean_page_number(
        page_number
    )

    document = get_enterprise_document(
        document_id
    )

    if document is None:
        raise FileNotFoundError(
            "The requested registered document was not found."
        )

    if not isinstance(
        document,
        dict,
    ):
        raise RuntimeError(
            "Enterprise registry returned an invalid document record."
        )

    registered_id = document.get(
        "document_id"
    )

    if registered_id != document_id:
        raise PermissionError(
            "Registry document identity did not match the request."
        )

    source_path = _registered_source_path(
        document
    )

    _verify_registered_source(
        document,
        source_path,
    )

    reader = PdfReader(
        str(source_path)
    )

    total_pages = len(
        reader.pages
    )

    if (
        page_number
        > total_pages
    ):
        raise ValueError(
            "Requested page is outside the source PDF page range."
        )

    writer = PdfWriter()

    writer.add_page(
        reader.pages[
            page_number - 1
        ]
    )

    output = BytesIO()

    writer.write(
        output
    )

    content = output.getvalue()

    if not content.startswith(
        b"%PDF"
    ):
        raise RuntimeError(
            "Source page extraction did not produce a PDF."
        )

    return SourcePagePreview(
        content=content,
        page_number=page_number,
        total_pages=total_pages,
    )
