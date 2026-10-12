from __future__ import annotations

import hashlib
import tempfile
import unittest
import uuid

from pathlib import Path

import numpy as np

from qdrant_client import QdrantClient

from app.services import (
    qdrant_importer,
    registry_backend,
    retrieval_service,
)


CANONICAL = (
    "212022f0a2614a7b839cc827522c6651_"
    "MC_diagnostics_man_0724_en-US_"
    "chunks_ready_bge_small.npz"
)


V2 = (
    "212022f0a2614a7b839cc827522c6651_"
    "MC_diagnostics_man_0724_en-US_"
    "chunks_v2_ready_bge_small.npz"
)


ABB = (
    "dde3696f00424107b1253d4dfd44a05b_"
    "ABB_LV_Motors_RevH_2022_"
    "structured_v1_ready_bge_small.npz"
)


EXPECTED_SOURCE_SHA = (
    "67dc7754e59856b4f0df012603c84432"
    "242b6a02c9d38dfaf4328bd7e052cd39"
)


EXPECTED_SOURCE_SIZE = 4722058


class LegacyVectorProvenanceMigrationTests(
    unittest.TestCase
):

    def setUp(self):

        self.outputs = []


    def tearDown(self):

        for filename in self.outputs:

            path = (
                Path(
                    retrieval_service
                    .VECTOR_DIRECTORY
                )
                / filename
            )

            path.unlink(
                missing_ok=True
            )


    def _output_name(
        self,
        prefix,
    ):

        name = (
            "ut_"
            + prefix
            + "_"
            + uuid.uuid4().hex
            + ".npz"
        )

        self.outputs.append(
            name
        )

        return name


    def _migrate(
        self,
        source,
        prefix,
    ):

        return (
            qdrant_importer
            .create_legacy_source_attested_vector_copy(
                source,

                output_filename=
                    self._output_name(
                        prefix
                    ),
            )
        )


    def test_canonical_migration_preserves_vectors_and_adds_source_provenance(self):

        original_vectors, original_metadata, _ = (
            retrieval_service
            .load_vector_store(
                CANONICAL
            )
        )


        result = self._migrate(
            CANONICAL,
            "canonical",
        )


        migrated_vectors, migrated_metadata, _ = (
            retrieval_service
            .load_vector_store(
                result[
                    "vector_store_filename"
                ]
            )
        )


        self.assertTrue(
            np.array_equal(
                original_vectors,
                migrated_vectors,
            )
        )


        self.assertEqual(
            migrated_metadata[
                "source_sha256"
            ],
            EXPECTED_SOURCE_SHA,
        )


        self.assertEqual(
            migrated_metadata[
                "source_size_bytes"
            ],
            EXPECTED_SOURCE_SIZE,
        )


        self.assertEqual(
            migrated_metadata[
                "embedding"
            ],
            original_metadata[
                "embedding"
            ],
        )


        self.assertEqual(
            migrated_metadata[
                "chunks"
            ],
            original_metadata[
                "chunks"
            ],
        )


        self.assertEqual(
            migrated_metadata[
                "parents"
            ],
            original_metadata[
                "parents"
            ],
        )


        self.assertFalse(
            result[
                "vectors_reembedded"
            ]
        )


        self.assertFalse(
            result[
                "vector_values_changed"
            ]
        )


    def test_v2_migration_preserves_vectors_and_adds_same_source_provenance(self):

        original_vectors, _, _ = (
            retrieval_service
            .load_vector_store(
                V2
            )
        )


        result = self._migrate(
            V2,
            "v2",
        )


        migrated_vectors, migrated_metadata, _ = (
            retrieval_service
            .load_vector_store(
                result[
                    "vector_store_filename"
                ]
            )
        )


        self.assertTrue(
            np.array_equal(
                original_vectors,
                migrated_vectors,
            )
        )


        self.assertEqual(
            migrated_metadata[
                "source_sha256"
            ],
            EXPECTED_SOURCE_SHA,
        )


        self.assertEqual(
            migrated_metadata[
                "source_size_bytes"
            ],
            EXPECTED_SOURCE_SIZE,
        )


        self.assertEqual(
            result[
                "vector_count"
            ],
            2849,
        )


    def test_provenance_aware_artifact_is_not_migrated_again(self):

        output = (
            self._output_name(
                "should_not_exist"
            )
        )


        with self.assertRaises(
            ValueError
        ):

            qdrant_importer.create_legacy_source_attested_vector_copy(
                ABB,

                output_filename=
                    output,
            )


        self.assertFalse(
            (
                Path(
                    retrieval_service
                    .VECTOR_DIRECTORY
                )
                / output
            ).exists()
        )


    def test_existing_output_is_never_overwritten(self):

        output = (
            self._output_name(
                "collision"
            )
        )


        output_path = (
            Path(
                retrieval_service
                .VECTOR_DIRECTORY
            )
            / output
        )


        output_path.write_bytes(
            b"do-not-overwrite"
        )


        original_bytes = (
            output_path
            .read_bytes()
        )


        with self.assertRaises(
            FileExistsError
        ):

            qdrant_importer.create_legacy_source_attested_vector_copy(
                CANONICAL,

                output_filename=
                    output,
            )


        self.assertEqual(
            output_path.read_bytes(),
            original_bytes,
        )


    def test_strict_existing_importer_accepts_migrated_copy(self):

        migration = self._migrate(
            CANONICAL,
            "import",
        )


        (
            vectors,
            metadata,
            _,
        ) = (
            retrieval_service
            .load_vector_store(
                migration[
                    "vector_store_filename"
                ]
            )
        )


        embedding = (
            metadata[
                "embedding"
            ]
        )


        with tempfile.TemporaryDirectory(
            prefix=
                "ta_legacy_provenance_registry_"
        ) as directory:

            root = Path(
                directory
            )


            registry_path = (
                root
                / "registry.sqlite3"
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
                    "Siemens",

                document_type=
                    "manual",

                document_status=
                    "migration-test-only",

                database_path=
                    registry_path,
            )


            vector_path = (
                Path(
                    retrieval_service
                    .VECTOR_DIRECTORY
                )
                / migration[
                    "vector_store_filename"
                ]
            )


            vector_sha = hashlib.sha256(
                vector_path.read_bytes()
            ).hexdigest()


            artifact = (
                registry_backend
                .register_document_vector_artifact(
                    {
                        "document_id":
                            metadata[
                                "document_id"
                            ],

                        "vector_store_filename":
                            migration[
                                "vector_store_filename"
                            ],

                        "prepared_filename":
                            embedding[
                                "prepared_filename"
                            ],

                        "prepared_sha256":
                            embedding[
                                "prepared_sha256"
                            ],

                        "vector_store_sha256":
                            vector_sha,

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


            qdrant_path = (
                root
                / "qdrant"
            )


            client = QdrantClient(
                path=str(
                    qdrant_path
                )
            )


            try:

                result = (
                    qdrant_importer
                    .import_registered_npz_artifact(
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
                            "ut_legacy_import",

                        database_path=
                            registry_path,
                    )
                )


                self.assertEqual(
                    result[
                        "points_count"
                    ],
                    vectors.shape[
                        0
                    ],
                )


                self.assertTrue(
                    result[
                        "source_sha256_verified"
                    ]
                )


            finally:

                close = getattr(
                    client,
                    "close",
                    None,
                )

                if callable(
                    close
                ):
                    close()


if __name__ == "__main__":
    unittest.main()
