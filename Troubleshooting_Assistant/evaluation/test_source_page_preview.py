from __future__ import annotations

import hashlib
import tempfile
import unittest

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from app.main import app
from app.services import source_page_service
from app.services.source_page_service import (
    SourcePagePreview,
    build_registered_source_page,
)


class SourcePagePreviewTests(
    unittest.TestCase
):

    def _make_pdf(
        self,
        directory: Path,
        *,
        pages: int = 2,
    ) -> tuple[Path, str]:

        path = (
            directory
            / "registered_test_manual.pdf"
        )

        writer = PdfWriter()

        for _ in range(
            pages
        ):
            writer.add_blank_page(
                width=612,
                height=792,
            )

        with path.open(
            "wb"
        ) as output:
            writer.write(
                output
            )

        digest = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

        return path, digest


    def test_registered_page_is_extracted_as_one_page_pdf(
        self,
    ):

        with tempfile.TemporaryDirectory() as temporary:

            root = Path(
                temporary
            )

            source, digest = self._make_pdf(
                root,
                pages=2,
            )

            document = {
                "document_id":
                    "test_document",
                "stored_filename":
                    source.name,
                "source_sha256":
                    digest,
            }

            with (
                patch.object(
                    source_page_service,
                    "RAW_DIRECTORY",
                    root,
                ),
                patch.object(
                    source_page_service,
                    "get_enterprise_document",
                    return_value=document,
                ),
            ):

                preview = (
                    build_registered_source_page(
                        "test_document",
                        2,
                    )
                )

        self.assertEqual(
            preview.page_number,
            2,
        )

        self.assertEqual(
            preview.total_pages,
            2,
        )

        self.assertTrue(
            preview.content.startswith(
                b"%PDF"
            )
        )

        extracted = PdfReader(
            BytesIO(
                preview.content
            )
        )

        self.assertEqual(
            len(extracted.pages),
            1,
        )


    def test_unregistered_document_is_rejected(
        self,
    ):

        with patch.object(
            source_page_service,
            "get_enterprise_document",
            return_value=None,
        ):

            with self.assertRaises(
                FileNotFoundError
            ):
                build_registered_source_page(
                    "missing_document",
                    1,
                )


    def test_page_zero_is_rejected(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):
            build_registered_source_page(
                "test_document",
                0,
            )


    def test_page_beyond_pdf_range_is_rejected(
        self,
    ):

        with tempfile.TemporaryDirectory() as temporary:

            root = Path(
                temporary
            )

            source, digest = self._make_pdf(
                root,
                pages=1,
            )

            document = {
                "document_id":
                    "test_document",
                "stored_filename":
                    source.name,
                "source_sha256":
                    digest,
            }

            with (
                patch.object(
                    source_page_service,
                    "RAW_DIRECTORY",
                    root,
                ),
                patch.object(
                    source_page_service,
                    "get_enterprise_document",
                    return_value=document,
                ),
            ):

                with self.assertRaises(
                    ValueError
                ):
                    build_registered_source_page(
                        "test_document",
                        2,
                    )


    def test_source_filename_path_traversal_is_rejected(
        self,
    ):

        document = {
            "document_id":
                "test_document",
            "stored_filename":
                "../outside.pdf",
            "source_sha256":
                "0" * 64,
        }

        with patch.object(
            source_page_service,
            "get_enterprise_document",
            return_value=document,
        ):

            with self.assertRaises(
                PermissionError
            ):
                build_registered_source_page(
                    "test_document",
                    1,
                )


    def test_source_sha256_mismatch_is_rejected(
        self,
    ):

        with tempfile.TemporaryDirectory() as temporary:

            root = Path(
                temporary
            )

            source, _ = self._make_pdf(
                root,
                pages=1,
            )

            document = {
                "document_id":
                    "test_document",
                "stored_filename":
                    source.name,
                "source_sha256":
                    "0" * 64,
            }

            with (
                patch.object(
                    source_page_service,
                    "RAW_DIRECTORY",
                    root,
                ),
                patch.object(
                    source_page_service,
                    "get_enterprise_document",
                    return_value=document,
                ),
            ):

                with self.assertRaises(
                    PermissionError
                ):
                    build_registered_source_page(
                        "test_document",
                        1,
                    )


    def test_http_route_returns_inline_pdf(
        self,
    ):

        preview = SourcePagePreview(
            content=(
                b"%PDF-1.4\n"
                b"% test\n"
            ),
            page_number=25,
            total_pages=32,
        )

        with patch(
            "app.services.assistant_workflow."
            "build_registered_source_page",
            return_value=preview,
        ):

            with TestClient(
                app
            ) as client:

                response = client.get(
                    "/assistant/source-page/"
                    "test_document/25"
                )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.headers.get(
                "content-type"
            ),
            "application/pdf",
        )

        self.assertEqual(
            response.headers.get(
                "cache-control"
            ),
            "private, no-store",
        )

        self.assertIn(
            "inline;",
            response.headers.get(
                "content-disposition",
                "",
            ),
        )

        self.assertEqual(
            response.content,
            preview.content,
        )


if __name__ == "__main__":
    unittest.main()
