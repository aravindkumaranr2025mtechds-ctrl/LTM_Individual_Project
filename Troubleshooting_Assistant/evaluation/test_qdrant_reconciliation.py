from __future__ import annotations

import hashlib
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from qdrant_client import QdrantClient

from app.services import (
    qdrant_importer,
    qdrant_store,
    registry_backend,
    retrieval_service,
)


ABB_FILENAME = (
    "dde3696f00424107b1253d4dfd44a05b_"
    "ABB_LV_Motors_RevH_2022_"
    "structured_v1_ready_bge_small.npz"
)


def sha256_file(path):
    digest = hashlib.sha256()

    with Path(path).open(
        "rb"
    ) as stream:

        while True:

            block = stream.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def register_abb(
    registry_path,
):
    vectors, metadata, parents = (
        retrieval_service
        .load_vector_store(
            ABB_FILENAME
        )
    )


    embedding = metadata[
        "embedding"
    ]


    vector_path = (
        Path(
            retrieval_service
            .VECTOR_DIRECTORY
        )
        / ABB_FILENAME
    )


    registry_backend.register_enterprise_document(
        {
            "document_id":
                metadata[
                    "document_id"
                ],

            "original_filename":
                metadata[
                    "source_filename"
                ],

            "stored_filename":
                metadata[
                    "source_filename"
                ],

            "file_type":
                ".pdf",

            "file_size_bytes":
                metadata[
                    "source_size_bytes"
                ],

            "source_sha256":
                metadata[
                    "source_sha256"
                ],
        },

        manufacturer=
            "ABB",

        document_type=
            "manual",

        document_status=
            "qdrant-reconciliation-test",

        database_path=
            registry_path,
    )


    artifact = (
        registry_backend
        .register_document_vector_artifact(
            {
                "document_id":
                    metadata[
                        "document_id"
                    ],

                "vector_store_filename":
                    ABB_FILENAME,

                "prepared_filename":
                    embedding[
                        "prepared_filename"
                    ],

                "prepared_sha256":
                    embedding[
                        "prepared_sha256"
                    ],

                "vector_store_sha256":
                    sha256_file(
                        vector_path
                    ),

                "embedding_model":
                    embedding[
                        "model_name"
                    ],

                "embedding_dimension":
                    embedding[
                        "embedding_dimension"
                    ],

                "vector_count":
                    len(
                        metadata[
                            "chunks"
                        ]
                    ),

                "embedding_created_at_utc":
                    embedding[
                        "created_at_utc"
                    ],
            },

            database_path=
                registry_path,
        )
    )


    return (
        vectors,
        metadata,
        artifact,
    )


class QdrantReconciliationTests(
    unittest.TestCase
):

    def test_missing_collection_bootstraps_and_reconciles(
        self,
    ):
        with tempfile.TemporaryDirectory(
            prefix="ta_reconcile_bootstrap_"
        ) as directory:

            root = Path(
                directory
            )

            registry = (
                root
                / "registry.sqlite3"
            )

            vectors, metadata, artifact = (
                register_abb(
                    registry
                )
            )

            client = QdrantClient(
                path=str(
                    root
                    / "qdrant"
                )
            )

            try:

                collection = (
                    "ut_reconcile_bootstrap"
                )


                before = (
                    qdrant_importer
                    .inspect_registered_artifact_qdrant_state(
                        client,

                        document_id=
                            metadata[
                                "document_id"
                            ],

                        vector_artifact_id=
                            artifact[
                                "vector_artifact_id"
                            ],

                        collection_name=
                            collection,

                        database_path=
                            registry,
                    )
                )


                self.assertEqual(
                    before[
                        "state"
                    ],
                    "missing_collection",
                )


                result = (
                    qdrant_importer
                    .bootstrap_registered_npz_artifact(
                        client,

                        document_id=
                            metadata[
                                "document_id"
                            ],

                        vector_artifact_id=
                            artifact[
                                "vector_artifact_id"
                            ],

                        collection_name=
                            collection,

                        database_path=
                            registry,
                    )
                )


                self.assertEqual(
                    result[
                        "status"
                    ],
                    "bootstrapped",
                )


                self.assertEqual(
                    result[
                        "after"
                    ][
                        "state"
                    ],
                    "synchronized",
                )


                self.assertEqual(
                    result[
                        "after"
                    ][
                        "indexed_points"
                    ],
                    len(
                        metadata[
                            "chunks"
                        ]
                    ),
                )

            finally:

                client.close()


    def test_synchronized_state_is_idempotent(
        self,
    ):
        with tempfile.TemporaryDirectory(
            prefix="ta_reconcile_idempotent_"
        ) as directory:

            root = Path(
                directory
            )

            registry = (
                root
                / "registry.sqlite3"
            )

            vectors, metadata, artifact = (
                register_abb(
                    registry
                )
            )

            client = QdrantClient(
                path=str(
                    root
                    / "qdrant"
                )
            )

            try:

                collection = (
                    "ut_reconcile_idempotent"
                )


                qdrant_importer.bootstrap_registered_npz_artifact(
                    client,

                    document_id=
                        metadata[
                            "document_id"
                        ],

                    vector_artifact_id=
                        artifact[
                            "vector_artifact_id"
                        ],

                    collection_name=
                        collection,

                    database_path=
                        registry,
                )


                with patch.object(
                    qdrant_importer,
                    "import_registered_npz_artifact",
                    side_effect=
                        AssertionError(
                            "Synchronized artifact was reimported."
                        ),
                ):

                    result = (
                        qdrant_importer
                        .bootstrap_registered_npz_artifact(
                            client,

                            document_id=
                                metadata[
                                    "document_id"
                                ],

                            vector_artifact_id=
                                artifact[
                                    "vector_artifact_id"
                                ],

                            collection_name=
                                collection,

                            database_path=
                                registry,
                        )
                    )


                self.assertEqual(
                    result[
                        "status"
                    ],
                    "already_synchronized",
                )


                self.assertFalse(
                    result[
                        "write_performed"
                    ]
                )

            finally:

                client.close()


    def test_partial_state_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory(
            prefix="ta_reconcile_partial_"
        ) as directory:

            root = Path(
                directory
            )

            registry = (
                root
                / "registry.sqlite3"
            )

            vectors, metadata, artifact = (
                register_abb(
                    registry
                )
            )

            client = QdrantClient(
                path=str(
                    root
                    / "qdrant"
                )
            )

            try:

                collection = (
                    "ut_reconcile_partial"
                )


                first_chunk = (
                    metadata[
                        "chunks"
                    ][0]
                )


                qdrant_store.upsert_artifact_vectors(
                    client,

                    vector_artifact_id=
                        artifact[
                            "vector_artifact_id"
                        ],

                    document_id=
                        metadata[
                            "document_id"
                        ],

                    chunk_ids=[
                        first_chunk[
                            "chunk_id"
                        ]
                    ],

                    vectors=
                        vectors[:1],

                    collection_name=
                        collection,
                )


                before = (
                    qdrant_importer
                    .inspect_registered_artifact_qdrant_state(
                        client,

                        document_id=
                            metadata[
                                "document_id"
                            ],

                        vector_artifact_id=
                            artifact[
                                "vector_artifact_id"
                            ],

                        collection_name=
                            collection,

                        database_path=
                            registry,
                    )
                )


                self.assertEqual(
                    before[
                        "state"
                    ],
                    "point_count_mismatch",
                )


                with self.assertRaises(
                    RuntimeError
                ):

                    qdrant_importer.bootstrap_registered_npz_artifact(
                        client,

                        document_id=
                            metadata[
                                "document_id"
                            ],

                        vector_artifact_id=
                            artifact[
                                "vector_artifact_id"
                            ],

                        collection_name=
                            collection,

                        database_path=
                            registry,
                    )


                after = (
                    qdrant_importer
                    .inspect_registered_artifact_qdrant_state(
                        client,

                        document_id=
                            metadata[
                                "document_id"
                            ],

                        vector_artifact_id=
                            artifact[
                                "vector_artifact_id"
                            ],

                        collection_name=
                            collection,

                        database_path=
                            registry,
                    )
                )


                self.assertEqual(
                    after[
                        "indexed_points"
                    ],
                    1,
                )


                self.assertEqual(
                    after[
                        "state"
                    ],
                    "point_count_mismatch",
                )

            finally:

                client.close()


    def test_payload_mismatch_fails_closed(
        self,
    ):
        with tempfile.TemporaryDirectory(
            prefix="ta_reconcile_payload_"
        ) as directory:

            root = Path(
                directory
            )

            registry = (
                root
                / "registry.sqlite3"
            )

            vectors, metadata, artifact = (
                register_abb(
                    registry
                )
            )

            client = QdrantClient(
                path=str(
                    root
                    / "qdrant"
                )
            )

            try:

                collection = (
                    "ut_reconcile_payload"
                )


                qdrant_importer.bootstrap_registered_npz_artifact(
                    client,

                    document_id=
                        metadata[
                            "document_id"
                        ],

                    vector_artifact_id=
                        artifact[
                            "vector_artifact_id"
                        ],

                    collection_name=
                        collection,

                    database_path=
                        registry,
                )


                first_chunk = (
                    metadata[
                        "chunks"
                    ][0]
                )


                qdrant_store.upsert_artifact_vectors(
                    client,

                    vector_artifact_id=
                        artifact[
                            "vector_artifact_id"
                        ],

                    document_id=
                        "wrong-document-id",

                    chunk_ids=[
                        first_chunk[
                            "chunk_id"
                        ]
                    ],

                    vectors=
                        vectors[:1],

                    collection_name=
                        collection,
                )


                inspected = (
                    qdrant_importer
                    .inspect_registered_artifact_qdrant_state(
                        client,

                        document_id=
                            metadata[
                                "document_id"
                            ],

                        vector_artifact_id=
                            artifact[
                                "vector_artifact_id"
                            ],

                        collection_name=
                            collection,

                        database_path=
                            registry,
                    )
                )


                self.assertEqual(
                    inspected[
                        "state"
                    ],
                    "payload_mismatch",
                )


                with self.assertRaises(
                    RuntimeError
                ):

                    qdrant_importer.bootstrap_registered_npz_artifact(
                        client,

                        document_id=
                            metadata[
                                "document_id"
                            ],

                        vector_artifact_id=
                            artifact[
                                "vector_artifact_id"
                            ],

                        collection_name=
                            collection,

                        database_path=
                            registry,
                    )

            finally:

                client.close()


    def test_unknown_artifact_does_not_create_collection(
        self,
    ):
        with tempfile.TemporaryDirectory(
            prefix="ta_reconcile_unknown_"
        ) as directory:

            root = Path(
                directory
            )

            registry = (
                root
                / "registry.sqlite3"
            )

            vectors, metadata, artifact = (
                register_abb(
                    registry
                )
            )

            client = QdrantClient(
                path=str(
                    root
                    / "qdrant"
                )
            )

            try:

                collection = (
                    "ut_reconcile_unknown"
                )


                self.assertFalse(
                    client.collection_exists(
                        collection
                    )
                )


                with self.assertRaises(
                    ValueError
                ):

                    qdrant_importer.bootstrap_registered_npz_artifact(
                        client,

                        document_id=
                            metadata[
                                "document_id"
                            ],

                        vector_artifact_id=
                            "unknown-artifact",

                        collection_name=
                            collection,

                        database_path=
                            registry,
                    )


                self.assertFalse(
                    client.collection_exists(
                        collection
                    )
                )

            finally:

                client.close()


if __name__ == "__main__":
    unittest.main()
