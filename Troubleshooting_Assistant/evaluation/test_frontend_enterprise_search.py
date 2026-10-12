from __future__ import annotations

import unittest

from pathlib import Path


class FrontendEnterpriseSearchTests(
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


    def test_search_uses_enterprise_assistant_turn(
        self,
    ):

        self.assertIn(
            "/assistant/turn",
            self.text,
        )

        self.assertIn(
            "mode:'enterprise_evidence'",
            self.text,
        )

        self.assertIn(
            "enterpriseSearchCall",
            self.text,
        )


    def test_enterprise_browser_payload_has_no_storage_controls(
        self,
    ):

        start = self.text.index(
            "function enterpriseSearchCall"
        )

        end = self.text.index(
            "</script>",
            start,
        )

        block = self.text[
            start:end
        ]


        for forbidden in (
            "vector_store_filename",
            "database_path",
            "qdrant_path",
            "collection_name",
            "vector_artifact_id",
            "access_level",
            "vector_backend",
        ):

            self.assertNotIn(
                forbidden,
                block,
            )


    def test_technician_renderer_hides_internal_vector_details(
        self,
    ):

        start = self.text.index(
            "function enterpriseSearchResult"
        )

        end = self.text.index(
            "async function enterpriseSearchCall",
            start,
        )

        block = self.text[
            start:end
        ]


        for forbidden in (
            "cosine_similarity",
            "matched_chunk_id",
            "vector_artifact_id",
            "qdrant_used",
            "vector_store_filename",
        ):

            self.assertNotIn(
                forbidden,
                block,
            )


        self.assertIn(
            "Evidence reliability checks",
            self.text,
        )

        self.assertIn(
            "not a diagnosis-confidence score",
            self.text,
        )


    def test_legacy_search_contract_is_retained(
        self,
    ):

        for endpoint in (
            "/documents/search",
            "/documents/search/abb",
            "/documents/search/abb/confirm",
        ):

            self.assertIn(
                endpoint,
                self.text,
            )


        for element_id in (
            "searchForm",
            "manufacturer",
            "query",
            "alarm",
            "searchOutput",
        ):

            self.assertIn(
                'id="' + element_id + '"',
                self.text,
            )


if __name__ == "__main__":
    unittest.main()
