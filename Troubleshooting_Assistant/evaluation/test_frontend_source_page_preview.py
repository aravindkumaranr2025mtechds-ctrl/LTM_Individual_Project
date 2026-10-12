from __future__ import annotations

import unittest

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


class FrontendSourcePagePreviewTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):

        cls.root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        cls.ui = (
            cls.root
            / "app"
            / "static"
            / "assistant_v2.html"
        )

        cls.text = cls.ui.read_text(
            encoding="utf-8-sig"
        )


    def test_preview_styles_and_script_present(
        self,
    ):

        self.assertIn(
            'id="sourcePagePreviewStyles"',
            self.text,
        )

        self.assertIn(
            'id="sourcePagePreviewScript"',
            self.text,
        )


    def test_preview_uses_trusted_source_page_route(
        self,
    ):

        self.assertIn(
            "/assistant/source-page/",
            self.text,
        )

        self.assertIn(
            "encodeURIComponent",
            self.text,
        )

        self.assertNotIn(
            '"/data/raw_documents/"',
            self.text,
        )


    def test_preview_is_inline_and_technician_friendly(
        self,
    ):

        for marker in (
            "sourcePageDialog",
            "sourcePageFrame",
            "View Source Page",
            "Original source page",
            "Registered source document",
        ):

            self.assertIn(
                marker,
                self.text,
            )


    def test_existing_enterprise_renderer_is_preserved_and_wrapped(
        self,
    ):

        self.assertIn(
            "function enterpriseSearchResult(data){",
            self.text,
        )

        self.assertIn(
            "enterpriseSearchResultBeforeSourcePreview",
            self.text,
        )

        self.assertIn(
            "appendSourcePageActions",
            self.text,
        )

        self.assertIn(
            "technicianEvidencePages",
            self.text,
        )

        self.assertIn(
            "technicianEvidenceTitle",
            self.text,
        )


    def test_production_assistant_serves_source_preview_ui(
        self,
    ):

        with TestClient(
            app
        ) as client:

            response = client.get(
                "/assistant"
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "View Source Page",
            response.text,
        )

        self.assertIn(
            "/assistant/source-page/",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
