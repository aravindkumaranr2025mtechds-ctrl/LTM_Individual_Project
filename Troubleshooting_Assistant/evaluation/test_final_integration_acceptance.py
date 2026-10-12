"""Final integration acceptance tests for the deterministic troubleshooting core.

This suite freezes the validated pre-agentic system before the Agentic AI
orchestration layer is introduced.
"""

import unittest

from fastapi.testclient import TestClient

from app.main import app


class FinalIntegrationAcceptanceTests(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(
            app,
            raise_server_exceptions=False,
        )

    def tearDown(self):
        self.client.close()

    def test_01_required_routes_registered(self):
        schema = self.client.get(
            "/openapi.json"
        )

        self.assertEqual(
            schema.status_code,
            200,
        )

        paths = schema.json()["paths"]

        required = {
            "/troubleshoot",
            "/development/troubleshoot",
            "/development/troubleshoot/guidance",
            "/development/troubleshoot/questions",
            "/development/troubleshoot/build",
            "/development/troubleshoot/turn",
        }

        self.assertTrue(
            required <= set(paths)
        )

    def test_02_free_text_does_not_infer_policy(self):
        response = self.client.post(
            "/troubleshoot",
            json={
                "machine_name":
                    "Siemens machine",
                "error_code":
                    "61352",
                "symptom":
                    "Need logfile path",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["status"],
            "needs_structured_input",
        )

        self.assertFalse(
            body["diagnosis_confirmed"]
        )

        self.assertFalse(
            body[
                "approved_for_automatic_execution"
            ]
        )

    def test_03_guidance_exposes_three_modes(self):
        response = self.client.get(
            "/development/troubleshoot/guidance"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json()[
                "supported_modes"
            ],
            [
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            ],
        )

    def test_04_question_builder_exposes_logfile_scope(self):
        response = self.client.get(
            "/development/troubleshoot/questions",
            params={
                "mode":
                    "siemens_logfile"
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        fields = response.json()[
            "form"
        ][
            "fields"
        ]

        self.assertEqual(
            fields[0]["field_id"],
            "alarm_scope",
        )

        self.assertTrue(
            fields[0]["required"]
        )

    def test_05_build_converts_explicit_logfile_answer(self):
        response = self.client.post(
            "/development/troubleshoot/build",
            json={
                "mode":
                    "siemens_logfile",
                "answers": {
                    "alarm_scope":
                        "61352_or_61353"
                },
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        structured = response.json()[
            "structured_assistance"
        ]

        self.assertEqual(
            structured["mode"],
            "siemens_logfile",
        )

        self.assertEqual(
            structured[
                "payload"
            ][
                "alarm_scope"
            ],
            "61352_or_61353",
        )

    def test_06_invalid_logfile_scope_rejected(self):
        response = self.client.post(
            "/development/troubleshoot/build",
            json={
                "mode":
                    "siemens_logfile",
                "answers": {
                    "alarm_scope":
                        "guessed_from_text"
                },
            },
        )

        self.assertEqual(
            response.status_code,
            422,
        )

    def test_07_logfile_end_to_end_answer(self):
        built = self.client.post(
            "/development/troubleshoot/build",
            json={
                "mode":
                    "siemens_logfile",
                "answers": {
                    "alarm_scope":
                        "61352_or_61353"
                },
            },
        )

        self.assertEqual(
            built.status_code,
            200,
        )

        structured = built.json()[
            "structured_assistance"
        ]

        response = self.client.post(
            "/troubleshoot",
            json={
                "machine_name":
                    "Siemens machine",
                "error_code":
                    "61352",
                "symptom":
                    "Need logfile path",
                "structured_assistance":
                    structured,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["status"],
            "assistance_returned",
        )

        self.assertEqual(
            body[
                "assistance"
            ][
                "selected_policy"
            ],
            "siemens_logfile",
        )

        self.assertEqual(
            body[
                "assistance"
            ][
                "result"
            ][
                "answer"
            ],
            "_PROTNAME[0]",
        )

        self.assertFalse(
            body["diagnosis_confirmed"]
        )

        self.assertFalse(
            body[
                "approved_for_automatic_execution"
            ]
        )

    def test_08_abb_turn_requests_clarification(self):
        response = self.client.post(
            "/development/troubleshoot/turn",
            json={
                "machine_name":
                    "ABB motor",
                "symptom":
                    "Motor stalls",
                "mode":
                    "abb_stall",
                "answers": {
                    "requested_information":
                        "review_reports"
                },
            },
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
            body[
                "next_question"
            ][
                "fact_id"
            ],
            "open_phase_reported",
        )

        self.assertFalse(
            body["server_session_created"]
        )

    def test_09_siemens_licensing_requests_missing_fact(self):
        response = self.client.post(
            "/development/troubleshoot/turn",
            json={
                "machine_name":
                    "Siemens machine",
                "symptom":
                    "Licensing issue",
                "mode":
                    "siemens_licensing",
                "answers": {
                    "options_activated":
                        "yes"
                },
            },
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
            body[
                "next_question"
            ][
                "fact_id"
            ],
            "license_key_set",
        )

    def test_10_unknown_information_is_not_diagnosis(self):
        response = self.client.post(
            "/development/troubleshoot/turn",
            json={
                "machine_name":
                    "ABB motor",
                "symptom":
                    "Motor stalls",
                "mode":
                    "abb_stall",
                "answers": {
                    "requested_information":
                        "review_reports"
                },
            },
        )

        body = response.json()

        self.assertFalse(
            body["diagnosis_confirmed"]
        )

        self.assertFalse(
            body[
                "approved_for_automatic_execution"
            ]
        )

    def test_11_logfile_scope_not_inferred_from_context(self):
        response = self.client.post(
            "/troubleshoot",
            json={
                "machine_name":
                    "Siemens machine",
                "error_code":
                    "61352",
                "symptom":
                    "Please tell me the logfile parameter",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json()["status"],
            "needs_structured_input",
        )

    def test_12_invalid_question_policy_rejected(self):
        response = self.client.get(
            "/development/troubleshoot/questions",
            params={
                "mode":
                    "guessed_policy"
            },
        )

        self.assertEqual(
            response.status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
