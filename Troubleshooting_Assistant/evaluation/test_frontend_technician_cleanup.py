from __future__ import annotations

import unittest

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


class FrontendTechnicianCleanupTests(
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


    def test_manufacturer_specific_fields_are_synchronized(
        self,
    ):

        self.assertIn(
            "function syncManufacturerSpecificFields()",
            self.text,
        )

        self.assertIn(
            "$('alarmLabel').hidden=!isSiemens",
            self.text,
        )

        self.assertIn(
            "$('manufacturer').onchange=",
            self.text,
        )

        self.assertIn(
            "syncManufacturerSpecificFields();",
            self.text,
        )


    def test_raw_source_response_is_engineering_only(
        self,
    ):

        self.assertIn(
            ".engineer-only-detail",
            self.text,
        )

        self.assertIn(
            "body.engineer-mode .engineer-only-detail",
            self.text,
        )

        self.assertIn(
            "d.classList.add('engineer-only-detail')",
            self.text,
        )

        self.assertIn(
            "Full source response",
            self.text,
        )


    def test_internal_source_filename_is_engineering_only(
        self,
    ):

        self.assertIn(
            "'muted engineer-only-detail'",
            self.text,
        )


    def test_source_page_preview_is_preserved(
        self,
    ):

        self.assertIn(
            'id="sourcePagePreviewScript"',
            self.text,
        )

        self.assertIn(
            "View Source Page",
            self.text,
        )

        self.assertIn(
            "/assistant/source-page/",
            self.text,
        )


    def test_production_ui_serves_cleanup(
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
            "syncManufacturerSpecificFields",
            response.text,
        )

        self.assertIn(
            "engineer-only-detail",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
