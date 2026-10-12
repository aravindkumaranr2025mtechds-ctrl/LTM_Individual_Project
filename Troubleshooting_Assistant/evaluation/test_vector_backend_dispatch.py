from __future__ import annotations

import unittest

from pathlib import Path
from unittest.mock import patch

from app import main as main_module

from app.services import (
    qdrant_store,
    retrieval_service,
)


class VectorBackendDispatchTests(
    unittest.TestCase
):

    def tearDown(self):

        qdrant_store.close_application_qdrant_client()


    def test_default_npz_dispatch_uses_existing_npz_retrieval(
        self,
    ):

        with patch.object(
            qdrant_store,
            "get_vector_retrieval_backend",
            return_value="npz",
        ), patch.object(
            retrieval_service,
            "retrieve_enterprise_sections",
            return_value={
                "backend": "npz"
            },
        ) as npz_call, patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_qdrant",
        ) as qdrant_call:

            result = retrieval_service.retrieve_enterprise_sections_configured(
                query="motor stalls",
                top_k=3,
                metadata_filters={
                    "manufacturer": "ABB"
                },
                database_path=Path(
                    "temporary.sqlite3"
                ),
                candidate_limit=12,
            )


        self.assertEqual(
            result,
            {
                "backend": "npz"
            },
        )


        npz_call.assert_called_once_with(
            query="motor stalls",
            alarm_number=None,
            top_k=3,
            metadata_filters={
                "manufacturer": "ABB"
            },
            database_path=Path(
                "temporary.sqlite3"
            ),
            candidate_limit=12,
        )


        qdrant_call.assert_not_called()


    def test_qdrant_dispatch_uses_process_owned_client_and_collection(
        self,
    ):

        sentinel_client = object()


        with patch.object(
            qdrant_store,
            "get_vector_retrieval_backend",
            return_value="qdrant",
        ), patch.object(
            qdrant_store,
            "get_application_qdrant_client",
            return_value=sentinel_client,
        ) as get_client, patch.object(
            qdrant_store,
            "get_application_qdrant_collection_name",
            return_value="trusted_collection",
        ) as get_collection, patch.object(
            retrieval_service,
            "retrieve_enterprise_sections",
        ) as npz_call, patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_qdrant",
            return_value={
                "backend": "qdrant"
            },
        ) as qdrant_call:

            result = retrieval_service.retrieve_enterprise_sections_configured(
                query="low voltage motor",
                top_k=5,
                metadata_filters={
                    "manufacturer": "ABB"
                },
                database_path=Path(
                    "temporary.sqlite3"
                ),
            )


        self.assertEqual(
            result,
            {
                "backend": "qdrant"
            },
        )


        get_client.assert_called_once_with()

        get_collection.assert_called_once_with()

        npz_call.assert_not_called()


        qdrant_call.assert_called_once_with(
            sentinel_client,
            query="low voltage motor",
            alarm_number=None,
            top_k=5,
            metadata_filters={
                "manufacturer": "ABB"
            },
            collection_name="trusted_collection",
            database_path=Path(
                "temporary.sqlite3"
            ),
            candidate_limit=25,
        )


    def test_invalid_backend_fails_before_retrieval(
        self,
    ):

        with patch.object(
            qdrant_store,
            "get_vector_retrieval_backend",
            side_effect=ValueError(
                "invalid backend"
            ),
        ), patch.object(
            retrieval_service,
            "retrieve_enterprise_sections",
        ) as npz_call, patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_qdrant",
        ) as qdrant_call:

            with self.assertRaises(
                ValueError
            ):

                retrieval_service.retrieve_enterprise_sections_configured(
                    query="test"
                )


        npz_call.assert_not_called()

        qdrant_call.assert_not_called()


    def test_qdrant_failure_does_not_fallback_to_npz(
        self,
    ):

        sentinel_client = object()


        with patch.object(
            qdrant_store,
            "get_vector_retrieval_backend",
            return_value="qdrant",
        ), patch.object(
            qdrant_store,
            "get_application_qdrant_client",
            return_value=sentinel_client,
        ), patch.object(
            qdrant_store,
            "get_application_qdrant_collection_name",
            return_value="trusted_collection",
        ), patch.object(
            retrieval_service,
            "retrieve_enterprise_sections",
        ) as npz_call, patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_qdrant",
            side_effect=FileNotFoundError(
                "Qdrant collection missing"
            ),
        ):

            with self.assertRaises(
                FileNotFoundError
            ):

                retrieval_service.retrieve_enterprise_sections_configured(
                    query="test"
                )


        npz_call.assert_not_called()


    def test_request_model_has_no_backend_or_storage_controls(
        self,
    ):

        model = (
            main_module
            .EnterpriseDocumentSearchRequest
        )


        fields = getattr(
            model,
            "model_fields",
            None,
        )


        if fields is None:

            fields = getattr(
                model,
                "__fields__",
            )


        names = set(
            fields.keys()
        )


        forbidden = {
            "backend",
            "vector_backend",
            "vector_retrieval_backend",
            "qdrant_path",
            "qdrant_url",
            "qdrant_collection",
            "collection_name",
            "access_level",
        }


        self.assertTrue(
            names.isdisjoint(
                forbidden
            )
        )


    def test_enterprise_route_uses_configured_dispatcher_only(
        self,
    ):

        source = Path(
            main_module.__file__
        ).read_text(
            encoding="utf-8-sig"
        )


        start = source.find(
            '"/development/documents/search/enterprise"'
        )


        self.assertGreaterEqual(
            start,
            0,
        )


        route = source[
            start:
            start + 7000
        ]


        self.assertIn(
            "retrieve_enterprise_sections_configured(",
            route,
        )


        self.assertNotIn(
            "return retrieve_enterprise_sections(",
            route,
        )


        self.assertNotIn(
            "TA_VECTOR_RETRIEVAL_BACKEND",
            route,
        )


        self.assertNotIn(
            "QdrantClient(",
            route,
        )


if __name__ == "__main__":
    unittest.main()
