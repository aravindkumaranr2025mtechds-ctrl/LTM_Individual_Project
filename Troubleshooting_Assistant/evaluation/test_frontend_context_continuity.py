from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


class FrontendContextContinuityTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

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


    def test_context_is_from_backend_continuation_answers(
        self,
    ):

        self.assertIn(
            "let currentTechnicalContext=null;",
            self.text,
        )

        self.assertIn(
            "data.continuation_answers",
            self.text,
        )

        self.assertIn(
            "captureEnterpriseTechnicalContext(",
            self.text,
        )


    def test_handoff_reuses_enterprise_mode_and_answers(
        self,
    ):

        self.assertIn(
            "'enterprise_evidence'",
            self.text,
        )

        self.assertIn(
            "preservedAnswers",
            self.text,
        )

        self.assertIn(
            "Continue Guided Review",
            self.text,
        )

        self.assertIn(
            "sendTurn();",
            self.text,
        )


    def test_existing_renderer_and_search_boundaries_remain(
        self,
    ):

        renderer = self.text.index(
            "function enterpriseSearchResult"
        )

        call = self.text.index(
            "async function enterpriseSearchCall",
            renderer,
        )

        form = self.text.index(
            "$('searchForm').onsubmit",
            call,
        )

        self.assertLess(
            renderer,
            call,
        )

        self.assertLess(
            call,
            form,
        )

        renderer_block = self.text[
            renderer:
            call
        ]

        self.assertNotIn(
            "vector_store_filename",
            renderer_block,
        )


    def test_production_route_serves_continuity_ui(
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

        self.assertEqual(
            response.content,
            self.ui.read_bytes(),
        )

        self.assertIn(
            "currentTechnicalContext",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
