from __future__ import annotations

import unittest

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


class WorkspaceModeFrontendTests(
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


    def test_workspace_modes_have_distinct_identity(
        self,
    ):

        for marker in (
            "Technician Workspace",
            "Engineering Console",
            "technician-workspace-context",
            "engineering-workspace-context",
            "#2563eb",
            "#7c3aed",
        ):

            self.assertIn(
                marker,
                self.text,
            )


    def test_mode_switch_is_explicit(
        self,
    ):

        self.assertIn(
            'classList.add(',
            self.text,
        )

        self.assertIn(
            'classList.remove(',
            self.text,
        )

        self.assertIn(
            '"engineer-mode"',
            self.text,
        )

        self.assertIn(
            "dataset.workspaceMode",
            self.text,
        )


    def test_engineering_details_are_mode_specific(
        self,
    ):

        self.assertIn(
            "body:not(.engineer-mode)",
            self.text,
        )

        self.assertIn(
            "body.engineer-mode",
            self.text,
        )

        self.assertIn(
            "#reviewOutput details",
            self.text,
        )

        self.assertIn(
            "#searchOutput details",
            self.text,
        )


    def test_existing_source_preview_is_preserved(
        self,
    ):

        for marker in (
            "/assistant/source-page/",
            "View Source Page",
            "source-page-actions",
            "/assistant/turn",
            "enterprise_evidence",
        ):

            self.assertIn(
                marker,
                self.text,
            )


    def test_production_page_contains_workspace_modes(
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
            "Technician Workspace",
            response.text,
        )

        self.assertIn(
            "Engineering Console",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
