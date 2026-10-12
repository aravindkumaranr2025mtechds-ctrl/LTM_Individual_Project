import unittest
from pathlib import Path


class FrontendV2StaticTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):

        cls.path = Path(
            "app/static/assistant_v2.html"
        )

        cls.text = (
            cls.path.read_text(
                encoding="utf-8-sig"
            )
        )

    def test_v2_file_exists(self):

        self.assertTrue(
            self.path.exists()
        )

    def test_technician_workspace_present(self):

        self.assertIn(
            "Industrial Troubleshooting Workspace",
            self.text,
        )

        self.assertIn(
            "Technician view",
            self.text,
        )

        self.assertIn(
            "Engineering details",
            self.text,
        )

    def test_existing_backend_endpoints_preserved(self):

        for endpoint in [
            "/documents/search",
            "/documents/search/abb",
            "/documents/search/abb/confirm",
        ]:
            self.assertIn(
                endpoint,
                self.text,
            )

    def test_required_legacy_ids_preserved(self):

        for element_id in [
            "guidedTab",
            "searchTab",
            "guided",
            "reviewForm",
            "mode",
            "sessionLabel",
            "description",
            "initialFields",
            "reset",
            "reviewOutput",
            "search",
            "searchForm",
            "manufacturer",
            "query",
            "alarmLabel",
            "alarm",
            "searchOutput",
        ]:

            self.assertIn(
                'id="' + element_id + '"',
                self.text,
            )

    def test_operator_safety_language_present(self):

        self.assertIn(
            "Cause is not automatically confirmed",
            self.text,
        )

        self.assertIn(
            "No automatic machine action is performed",
            self.text,
        )

    def test_no_external_frontend_dependency(self):

        self.assertNotIn(
            "<script src=",
            self.text.lower(),
        )

        self.assertNotIn(
            'rel="stylesheet"',
            self.text.lower(),
        )


if __name__ == "__main__":
    unittest.main()
