from __future__ import annotations

import unittest

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


class FrontendOperatorWorkflowTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):

        cls.path = (
            Path(__file__)
            .resolve()
            .parents[1]
            / "app"
            / "static"
            / "assistant_v2.html"
        )


        cls.text = cls.path.read_text(
            encoding="utf-8-sig"
        )


    def test_operator_search_states_present(
        self,
    ):

        for value in (
            "Searching evidence",
            "Evidence found",
            "No evidence found",
            "Search unavailable",
        ):

            self.assertIn(
                value,
                self.text,
            )


    def test_guided_handoff_does_not_infer_state(
        self,
    ):

        start = self.text.index(
            "function appendGuidedReviewHandoff"
        )

        end = self.text.index(
            "function enterpriseSearchResult",
            start,
        )

        block = self.text[
            start:end
        ]


        self.assertIn(
            "Continue with Guided Review",
            block,
        )


        self.assertIn(
            "Search text is not automatically treated as a machine fact",
            block,
        )


        for forbidden in (
            "$('mode').value=",
            "data-fact",
            "requested_information",
            "alarm_scope",
            "open_phase_reported",
            "reported_alarm_number",
        ):

            self.assertNotIn(
                forbidden,
                block,
            )


    def test_error_state_does_not_claim_success(
        self,
    ):

        start = self.text.index(
            "async function enterpriseSearchCall"
        )

        end = self.text.index(
            "$('searchForm').onsubmit=",
            start,
        )

        block = self.text[
            start:end
        ]


        self.assertIn(
            "'error'",
            block,
        )

        self.assertIn(
            "Search unavailable",
            block,
        )

        self.assertIn(
            "No troubleshooting conclusion was generated.",
            block,
        )


    def test_production_assistant_serves_polished_workspace(
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
            "Continue with Guided Review",
            page,
        )

        self.assertIn(
            "enterprise_evidence",
            page,
        )

        self.assertIn(
            "No evidence found",
            page,
        )

        self.assertIn(
            "Search unavailable",
            page,
        )


if __name__ == "__main__":
    unittest.main()
