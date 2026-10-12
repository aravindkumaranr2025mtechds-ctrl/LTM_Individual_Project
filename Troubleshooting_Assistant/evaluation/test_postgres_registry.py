"""
Persistent integration tests for the PostgreSQL Registry V3 adapter.

The tests use a reserved test prefix and remove only records created
under that prefix.

If the local PostgreSQL development server is unavailable, this
integration test class is skipped. Schema or application-contract
errors are not silently skipped.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import psycopg

from app.services import postgres_registry


TEST_PREFIX = "ut_pg_registry_"


class PostgresRegistryIntegrationTests(
    unittest.TestCase
):
    """
    Verify PostgreSQL Registry V3 behavior without touching
    production/manual/vector files.
    """

    @classmethod
    def setUpClass(cls):

        try:

            cls.foundation = (
                postgres_registry
                .validate_postgres_registry_v3()
            )

        except (
            psycopg.OperationalError,
            FileNotFoundError,
        ) as error:

            raise unittest.SkipTest(
                "Local PostgreSQL development registry "
                "is unavailable."
            ) from error


        if (
            cls.foundation[
                "schema_version"
            ]
            != 3
        ):
            raise RuntimeError(
                "PostgreSQL Registry V3 is required."
            )


        if (
            cls.foundation[
                "application_role_superuser"
            ]
            is not False
        ):
            raise RuntimeError(
                "Tests must not run with a PostgreSQL superuser."
            )


        cls._cleanup_test_records()


    @classmethod
    def tearDownClass(cls):

        cls._cleanup_test_records()


    @classmethod
    def _cleanup_test_records(cls):
        """
        Remove only records having the reserved integration-test
        identifiers.

        Vector artifacts are removed first because their document
        foreign key uses ON DELETE RESTRICT.
        """
        connection = (
            postgres_registry
            ._connect()
        )

        try:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    DELETE FROM document_vector_artifacts
                    WHERE document_id LIKE %s
                       OR vector_store_filename LIKE %s
                    """,
                    (
                        TEST_PREFIX + "%",
                        TEST_PREFIX + "%",
                    ),
                )

                cursor.execute(
                    """
                    DELETE FROM enterprise_documents
                    WHERE document_id LIKE %s
                       OR stored_filename LIKE %s
                    """,
                    (
                        TEST_PREFIX + "%",
                        TEST_PREFIX + "%",
                    ),
                )

            connection.commit()

        except BaseException:

            connection.rollback()
            raise

        finally:

            connection.close()


    @classmethod
    def _database_counts(cls):

        connection = (
            postgres_registry
            ._connect()
        )

        try:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM enterprise_documents
                    """
                )

                documents = (
                    cursor.fetchone()[
                        "total"
                    ]
                )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM document_vector_artifacts
                    """
                )

                artifacts = (
                    cursor.fetchone()[
                        "total"
                    ]
                )

            return (
                documents,
                artifacts,
            )

        finally:

            connection.close()


    def setUp(self):

        self._cleanup_test_records()

        (
            self.baseline_documents,
            self.baseline_artifacts,
        ) = self._database_counts()


    def tearDown(self):

        self._cleanup_test_records()

        (
            final_documents,
            final_artifacts,
        ) = self._database_counts()


        self.assertEqual(
            final_documents,
            self.baseline_documents,
            "PostgreSQL test leaked an enterprise document.",
        )

        self.assertEqual(
            final_artifacts,
            self.baseline_artifacts,
            "PostgreSQL test leaked a vector artifact.",
        )


    # ========================================================
    # TEST DATA HELPERS
    # ========================================================

    def _document(
        self,
        suffix: str,
        sha_character: str,
        *,
        stored_filename: str | None = None,
    ) -> dict:

        document_id = (
            TEST_PREFIX
            + suffix
        )

        return {
            "document_id":
                document_id,

            "original_filename":
                f"{document_id}.pdf",

            "stored_filename":
                stored_filename
                or f"{document_id}_stored.pdf",

            "file_type":
                ".pdf",

            "file_size_bytes":
                4096,

            "source_sha256":
                sha_character * 64,
        }


    def _register_document(
        self,
        suffix: str,
        sha_character: str,
        *,
        family: str | None = None,
        predecessor: str | None = None,
        manufacturer: str = "ABB",
        plant_id: str = "plant-a",
        stored_filename: str | None = None,
    ) -> dict:

        return (
            postgres_registry
            .register_enterprise_document(
                self._document(
                    suffix,
                    sha_character,
                    stored_filename=
                        stored_filename,
                ),
                plant_id=plant_id,
                department="maintenance",
                equipment_id=(
                    TEST_PREFIX
                    + "motor-001"
                ),
                equipment_type="motor",
                manufacturer=manufacturer,
                model="integration-test-model",
                document_family_id=family,
                supersedes_document_id=
                    predecessor,
                document_type="manual",
                revision="R1",
                effective_date="2026-09-18",
                document_status="test-only",
                access_level=None,
            )
        )


    def _artifact(
        self,
        document_id: str,
        suffix: str,
        sha_character: str,
        *,
        dimension: int = 384,
        vector_count: int = 10,
        vector_filename: str | None = None,
    ) -> dict:

        now = datetime.now(
            timezone.utc
        ).isoformat()

        return {
            "document_id":
                document_id,

            "vector_store_filename":
                vector_filename
                or (
                    TEST_PREFIX
                    + suffix
                    + ".npz"
                ),

            "prepared_filename":
                (
                    TEST_PREFIX
                    + suffix
                    + ".json"
                ),

            "prepared_sha256":
                sha_character * 64,

            "vector_store_sha256":
                (
                    sha_character.upper()
                    * 64
                ).lower(),

            "embedding_model":
                "BAAI/bge-small-en-v1.5",

            "embedding_dimension":
                dimension,

            "vector_count":
                vector_count,

            "embedding_created_at_utc":
                now,
        }


    # ========================================================
    # 1. FOUNDATION
    # ========================================================

    def test_01_registry_v3_and_non_superuser_boundary(
        self
    ):

        result = (
            postgres_registry
            .validate_postgres_registry_v3()
        )

        self.assertEqual(
            result[
                "schema_version"
            ],
            3,
        )

        self.assertFalse(
            result[
                "application_role_superuser"
            ]
        )


    # ========================================================
    # 2. DOCUMENT WRITE + READ
    # ========================================================

    def test_02_document_registration_roundtrip(
        self
    ):

        registered = (
            postgres_registry
            .register_enterprise_document(
                self._document(
                    "document_roundtrip",
                    "a",
                ),
                plant_id="  plant-a  ",
                department=" maintenance ",
                equipment_id=(
                    TEST_PREFIX
                    + "motor-roundtrip"
                ),
                equipment_type=" motor ",
                manufacturer=" ABB ",
                model=" test-model ",
                document_family_id=(
                    TEST_PREFIX
                    + "family-roundtrip"
                ),
                document_type=" manual ",
                revision=" R1 ",
                effective_date=" 2026-09-18 ",
                document_status=" test-only ",
                access_level=None,
            )
        )


        self.assertEqual(
            registered[
                "plant_id"
            ],
            "plant-a",
        )

        self.assertEqual(
            registered[
                "department"
            ],
            "maintenance",
        )

        self.assertEqual(
            registered[
                "manufacturer"
            ],
            "ABB",
        )


        loaded = (
            postgres_registry
            .get_enterprise_document(
                registered[
                    "document_id"
                ]
            )
        )


        self.assertIsNotNone(
            loaded
        )

        self.assertEqual(
            loaded[
                "document_id"
            ],
            registered[
                "document_id"
            ],
        )

        self.assertEqual(
            loaded[
                "source_sha256"
            ],
            "a" * 64,
        )


    # ========================================================
    # 3. DUPLICATE PROTECTION
    # ========================================================

    def test_03_duplicate_document_constraints(
        self
    ):

        first = (
            self._register_document(
                "duplicate_base",
                "b",
            )
        )


        with self.assertRaises(
            ValueError
        ):

            postgres_registry.register_enterprise_document(
                self._document(
                    "duplicate_base",
                    "c",
                    stored_filename=(
                        TEST_PREFIX
                        + "duplicate_other.pdf"
                    ),
                )
            )


        with self.assertRaises(
            ValueError
        ):

            postgres_registry.register_enterprise_document(
                self._document(
                    "duplicate_second_id",
                    "d",
                    stored_filename=first[
                        "stored_filename"
                    ],
                )
            )


    # ========================================================
    # 4. ONE DOCUMENT -> MANY ARTIFACTS + AMBIGUITY
    # ========================================================

    def test_04_multiple_artifacts_remain_ambiguous(
        self
    ):

        document = (
            self._register_document(
                "multi_artifact",
                "c",
                family=(
                    TEST_PREFIX
                    + "family-multi"
                ),
                manufacturer="ABB",
            )
        )


        artifact_one = (
            postgres_registry
            .register_document_vector_artifact(
                self._artifact(
                    document[
                        "document_id"
                    ],
                    "multi_vectors_1",
                    "1",
                )
            )
        )


        artifact_two = (
            postgres_registry
            .register_document_vector_artifact(
                self._artifact(
                    document[
                        "document_id"
                    ],
                    "multi_vectors_2",
                    "2",
                )
            )
        )


        self.assertNotEqual(
            artifact_one[
                "vector_artifact_id"
            ],
            artifact_two[
                "vector_artifact_id"
            ],
        )


        artifacts = (
            postgres_registry
            .find_document_vector_artifacts(
                document[
                    "document_id"
                ]
            )
        )


        self.assertEqual(
            len(artifacts),
            2,
        )


        discovery = (
            postgres_registry
            .discover_enterprise_vector_artifacts(
                {
                    "manufacturer":
                        "abb",

                    "document_family_id": (
                        TEST_PREFIX
                        + "family-multi"
                    ),
                }
            )
        )


        self.assertEqual(
            discovery[
                "documents_with_artifacts"
            ],
            1,
        )

        self.assertEqual(
            discovery[
                "artifacts_count"
            ],
            2,
        )

        self.assertEqual(
            discovery[
                "single_artifact_candidates"
            ],
            [],
        )

        self.assertEqual(
            len(
                discovery[
                    "ambiguous_documents"
                ]
            ),
            1,
        )

        self.assertEqual(
            discovery[
                "ambiguous_documents"
            ][0][
                "document_id"
            ],
            document[
                "document_id"
            ],
        )

        self.assertEqual(
            discovery[
                "ambiguous_documents"
            ][0][
                "artifact_count"
            ],
            2,
        )

        self.assertFalse(
            discovery[
                "automatic_artifact_selection"
            ]
        )


        forbidden = {
            "current",
            "is_current",
            "preferred",
            "is_preferred",
            "approved",
            "is_approved",
        }


        for artifact in (
            discovery[
                "candidate_artifacts"
            ]
        ):

            self.assertFalse(
                forbidden
                & set(artifact)
            )


    # ========================================================
    # 5. METADATA FILTERS + ACCESS BOUNDARY
    # ========================================================

    def test_05_metadata_filters_and_access_level_boundary(
        self
    ):

        document = (
            self._register_document(
                "metadata_filter",
                "d",
                family=(
                    TEST_PREFIX
                    + "family-filter"
                ),
                manufacturer="Siemens",
                plant_id="Plant-01",
            )
        )


        postgres_registry.register_document_vector_artifact(
            self._artifact(
                document[
                    "document_id"
                ],
                "metadata_filter_vectors",
                "3",
            )
        )


        result = (
            postgres_registry
            .discover_enterprise_vector_artifacts(
                {
                    "manufacturer":
                        "  siemens  ",

                    "plant_id":
                        " plant-01 ",
                }
            )
        )


        self.assertEqual(
            result[
                "metadata_filters"
            ],
            {
                "manufacturer":
                    "siemens",

                "plant_id":
                    "plant-01",
            },
        )


        self.assertTrue(
            result[
                "metadata_filter_applied"
            ]
        )

        self.assertEqual(
            result[
                "artifacts_count"
            ],
            1,
        )


        with self.assertRaises(
            ValueError
        ):

            postgres_registry.discover_enterprise_vector_artifacts(
                {
                    "access_level":
                        "internal"
                }
            )


        with self.assertRaises(
            ValueError
        ):

            postgres_registry.discover_enterprise_vector_artifacts(
                {
                    "unsupported_filter":
                        "value"
                }
            )


    # ========================================================
    # 6. RELATIONSHIP CLASSIFICATIONS
    # ========================================================

    def test_06_relationship_classifications_and_safety(
        self
    ):

        family = (
            TEST_PREFIX
            + "relationship-family"
        )


        base = (
            self._register_document(
                "relationship_base",
                "e",
                family=family,
            )
        )


        exact = (
            postgres_registry
            .analyze_enterprise_document_relationship(
                {
                    "source_sha256":
                        "e" * 64
                }
            )
        )


        self.assertEqual(
            exact[
                "classification"
            ],
            "exact_content_match",
        )

        self.assertIn(
            base[
                "document_id"
            ],
            exact[
                "exact_content_document_ids"
            ],
        )


        same_family = (
            postgres_registry
            .analyze_enterprise_document_relationship(
                {
                    "source_sha256":
                        "f" * 64
                },
                document_family_id=
                    family,
            )
        )


        self.assertEqual(
            same_family[
                "classification"
            ],
            "same_family_new_content",
        )


        successor = (
            postgres_registry
            .analyze_enterprise_document_relationship(
                {
                    "source_sha256":
                        "1" * 64
                },
                document_family_id=
                    family,
                supersedes_document_id=
                    base[
                        "document_id"
                    ],
            )
        )


        self.assertEqual(
            successor[
                "classification"
            ],
            "declared_revision_successor",
        )


        new_document = (
            postgres_registry
            .analyze_enterprise_document_relationship(
                {
                    "source_sha256":
                        "2" * 64
                },
                document_family_id=(
                    TEST_PREFIX
                    + "unused-family"
                ),
            )
        )


        self.assertEqual(
            new_document[
                "classification"
            ],
            "new_document",
        )


        for result in (
            exact,
            same_family,
            successor,
            new_document,
        ):

            self.assertFalse(
                result[
                    "automatic_deletion"
                ]
            )

            self.assertFalse(
                result[
                    "automatic_status_change"
                ]
            )

            self.assertFalse(
                result[
                    "revision_order_inferred"
                ]
            )


    # ========================================================
    # 7. PREDECESSOR VALIDATION
    # ========================================================

    def test_07_declared_predecessor_rules(
        self
    ):

        family = (
            TEST_PREFIX
            + "predecessor-family"
        )


        predecessor = (
            self._register_document(
                "predecessor_base",
                "3",
                family=family,
            )
        )


        successor = (
            self._register_document(
                "predecessor_successor",
                "4",
                family=family,
                predecessor=(
                    predecessor[
                        "document_id"
                    ]
                ),
            )
        )


        self.assertEqual(
            successor[
                "supersedes_document_id"
            ],
            predecessor[
                "document_id"
            ],
        )


        with self.assertRaises(
            ValueError
        ):

            self._register_document(
                "wrong_family_successor",
                "5",
                family=(
                    TEST_PREFIX
                    + "different-family"
                ),
                predecessor=(
                    predecessor[
                        "document_id"
                    ]
                ),
            )


        with self.assertRaises(
            ValueError
        ):

            self._register_document(
                "missing_predecessor",
                "6",
                family=family,
                predecessor=(
                    TEST_PREFIX
                    + "does-not-exist"
                ),
            )


        with self.assertRaises(
            ValueError
        ):

            postgres_registry.register_enterprise_document(
                self._document(
                    "predecessor_without_family",
                    "7",
                ),
                supersedes_document_id=(
                    predecessor[
                        "document_id"
                    ]
                ),
            )


    # ========================================================
    # 8. ARTIFACT INPUT SAFETY
    # ========================================================

    def test_08_artifact_input_and_duplicate_safety(
        self
    ):

        with self.assertRaises(
            ValueError
        ):

            postgres_registry.register_document_vector_artifact(
                self._artifact(
                    (
                        TEST_PREFIX
                        + "missing-document"
                    ),
                    "unknown_document_artifact",
                    "8",
                )
            )


        document = (
            self._register_document(
                "artifact_validation",
                "9",
            )
        )


        with self.assertRaises(
            ValueError
        ):

            postgres_registry.register_document_vector_artifact(
                self._artifact(
                    document[
                        "document_id"
                    ],
                    "invalid_dimension",
                    "a",
                    dimension=0,
                )
            )


        with self.assertRaises(
            ValueError
        ):

            postgres_registry.register_document_vector_artifact(
                self._artifact(
                    document[
                        "document_id"
                    ],
                    "invalid_count",
                    "b",
                    vector_count=0,
                )
            )


        valid = (
            postgres_registry
            .register_document_vector_artifact(
                self._artifact(
                    document[
                        "document_id"
                    ],
                    "duplicate_vector_base",
                    "c",
                )
            )
        )


        with self.assertRaises(
            ValueError
        ):

            postgres_registry.register_document_vector_artifact(
                self._artifact(
                    document[
                        "document_id"
                    ],
                    "duplicate_vector_other",
                    "d",
                    vector_filename=(
                        valid[
                            "vector_store_filename"
                        ]
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
