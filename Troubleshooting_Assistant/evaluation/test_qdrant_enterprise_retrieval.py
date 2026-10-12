from __future__ import annotations

import hashlib
import tempfile
import unittest

from pathlib import Path

import numpy as np

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


class _DummyModel:

    def __init__(
        self,
        vector,
    ):
        self.vector = vector


    def encode(
        self,
        texts,
        **kwargs,
    ):
        return np.asarray(
            [
                self.vector
            ],
            dtype=np.float32,
        )


class QdrantEnterpriseRetrievalTests(
    unittest.TestCase
):

    def setUp(self):

        self.vector_path = (
            Path(
                retrieval_service
                .VECTOR_DIRECTORY
            )
            / ABB_VECTOR_FILENAME
        ).resolve()


        self.assertTrue(
            self.vector_path.is_file()
        )


        (
            self.vectors,
            self.metadata,
            self.parents,
        ) = (
            retrieval_service
            .load_vector_store(
                ABB_VECTOR_FILENAME
            )
        )


        self.embedding = (
            self.metadata[
                "embedding"
            ]
        )


        self.vector_sha256 = (
            hashlib.sha256(
                self.vector_path
                .read_bytes()
            )
            .hexdigest()
        )


        self.temp = (
            tempfile
            .TemporaryDirectory(
                prefix=
                    "ta_7edc_test_"
            )
        )


        root = Path(
            self.temp.name
        )


        self.registry_path = (
            root
            / "registry.sqlite3"
        )


        self.client = QdrantClient(
            path=str(
                root
                / "qdrant"
            )
        )


        self.collection = (
            "ut_7edc_enterprise"
        )


        self.original_get_model = (
            retrieval_service
            .get_embedding_model
        )

        self.original_get_tokenizer = (
            retrieval_service
            .get_tokenizer
        )

        self.original_count_tokens = (
            retrieval_service
            .count_tokens
        )


        retrieval_service.get_embedding_model = (
            lambda:
                _DummyModel(
                    self.vectors[0]
                )
        )


        retrieval_service.get_tokenizer = (
            lambda:
                object()
        )


        retrieval_service.count_tokens = (
            lambda text, tokenizer:
                5
        )


    def tearDown(self):

        retrieval_service.get_embedding_model = (
            self.original_get_model
        )

        retrieval_service.get_tokenizer = (
            self.original_get_tokenizer
        )

        retrieval_service.count_tokens = (
            self.original_count_tokens
        )


        close = getattr(
            self.client,
            "close",
            None,
        )

        if callable(
            close
        ):
            close()


        self.temp.cleanup()


    def _register_document(self):

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
                        self.metadata[
                            "source_sha256"
                        ],
                },

                manufacturer=
                    self.metadata.get(
                        "manufacturer"
                    ),

                plant_id=
                    "plant-7edc",

                equipment_type=
                    "motor",

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


    def _register_artifact(self):

        return (
            registry_backend
            .register_document_vector_artifact(
                {
                    "document_id":
                        self.metadata[
                            "document_id"
                        ],

                    "vector_store_filename":
                        ABB_VECTOR_FILENAME,

                    "prepared_filename":
                        self.embedding[
                            "prepared_filename"
                        ],

                    "prepared_sha256":
                        self.embedding[
                            "prepared_sha256"
                        ],

                    "vector_store_sha256":
                        self.vector_sha256,

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


    def _index(
        self,
        artifact,
    ):

        return (
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


    def test_semantic_qdrant_retrieval_hydrates_validated_evidence(self):

        self._register_document()

        artifact = (
            self._register_artifact()
        )

        self._index(
            artifact
        )


        result = (
            retrieval_service
            .retrieve_enterprise_sections_qdrant(
                self.client,

                query=
                    "motor fails to start blown fuses",

                top_k=
                    3,

                metadata_filters={
                    "manufacturer":
                        "ABB",
                },

                collection_name=
                    self.collection,

                database_path=
                    self.registry_path,
            )
        )


        self.assertEqual(
            result[
                "mode"
            ],
            "semantic_qdrant",
        )

        self.assertTrue(
            result[
                "qdrant_used"
            ]
        )

        self.assertEqual(
            result[
                "eligible_artifacts_count"
            ],
            1,
        )

        self.assertGreaterEqual(
            result[
                "results_count"
            ],
            1,
        )

        first_result = (
            result[
                "results"
            ][0]
        )


        self.assertEqual(
            first_result[
                "vector_artifact_id"
            ],
            artifact[
                "vector_artifact_id"
            ],
        )


        # Permanent contract:
        # make_result exposes the matched vector chunk as
        # matched_chunk_id, not chunk_id.
        self.assertEqual(
            first_result[
                "matched_chunk_id"
            ],
            self.metadata[
                "chunks"
            ][0][
                "chunk_id"
            ],
        )


        self.assertFalse(
            first_result[
                "similarity_is_confidence"
            ]
        )

        self.assertFalse(
            result[
                "automatic_artifact_selection"
            ]
        )


    def test_missing_qdrant_collection_fails_closed_without_creation(self):

        self._register_document()
        self._register_artifact()


        missing = (
            "ut_7edc_missing_collection"
        )


        self.assertFalse(
            self.client
            .collection_exists(
                missing
            )
        )


        with self.assertRaises(
            FileNotFoundError
        ):

            retrieval_service.retrieve_enterprise_sections_qdrant(
                self.client,

                query=
                    "motor fails to start",

                metadata_filters={
                    "manufacturer":
                        "ABB",
                },

                collection_name=
                    missing,

                database_path=
                    self.registry_path,
            )


        self.assertFalse(
            self.client
            .collection_exists(
                missing
            )
        )


    def test_ambiguous_document_is_withheld_before_model_and_qdrant(self):

        self._register_document()

        self._register_artifact()


        registry_backend.register_document_vector_artifact(
            {
                "document_id":
                    self.metadata[
                        "document_id"
                    ],

                "vector_store_filename":
                    "ut_7edc_second_artifact.npz",

                "prepared_filename":
                    self.embedding[
                        "prepared_filename"
                    ],

                "prepared_sha256":
                    self.embedding[
                        "prepared_sha256"
                    ],

                "vector_store_sha256":
                    "2" * 64,

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


        model_called = {
            "value":
                False
        }


        def forbidden_model():

            model_called[
                "value"
            ] = True

            raise RuntimeError(
                "Model must not run."
            )


        retrieval_service.get_embedding_model = (
            forbidden_model
        )


        result = (
            retrieval_service
            .retrieve_enterprise_sections_qdrant(
                self.client,

                query=
                    "motor stalls",

                metadata_filters={
                    "manufacturer":
                        "ABB",
                },

                collection_name=
                    self.collection,

                database_path=
                    self.registry_path,
            )
        )


        self.assertEqual(
            result[
                "status"
            ],
            "ambiguous",
        )

        self.assertEqual(
            result[
                "eligible_artifacts_count"
            ],
            0,
        )

        self.assertEqual(
            result[
                "results_count"
            ],
            0,
        )

        self.assertFalse(
            result[
                "qdrant_used"
            ]
        )

        self.assertFalse(
            model_called[
                "value"
            ]
        )

        self.assertFalse(
            self.client
            .collection_exists(
                self.collection
            )
        )


    def test_qdrant_cannot_return_noneligible_artifact(self):

        self._register_document()

        artifact = (
            self._register_artifact()
        )

        self._index(
            artifact
        )


        other_vector = np.zeros(
            (
                qdrant_store
                .VECTOR_SIZE,
            ),
            dtype=np.float32,
        )

        other_vector[0] = 1.0


        qdrant_store.upsert_artifact_vectors(
            self.client,

            vector_artifact_id=
                "not-registry-eligible",

            document_id=
                "other-document",

            chunk_ids=[
                "other-chunk"
            ],

            vectors=np.stack(
                [
                    other_vector
                ]
            ),

            collection_name=
                self.collection,
        )


        result = (
            retrieval_service
            .retrieve_enterprise_sections_qdrant(
                self.client,

                query=
                    "motor failure",

                top_k=
                    5,

                metadata_filters={
                    "manufacturer":
                        "ABB",
                },

                collection_name=
                    self.collection,

                database_path=
                    self.registry_path,
            )
        )


        returned = {
            item[
                "vector_artifact_id"
            ]

            for item
            in result[
                "results"
            ]
        }


        self.assertEqual(
            returned,
            {
                artifact[
                    "vector_artifact_id"
                ]
            },
        )


    def test_exact_alarm_delegates_to_existing_deterministic_path(self):

        sentinel = {
            "status":
                "found",

            "mode":
                "exact_alarm",

            "results_count":
                1,

            "results":
                [],
        }


        original = (
            retrieval_service
            .retrieve_enterprise_sections
        )


        calls = []


        def fake_existing(
            **kwargs,
        ):

            calls.append(
                kwargs
            )

            return dict(
                sentinel
            )


        retrieval_service.retrieve_enterprise_sections = (
            fake_existing
        )


        try:

            result = (
                retrieval_service
                .retrieve_enterprise_sections_qdrant(
                    self.client,

                    query=
                        "ignored",

                    alarm_number=
                        "1001",

                    top_k=
                        3,

                    metadata_filters={
                        "manufacturer":
                            "Siemens",
                    },

                    collection_name=
                        self.collection,

                    database_path=
                        self.registry_path,
                )
            )


        finally:

            retrieval_service.retrieve_enterprise_sections = (
                original
            )


        self.assertEqual(
            len(calls),
            1,
        )

        self.assertEqual(
            calls[0][
                "alarm_number"
            ],
            "1001",
        )

        self.assertEqual(
            result[
                "vector_backend"
            ],
            "deterministic_npz_exact",
        )

        self.assertFalse(
            result[
                "qdrant_used"
            ]
        )

        self.assertFalse(
            self.client
            .collection_exists(
                self.collection
            )
        )


if __name__ == "__main__":
    unittest.main()
