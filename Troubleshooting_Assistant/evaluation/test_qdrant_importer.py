from __future__ import annotations

import hashlib
import tempfile
import unittest

from pathlib import Path

from qdrant_client import QdrantClient

from app.services import (
    qdrant_importer,
    qdrant_store,
    registry_backend,
    retrieval_service,
)


ABB_VECTOR_FILENAME = (
    "dde3696f00424107b1253d4dfd44a05b_"
    "ABB_LV_Motors_RevH_2022_"
    "structured_v1_ready_bge_small.npz"
)


class QdrantImporterTests(
    unittest.TestCase
):

    def setUp(self):

        self.vector_path = (
            Path(
                retrieval_service.VECTOR_DIRECTORY
            )
            / ABB_VECTOR_FILENAME
        ).resolve()

        self.assertTrue(
            self.vector_path.is_file(),
            "Required ABB validation NPZ is missing.",
        )

        (
            self.vectors,
            self.metadata,
            self.parents,
        ) = retrieval_service.load_vector_store(
            ABB_VECTOR_FILENAME
        )

        self.embedding = (
            self.metadata["embedding"]
        )

        self.vector_sha256 = hashlib.sha256(
            self.vector_path.read_bytes()
        ).hexdigest()

        self._temporary = (
            tempfile.TemporaryDirectory(
                prefix=
                    "ta_qdrant_importer_test_"
            )
        )

        temporary_root = Path(
            self._temporary.name
        )

        self.registry_path = (
            temporary_root
            / "registry.sqlite3"
        )

        self.qdrant_path = (
            temporary_root
            / "qdrant"
        )

        self.client = QdrantClient(
            path=str(
                self.qdrant_path
            )
        )

        self.collection = (
            "ut_npz_import"
        )


    def tearDown(self):

        client = getattr(
            self,
            "client",
            None,
        )

        if client is not None:

            close = getattr(
                client,
                "close",
                None,
            )

            if callable(close):
                close()

        self.client = None

        self._temporary.cleanup()


    def _register_document(
        self,
        *,
        source_sha256=None,
    ):

        if source_sha256 is None:
            source_sha256 = (
                self.metadata[
                    "source_sha256"
                ]
            )

        return (
            registry_backend
            .register_enterprise_document(
                {
                    "document_id":
                        self.metadata[
                            "document_id"
                        ],

                    "original_filename":
                        self.metadata[
                            "source_filename"
                        ],

                    "stored_filename":
                        self.metadata[
                            "source_filename"
                        ],

                    "file_type":
                        ".pdf",

                    "file_size_bytes":
                        int(
                            self.metadata[
                                "source_size_bytes"
                            ]
                        ),

                    "source_sha256":
                        source_sha256,
                },

                manufacturer=
                    self.metadata.get(
                        "manufacturer"
                    ),

                document_type=
                    "manual",

                revision=
                    self.metadata.get(
                        "revision"
                    ),

                document_status=
                    "test-only",

                database_path=
                    self.registry_path,
            )
        )


    def _register_artifact(
        self,
        *,
        vector_store_filename=
            ABB_VECTOR_FILENAME,
        vector_store_sha256=None,
        prepared_sha256=None,
    ):

        if vector_store_sha256 is None:
            vector_store_sha256 = (
                self.vector_sha256
            )

        if prepared_sha256 is None:
            prepared_sha256 = (
                self.embedding[
                    "prepared_sha256"
                ]
            )

        return (
            registry_backend
            .register_document_vector_artifact(
                {
                    "document_id":
                        self.metadata[
                            "document_id"
                        ],

                    "vector_store_filename":
                        vector_store_filename,

                    "prepared_filename":
                        self.embedding[
                            "prepared_filename"
                        ],

                    "prepared_sha256":
                        prepared_sha256,

                    "vector_store_sha256":
                        vector_store_sha256,

                    "embedding_model":
                        self.embedding[
                            "model_name"
                        ],

                    "embedding_dimension":
                        self.embedding[
                            "embedding_dimension"
                        ],

                    "vector_count":
                        len(
                            self.metadata[
                                "chunks"
                            ]
                        ),

                    "embedding_created_at_utc":
                        self.embedding[
                            "created_at_utc"
                        ],
                },

                database_path=
                    self.registry_path,
            )
        )


    def test_import_registered_real_npz(self):

        self._register_document()

        artifact = (
            self._register_artifact()
        )

        result = (
            qdrant_importer
            .import_registered_npz_artifact(
                self.client,

                document_id=
                    self.metadata[
                        "document_id"
                    ],

                vector_artifact_id=
                    artifact[
                        "vector_artifact_id"
                    ],

                collection_name=
                    self.collection,

                database_path=
                    self.registry_path,
            )
        )

        self.assertEqual(
            result[
                "points_count"
            ],
            54,
        )

        self.assertTrue(
            result[
                "source_sha256_verified"
            ]
        )

        self.assertTrue(
            result[
                "vector_store_sha256_verified"
            ]
        )

        self.assertTrue(
            result[
                "prepared_sha256_verified"
            ]
        )

        self.assertFalse(
            result[
                "automatic_artifact_selection"
            ]
        )

        query = (
            qdrant_store
            .query_eligible_artifacts(
                self.client,

                query_vector=
                    self.vectors[0],

                eligible_vector_artifact_ids=[
                    artifact[
                        "vector_artifact_id"
                    ]
                ],

                limit=5,

                collection_name=
                    self.collection,
            )
        )

        self.assertGreaterEqual(
            query[
                "results_count"
            ],
            1,
        )

        self.assertTrue(
            all(
                item[
                    "vector_artifact_id"
                ]
                == artifact[
                    "vector_artifact_id"
                ]

                for item
                in query[
                    "results"
                ]
            )
        )

        self.assertIn(
            self.metadata[
                "chunks"
            ][0][
                "chunk_id"
            ],

            [
                item[
                    "chunk_id"
                ]
                for item
                in query[
                    "results"
                ]
            ],
        )


    def test_unknown_artifact_id_fails_before_qdrant_creation(self):

        self._register_document()
        self._register_artifact()

        with self.assertRaises(
            ValueError
        ):
            qdrant_importer.import_registered_npz_artifact(
                self.client,

                document_id=
                    self.metadata[
                        "document_id"
                    ],

                vector_artifact_id=
                    "vec-does-not-exist",

                collection_name=
                    self.collection,

                database_path=
                    self.registry_path,
            )

        self.assertFalse(
            self.client.collection_exists(
                self.collection
            )
        )


    def test_vector_store_sha_mismatch_is_rejected(self):

        self._register_document()

        artifact = (
            self._register_artifact(
                vector_store_sha256=
                    "0" * 64
            )
        )

        with self.assertRaises(
            ValueError
        ):
            qdrant_importer.import_registered_npz_artifact(
                self.client,

                document_id=
                    self.metadata[
                        "document_id"
                    ],

                vector_artifact_id=
                    artifact[
                        "vector_artifact_id"
                    ],

                collection_name=
                    self.collection,

                database_path=
                    self.registry_path,
            )

        self.assertFalse(
            self.client.collection_exists(
                self.collection
            )
        )


    def test_registered_source_sha_mismatch_is_rejected(self):

        self._register_document(
            source_sha256=
                "1" * 64
        )

        artifact = (
            self._register_artifact()
        )

        with self.assertRaises(
            ValueError
        ):
            qdrant_importer.import_registered_npz_artifact(
                self.client,

                document_id=
                    self.metadata[
                        "document_id"
                    ],

                vector_artifact_id=
                    artifact[
                        "vector_artifact_id"
                    ],

                collection_name=
                    self.collection,

                database_path=
                    self.registry_path,
            )

        self.assertFalse(
            self.client.collection_exists(
                self.collection
            )
        )


    def test_exact_artifact_identity_does_not_infer_preference(self):

        self._register_document()

        primary = (
            self._register_artifact()
        )

        secondary = (
            self._register_artifact(
                vector_store_filename=
                    "ut_secondary_unselected.npz",

                vector_store_sha256=
                    "2" * 64,
            )
        )

        self.assertNotEqual(
            primary[
                "vector_artifact_id"
            ],
            secondary[
                "vector_artifact_id"
            ],
        )

        result = (
            qdrant_importer
            .import_registered_npz_artifact(
                self.client,

                document_id=
                    self.metadata[
                        "document_id"
                    ],

                vector_artifact_id=
                    primary[
                        "vector_artifact_id"
                    ],

                collection_name=
                    self.collection,

                database_path=
                    self.registry_path,
            )
        )

        self.assertEqual(
            result[
                "vector_artifact_id"
            ],
            primary[
                "vector_artifact_id"
            ],
        )

        self.assertFalse(
            result[
                "automatic_artifact_selection"
            ]
        )


if __name__ == "__main__":
    unittest.main()
