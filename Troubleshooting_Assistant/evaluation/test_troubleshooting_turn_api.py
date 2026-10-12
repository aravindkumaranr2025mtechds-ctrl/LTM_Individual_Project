import unittest

from fastapi.testclient import TestClient

from app.main import app


class TroubleshootingTurnAPITests(
    unittest.TestCase
):
    def setUp(self):
        self.client = TestClient(
            app,
            raise_server_exceptions=False,
        )

    def tearDown(self):
        self.client.close()

    def post(self, mode, answers, symptom="Example"):
        return self.client.post(
            "/development/troubleshoot/turn",
            json={
                "machine_name":
                    "Example machine",
                "symptom":
                    symptom,
                "mode":
                    mode,
                "answers":
                    answers,
            },
        )

    def test_abb_returns_next_question(self):
        response = self.post(
            "abb_stall",
            {
                "requested_information":
                    "review_reports",
            },
            "Motor stalls",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["status"],
            "needs_clarification",
        )

        self.assertEqual(
            body["next_question"][
                "fact_id"
            ],
            "open_phase_reported",
        )

    def test_licensing_returns_next_question(self):
        response = self.post(
            "siemens_licensing",
            {
                "options_activated":
                    "yes",
            },
            "Licensing issue",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["status"],
            "needs_clarification",
        )

        self.assertEqual(
            body["next_question"][
                "fact_id"
            ],
            "license_key_set",
        )

    def test_logfile_turn_completes(self):
        response = self.post(
            "siemens_logfile",
            {
                "alarm_scope":
                    "61352_or_61353",
            },
            "Need logfile path",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["status"],
            "turn_complete",
        )

        self.assertEqual(
            body["assistance"][
                "result"
            ][
                "answer"
            ],
            "_PROTNAME[0]",
        )

    def test_invalid_scope_is_422(self):
        response = self.post(
            "siemens_logfile",
            {
                "alarm_scope":
                    "guessed_from_text",
            },
        )

        self.assertEqual(
            response.status_code,
            422,
        )

    def test_no_server_session_created(self):
        response = self.post(
            "siemens_licensing",
            {
                "options_activated":
                    "yes",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            response.json()[
                "server_session_created"
            ]
        )


if __name__ == "__main__":
    unittest.main()
