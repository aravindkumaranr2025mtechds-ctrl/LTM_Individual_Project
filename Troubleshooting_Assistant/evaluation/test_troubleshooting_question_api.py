import unittest

from fastapi.testclient import TestClient

from app.main import app


class TroubleshootingQuestionAPITests(
    unittest.TestCase
):
    def setUp(self):
        self.client = TestClient(
            app,
            raise_server_exceptions=False,
        )

    def tearDown(self):
        self.client.close()

    def test_abb_question_form(self):
        response = self.client.get(
            "/development/troubleshoot/questions",
            params={
                "mode": "abb_stall"
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["mode"],
            "abb_stall",
        )

        self.assertEqual(
            body["status"],
            "question_form",
        )

    def test_licensing_question_form(self):
        response = self.client.get(
            "/development/troubleshoot/questions",
            params={
                "mode":
                    "siemens_licensing"
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        ids = {
            item["field_id"]
            for item
            in response.json()[
                "form"
            ]["fields"]
        }

        self.assertIn(
            "license_key_set",
            ids,
        )

    def test_logfile_question_form(self):
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

        field = response.json()[
            "form"
        ]["fields"][0]

        self.assertEqual(
            field["field_id"],
            "alarm_scope",
        )

        self.assertTrue(
            field["required"]
        )

    def test_invalid_mode_is_422(self):
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
