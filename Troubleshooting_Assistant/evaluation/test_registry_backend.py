"""
Tests for trusted Registry V3 backend selection.

These tests must not change the live application registry.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from app.services import (
    postgres_registry,
    registry_backend,
)


class RegistryBackendSelectorTests(
    unittest.TestCase
):

    def test_01_missing_setting_defaults_to_sqlite(
        self
    ):

        with patch.dict(
            os.environ,
            {},
            clear=False,
        ):

            os.environ.pop(
                registry_backend
                .REGISTRY_BACKEND_ENV,
                None,
            )

            self.assertEqual(
                registry_backend
                .get_active_registry_backend(),
                "sqlite",
            )


    def test_02_backend_value_is_normalized(
        self
    ):

        with patch.dict(
            os.environ,
            {
                registry_backend
                .REGISTRY_BACKEND_ENV:
                    "  PoStGrEs  "
            },
            clear=False,
        ):

            self.assertEqual(
                registry_backend
                .get_active_registry_backend(),
                "postgres",
            )


    def test_03_unknown_backend_fails_closed(
        self
    ):

        with patch.dict(
            os.environ,
            {
                registry_backend
                .REGISTRY_BACKEND_ENV:
                    "automatic"
            },
            clear=False,
        ):

            with self.assertRaises(
                RuntimeError
            ):

                registry_backend.get_active_registry_backend()


    def test_04_explicit_database_path_forces_sqlite(
        self
    ):

        with patch.dict(
            os.environ,
            {
                registry_backend
                .REGISTRY_BACKEND_ENV:
                    "postgres"
            },
            clear=False,
        ):

            self.assertEqual(
                registry_backend
                .get_active_registry_backend(
                    database_path=
                        Path(
                            "temporary-test.sqlite3"
                        )
                ),
                "sqlite",
            )


    def test_05_postgres_read_routes_to_postgres_adapter(
        self
    ):

        expected = {
            "document_id":
                "postgres-routed-document"
        }

        with patch.dict(
            os.environ,
            {
                registry_backend
                .REGISTRY_BACKEND_ENV:
                    "postgres"
            },
            clear=False,
        ):

            with patch.object(
                postgres_registry,
                "get_enterprise_document",
                return_value=expected,
            ) as mocked:

                actual = (
                    registry_backend
                    .get_enterprise_document(
                        "postgres-routed-document"
                    )
                )


        self.assertEqual(
            actual,
            expected,
        )

        mocked.assert_called_once_with(
            "postgres-routed-document"
        )


    def test_06_postgres_failure_does_not_fallback(
        self
    ):

        with patch.dict(
            os.environ,
            {
                registry_backend
                .REGISTRY_BACKEND_ENV:
                    "postgres"
            },
            clear=False,
        ):

            with patch.object(
                postgres_registry,
                "get_enterprise_document",
                side_effect=RuntimeError(
                    "simulated-postgres-failure"
                ),
            ):

                with self.assertRaisesRegex(
                    RuntimeError,
                    "simulated-postgres-failure",
                ):

                    registry_backend.get_enterprise_document(
                        "document-001"
                    )


    def test_07_explicit_temp_sqlite_roundtrip(
        self
    ):

        with tempfile.TemporaryDirectory() as temp_name:

            database_path = (
                Path(temp_name)
                / "registry.sqlite3"
            )


            # Even with process configuration set to PostgreSQL,
            # the explicit temporary SQLite path must remain SQLite.
            with patch.dict(
                os.environ,
                {
                    registry_backend
                    .REGISTRY_BACKEND_ENV:
                        "postgres"
                },
                clear=False,
            ):

                registered = (
                    registry_backend
                    .register_enterprise_document(
                        {
                            "document_id":
                                "selector-sqlite-test",

                            "original_filename":
                                "selector-test.pdf",

                            "stored_filename":
                                "selector-test-stored.pdf",

                            "file_type":
                                ".pdf",

                            "file_size_bytes":
                                100,

                            "source_sha256":
                                "a" * 64,
                        },
                        manufacturer="ABB",
                        document_type="manual",
                        database_path=
                            database_path,
                    )
                )


                loaded = (
                    registry_backend
                    .get_enterprise_document(
                        "selector-sqlite-test",
                        database_path=
                            database_path,
                    )
                )


            self.assertEqual(
                registered[
                    "document_id"
                ],
                "selector-sqlite-test",
            )

            self.assertIsNotNone(
                loaded
            )

            self.assertEqual(
                loaded[
                    "source_sha256"
                ],
                "a" * 64,
            )


    def test_08_access_level_cannot_be_retrieval_filter(
        self
    ):

        with tempfile.TemporaryDirectory() as temp_name:

            database_path = (
                Path(temp_name)
                / "registry.sqlite3"
            )

            with self.assertRaises(
                ValueError
            ):

                registry_backend.discover_enterprise_vector_artifacts(
                    {
                        "access_level":
                            "internal"
                    },
                    database_path=
                        database_path,
                )


if __name__ == "__main__":
    unittest.main()


# ----------------------------------------------------------------------
# Step 7D5D-B3C-A3
# Protect the embedding artifact helper's Registry backend boundary.
# ----------------------------------------------------------------------

class EmbeddingArtifactRegistryBackendContractTests(
    __import__("unittest").TestCase
):

    def test_embedding_artifact_helper_has_optional_database_path(self):

        import inspect

        from app.services import embedding_service

        signature = inspect.signature(
            embedding_service
            ._register_vector_artifact_if_enterprise
        )

        self.assertIn(
            "database_path",
            signature.parameters,
        )

        parameter = (
            signature.parameters[
                "database_path"
            ]
        )

        self.assertEqual(
            parameter.kind,
            inspect.Parameter.KEYWORD_ONLY,
        )

        self.assertIsNone(
            parameter.default
        )
