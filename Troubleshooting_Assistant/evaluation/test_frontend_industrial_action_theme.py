from __future__ import annotations

import unittest

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


class FrontendIndustrialActionThemeTests(
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


    def test_industrial_action_theme_is_present(
        self,
    ):

        self.assertIn(
            'id="industrialActionTheme"',
            self.text,
        )

        for marker in (
            "--action-blue",
            "--action-green",
            "--action-amber",
            "--action-purple",
            "--action-teal",
            "--action-red",
        ):

            self.assertIn(
                marker,
                self.text,
            )


    def test_primary_actions_have_distinct_styles(
        self,
    ):

        for selector in (
            "#technicianViewBtn",
            "#engineerViewBtn",
            "#guidedTab",
            "#searchTab",
            '#searchForm button[type="submit"]',
            ".source-page-button-group button",
            "#reset",
            ".source-page-close",
        ):

            self.assertIn(
                selector,
                self.text,
            )


    def test_existing_source_page_feature_is_preserved(
        self,
    ):

        self.assertIn(
            "View Source Page",
            self.text,
        )

        self.assertIn(
            "/assistant/source-page/",
            self.text,
        )

        self.assertIn(
            'id="sourcePagePreviewScript"',
            self.text,
        )


    def test_accessibility_behaviour_is_present(
        self,
    ):

        self.assertIn(
            "button:focus-visible",
            self.text,
        )

        self.assertIn(
            "prefers-reduced-motion",
            self.text,
        )

        self.assertIn(
            "button:disabled",
            self.text,
        )


    def test_production_ui_serves_industrial_theme(
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
            "industrialActionTheme",
            response.text,
        )

        self.assertIn(
            "--action-amber",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
