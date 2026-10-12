import unittest

from fastapi.testclient import TestClient

from app.main import app


class TroubleshootingAnswerFlowTests(
    unittest.TestCase
):
    def setUp(self):
        self.client = TestClient(
            app,
            raise_server_exceptions=False,
        )

    def tearDown(self):
        self.client.close()

    def build(self, mode, answers):
        return self.client.post(
            "/development/troubleshoot/build",
            json={
                "mode": mode,
                "answers": answers,
            },
        )

    def test_abb_form_answers_build_payload(self):
        response = self.build(
            "abb_stall",
            {
                "requested_information":
                    "review_reports",
                "low_voltage_reported":
                    "yes",
                "open_circuit_reported":
                    "unknown",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        structured = body[
            "structured_assistance"
        ]

        self.assertEqual(
            structured["mode"],
            "abb_stall",
        )

        self.assertEqual(
            structured[
                "payload"
            ][
                "observations"
            ][
                "low_voltage_reported"
            ],
            [True],
        )

    def test_logfile_form_answer_builds_payload(self):
        response = self.build(
            "siemens_logfile",
            {
                "alarm_scope":
                    "61352_or_61353",
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
            structured["payload"][
                "alarm_scope"
            ],
            "61352_or_61353",
        )

    def test_missing_logfile_scope_rejected(self):
        response = self.build(
            "siemens_logfile",
            {},
        )

        self.assertEqual(
            response.status_code,
            422,
        )

    def test_built_logfile_payload_runs_through_main_endpoint(self):
        built = self.build(
            "siemens_logfile",
            {
                "alarm_scope":
                    "61352_or_61353",
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
            body["assistance"][
                "selected_policy"
            ],
            "siemens_logfile",
        )

        result = body[
            "assistance"
        ][
            "result"
        ]

        self.assertEqual(
            result["status"],
            "answer_supported",
        )

        self.assertEqual(
            result["answer"],
            "_PROTNAME[0]",
        )

    def test_built_licensing_payload_runs_through_main_endpoint(self):
        built = self.build(
            "siemens_licensing",
            {
                "options_activated":
                    "yes",
                "license_key_set":
                    "no",
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
                "symptom":
                    "Licensing issue",
                "structured_assistance":
                    structured,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        result = response.json()[
            "assistance"
        ][
            "result"
        ]

        self.assertEqual(
            result["status"],
            "description_supported",
        )

        self.assertEqual(
            result[
                "selected_description_alarm"
            ],
            "8080",
        )

    def test_safety_flags_preserved(self):
        response = self.build(
            "siemens_logfile",
            {
                "alarm_scope":
                    "61352",
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


if __name__ == "__main__":
    unittest.main()
