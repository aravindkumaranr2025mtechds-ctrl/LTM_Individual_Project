import unittest

from fastapi.testclient import TestClient

from app.main import app


class TroubleshootingGuidanceAPITests(
    unittest.TestCase
):
    def setUp(self):
        self.client = TestClient(
            app,
            raise_server_exceptions=False,
        )

    def tearDown(self):
        self.client.close()

    def test_all_guidance_endpoint(self):
        response = self.client.get(
            "/development/troubleshoot/guidance"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["supported_modes"],
            [
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            ],
        )

        self.assertFalse(
            body["diagnosis_confirmed"]
        )

    def test_specific_logfile_guidance(self):
        response = self.client.get(
            "/development/troubleshoot/guidance",
            params={
                "mode": "siemens_logfile"
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["mode"],
            "siemens_logfile",
        )

        self.assertIn(
            "61352",
            body["guidance"][
                "alarm_scope_values"
            ],
        )

    def test_invalid_guidance_mode_is_422(self):
        response = self.client.get(
            "/development/troubleshoot/guidance",
            params={
                "mode": "guessed_policy"
            },
        )

        self.assertEqual(
            response.status_code,
            422,
        )

    def test_free_text_response_includes_guidance(self):
        response = self.client.post(
            "/troubleshoot",
            json={
                "machine_name": "Siemens",
                "error_code": "61352",
                "symptom": "Need logfile path",
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

        self.assertEqual(
            body["guidance_endpoint"],
            "/development/troubleshoot/guidance",
        )

        self.assertEqual(
            set(
                body[
                    "structured_input_guidance"
                ]
            ),
            {
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            },
        )

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
