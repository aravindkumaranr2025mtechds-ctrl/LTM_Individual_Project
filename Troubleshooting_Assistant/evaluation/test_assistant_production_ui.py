from __future__ import annotations

import unittest

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


class AssistantProductionUITests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):

        cls.root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        cls.old_ui = (
            cls.root
            / "app"
            / "static"
            / "assistant.html"
        )

        cls.v2_ui = (
            cls.root
            / "app"
            / "static"
            / "assistant_v2.html"
        )


    def test_production_assistant_serves_v2(
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
            self.v2_ui.read_bytes(),
        )

        self.assertNotEqual(
            response.content,
            self.old_ui.read_bytes(),
        )


    def test_production_ui_contains_enterprise_workspace(
        self,
    ):

        with TestClient(
            app
        ) as client:

            response = client.get(
                "/assistant"
            )


        page = response.text


        self.assertIn(
            "Industrial Troubleshooting Assistant",
            page,
        )

        self.assertIn(
            "Search Technical Evidence",
            page,
        )

        self.assertIn(
            "enterprise_evidence",
            page,
        )

        self.assertIn(
            "/assistant/turn",
            page,
        )


    def test_assistant_turn_is_live(
        self,
    ):

        with TestClient(
            app
        ) as client:

            response = client.post(
                "/assistant/turn",
                json={},
            )


        self.assertEqual(
            response.status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
