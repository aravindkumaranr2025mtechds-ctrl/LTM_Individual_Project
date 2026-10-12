from __future__ import annotations

import tempfile
import unittest

from pathlib import Path

import numpy as np

from qdrant_client import (
    QdrantClient,
)

from app.services import (
    embedding_service,
    qdrant_store,
)


class QdrantStoreTests(
    unittest.TestCase
):

    def setUp(self):

        self._temporary = (
            tempfile.TemporaryDirectory(
                prefix=
                    "ta_qdrant_store_test_"
            )
        )

        self.path = Path(
            self._temporary.name
        )

        self.client = QdrantClient(
            path=str(
                self.path
            )
        )

        self.collection = (
            "ut_industrial_dense"
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

            if callable(
                close
            ):
                close()

        self.client = None

        self._temporary.cleanup()


    @staticmethod
    def _unit_vector(index):

        vector = np.zeros(
            (
                qdrant_store
                .VECTOR_SIZE,
            ),
            dtype=np.float32,
        )

        vector[index] = 1.0

        return vector


    def test_collection_contract_matches_embedding_model(self):

        self.assertEqual(
            qdrant_store
            .VECTOR_SIZE,

            embedding_service
            .EMBEDDING_DIMENSION,
        )

        info = (
            qdrant_store
            .ensure_dense_collection(
                self.client,
                collection_name=
                    self.collection,
            )
        )

        vectors = (
            info.config.params.vectors
        )

        self.assertEqual(
            vectors.size,
            384,
        )

        self.assertEqual(
            vectors.distance,
            qdrant_store
            .VECTOR_DISTANCE,
        )


    def test_deterministic_point_identity(self):

        first = (
            qdrant_store
            .deterministic_point_id(
                vector_artifact_id=
                    "vec-test-001",

                chunk_id=
                    "chunk-001",
            )
        )

        second = (
            qdrant_store
            .deterministic_point_id(
                vector_artifact_id=
                    "vec-test-001",

                chunk_id=
                    "chunk-001",
            )
        )

        different = (
            qdrant_store
            .deterministic_point_id(
                vector_artifact_id=
                    "vec-test-001",

                chunk_id=
                    "chunk-002",
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertNotEqual(
            first,
            different,
        )


    def test_query_is_bounded_to_explicit_eligible_artifacts(self):

        vector_a = self._unit_vector(
            0
        )

        vector_b = self._unit_vector(
            1
        )

        qdrant_store.upsert_artifact_vectors(
            self.client,

            vector_artifact_id=
                "vec-artifact-a",

            document_id=
                "document-a",

            chunk_ids=[
                "chunk-a",
            ],

            vectors=np.stack(
                [
                    vector_a,
                ]
            ),

            collection_name=
                self.collection,
        )

        qdrant_store.upsert_artifact_vectors(
            self.client,

            vector_artifact_id=
                "vec-artifact-b",

            document_id=
                "document-b",

            chunk_ids=[
                "chunk-b",
            ],

            vectors=np.stack(
                [
                    vector_b,
                ]
            ),

            collection_name=
                self.collection,
        )

        # vector-a is the perfect semantic match,
        # but Registry eligibility supplies only artifact-b.
        result = (
            qdrant_store
            .query_eligible_artifacts(
                self.client,

                query_vector=
                    vector_a,

                eligible_vector_artifact_ids=[
                    "vec-artifact-b",
                ],

                limit=5,

                collection_name=
                    self.collection,
            )
        )

        self.assertEqual(
            result[
                "results_count"
            ],
            1,
        )

        self.assertEqual(
            result[
                "results"
            ][0][
                "vector_artifact_id"
            ],
            "vec-artifact-b",
        )

        self.assertEqual(
            result[
                "results"
            ][0][
                "document_id"
            ],
            "document-b",
        )

        self.assertFalse(
            result[
                "automatic_artifact_selection"
            ]
        )

        self.assertFalse(
            result[
                "results"
            ][0][
                "similarity_is_confidence"
            ]
        )


    def test_qdrant_payload_excludes_access_level(self):

        vector = self._unit_vector(
            5
        )

        qdrant_store.upsert_artifact_vectors(
            self.client,

            vector_artifact_id=
                "vec-payload-test",

            document_id=
                "document-payload-test",

            chunk_ids=[
                "chunk-payload-test",
            ],

            vectors=np.stack(
                [
                    vector,
                ]
            ),

            collection_name=
                self.collection,
        )

        result = (
            qdrant_store
            .query_eligible_artifacts(
                self.client,

                query_vector=
                    vector,

                eligible_vector_artifact_ids=[
                    "vec-payload-test",
                ],

                collection_name=
                    self.collection,
            )
        )

        self.assertEqual(
            result[
                "results_count"
            ],
            1,
        )

        self.assertNotIn(
            "access_level",
            result[
                "results"
            ][0],
        )


    def test_wrong_vector_dimension_is_rejected(self):

        wrong = np.zeros(
            (
                1,
                383,
            ),
            dtype=np.float32,
        )

        wrong[0, 0] = 1.0

        with self.assertRaises(
            ValueError
        ):

            qdrant_store.upsert_artifact_vectors(
                self.client,

                vector_artifact_id=
                    "vec-wrong-dimension",

                document_id=
                    "document-wrong-dimension",

                chunk_ids=[
                    "chunk-wrong-dimension",
                ],

                vectors=
                    wrong,

                collection_name=
                    self.collection,
            )


    def test_empty_eligible_artifact_set_is_rejected(self):

        vector = self._unit_vector(
            10
        )

        with self.assertRaises(
            ValueError
        ):

            qdrant_store.query_eligible_artifacts(
                self.client,

                query_vector=
                    vector,

                eligible_vector_artifact_ids=[],

                collection_name=
                    self.collection,
            )


    def test_local_qdrant_persistence(self):

        vector = self._unit_vector(
            12
        )

        qdrant_store.upsert_artifact_vectors(
            self.client,

            vector_artifact_id=
                "vec-persistent",

            document_id=
                "document-persistent",

            chunk_ids=[
                "chunk-persistent",
            ],

            vectors=np.stack(
                [
                    vector,
                ]
            ),

            collection_name=
                self.collection,
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

        self.client = None


        reopened = QdrantClient(
            path=str(
                self.path
            )
        )

        try:

            result = (
                qdrant_store
                .query_eligible_artifacts(
                    reopened,

                    query_vector=
                        vector,

                    eligible_vector_artifact_ids=[
                        "vec-persistent",
                    ],

                    collection_name=
                        self.collection,
                )
            )

            self.assertEqual(
                result[
                    "results_count"
                ],
                1,
            )

            self.assertEqual(
                result[
                    "results"
                ][0][
                    "vector_artifact_id"
                ],
                "vec-persistent",
            )

        finally:

            close = getattr(
                reopened,
                "close",
                None,
            )

            if callable(
                close
            ):
                close()



    def test_query_missing_collection_does_not_create_it(self):

        vector = self._unit_vector(
            20
        )

        missing_collection = (
            "ut_missing_read_only_collection"
        )

        self.assertFalse(
            self.client.collection_exists(
                missing_collection
            )
        )

        with self.assertRaises(
            FileNotFoundError
        ):

            qdrant_store.query_eligible_artifacts(
                self.client,

                query_vector=
                    vector,

                eligible_vector_artifact_ids=[
                    "vec-explicit-eligible"
                ],

                collection_name=
                    missing_collection,
            )

        self.assertFalse(
            self.client.collection_exists(
                missing_collection
            )
        )

if __name__ == "__main__":
    unittest.main()
