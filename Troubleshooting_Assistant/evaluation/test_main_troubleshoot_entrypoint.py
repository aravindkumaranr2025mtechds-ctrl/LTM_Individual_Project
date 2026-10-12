import unittest

from fastapi.testclient import TestClient

from app.main import app


ABB = (
    "dde3696f00424107b1253d4dfd44a05b_"
    "ABB_LV_Motors_RevH_2022"
)

INDEX = (
    ABB
    + "_structured_v1_ready_evidence_v1.json"
)


class MainTroubleshootEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(
            app,
            raise_server_exceptions=False,
        )

    def tearDown(self):
        self.client.close()

    def base(self):
        return {
            "machine_name": "Example machine",
            "error_code": None,
            "symptom": "Reported troubleshooting symptom",
            "operating_condition": None,
            "previous_attempts": None,
        }

    def test_free_text_does_not_infer_policy(self):
        payload = self.base()
        payload.update({
            "machine_name": "Siemens",
            "error_code": "61352",
            "symptom": "logfile path",
        })

        response = self.client.post(
            "/troubleshoot",
            json=payload,
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
            body["approved_for_automatic_execution"]
        )

    def test_abb_explicit_structured_request(self):
        payload = self.base()

        payload["structured_assistance"] = {
            "mode": "abb_stall",
            "payload": {
                "index_filename": INDEX,
                "observations": {},
                "requested_information":
                    "list_possible_causes",
                "deferred_fact_ids": [],
            },
        }

        response = self.client.post(
            "/troubleshoot",
            json=payload,
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

        result = (
            body["assistance"]["result"]
        )

        self.assertEqual(
            result["status"],
            "source_information",
        )

        self.assertEqual(
            result["source_record_count"],
            5,
        )

    def test_siemens_licensing_explicit_request(self):
        payload = self.base()

        payload["structured_assistance"] = {
            "mode": "siemens_licensing",
            "payload": {
                "observations": {
                    "options_activated": [True],
                    "license_key_set": [False],
                },
                "clarifications_used": 0,
                "deferred_fact_ids": [],
            },
        }

        response = self.client.post(
            "/troubleshoot",
            json=payload,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        result = (
            response.json()
            ["assistance"]
            ["result"]
        )

        self.assertEqual(
            result["status"],
            "description_supported",
        )

        self.assertEqual(
            result["selected_description_alarm"],
            "8080",
        )

    def test_siemens_logfile_explicit_request(self):
        payload = self.base()

        payload["structured_assistance"] = {
            "mode": "siemens_logfile",
            "payload": {
                "alarm_scope":
                    "61352_or_61353",
            },
        }

        response = self.client.post(
            "/troubleshoot",
            json=payload,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        result = (
            response.json()
            ["assistance"]
            ["result"]
        )

        self.assertEqual(
            result["status"],
            "answer_supported",
        )

        self.assertEqual(
            result["answer"],
            "_PROTNAME[0]",
        )

    def test_invalid_structured_payload_is_422(self):
        payload = self.base()

        payload["structured_assistance"] = {
            "mode": "siemens_logfile",
            "payload": {
                "alarm_scope": "guessed_from_text",
            },
        }

        response = self.client.post(
            "/troubleshoot",
            json=payload,
        )

        self.assertEqual(
            response.status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
