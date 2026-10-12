from __future__ import annotations

import inspect
import tempfile
import unittest

import numpy as np

from qdrant_client import QdrantClient

from app.services import (
    qdrant_store,
    retrieval_service,
)


class QdrantParentDedupDepthTests(
    unittest.TestCase
):

    def test_deep_query_can_read_beyond_old_25_result_boundary(
        self,
    ):

        with tempfile.TemporaryDirectory(
            prefix=
                "ta_r3b_deep_"
        ) as directory:

            client = QdrantClient(
                path=directory
            )


            try:

                collection = (
                    "ut_r3b_deep"
                )


                vectors = np.zeros(
                    (
                        40,
                        qdrant_store
                        .VECTOR_SIZE,
                    ),
                    dtype=np.float32,
                )


                for index in range(
                    40
                ):

                    vectors[
                        index,
                        index
                    ] = 1.0


                qdrant_store.upsert_artifact_vectors(
                    client,

                    vector_artifact_id=
                        "vec-r3b",

                    document_id=
                        "doc-r3b",

                    chunk_ids=[
                        f"chunk-{index:03d}"
                        for index
                        in range(
                            40
                        )
                    ],

                    vectors=
                        vectors,

                    collection_name=
                        collection,
                )


                result = (
                    qdrant_store
                    .query_eligible_artifacts_deep(
                        client,

                        query_vector=
                            vectors[
                                0
                            ],

                        eligible_vector_artifact_ids=[
                            "vec-r3b"
                        ],

                        limit=
                            40,

                        collection_name=
                            collection,
                    )
                )


                self.assertEqual(
                    result[
                        "results_count"
                    ],
                    40,
                )


                self.assertTrue(
                    result[
                        "exact_vector_search"
                    ]
                )


                self.assertFalse(
                    result[
                        "automatic_artifact_selection"
                    ]
                )


                self.assertFalse(
                    result[
                        "similarity_is_confidence"
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


    def test_deep_query_missing_collection_fails_closed(
        self,
    ):

        with tempfile.TemporaryDirectory(
            prefix=
                "ta_r3b_missing_"
        ) as directory:

            client = QdrantClient(
                path=directory
            )


            try:

                collection = (
                    "ut_r3b_missing"
                )


                vector = np.zeros(
                    (
                        qdrant_store
                        .VECTOR_SIZE,
                    ),
                    dtype=np.float32,
                )


                vector[
                    0
                ] = 1.0


                self.assertFalse(
                    client.collection_exists(
                        collection
                    )
                )


                with self.assertRaises(
                    FileNotFoundError
                ):

                    qdrant_store.query_eligible_artifacts_deep(
                        client,

                        query_vector=
                            vector,

                        eligible_vector_artifact_ids=[
                            "vec-r3b"
                        ],

                        limit=
                            30,

                        collection_name=
                            collection,
                    )


                self.assertFalse(
                    client.collection_exists(
                        collection
                    )
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


    def test_enterprise_retrieval_contains_bounded_adaptive_strategy(
        self,
    ):

        source = inspect.getsource(
            retrieval_service
            .retrieve_enterprise_sections_qdrant
        )


        self.assertIn(
            "query_eligible_artifacts_deep",
            source,
        )


        self.assertIn(
            "raw_candidate_limit * 2",
            source,
        )


        self.assertIn(
            "maximum_raw_candidates",
            source,
        )


        self.assertIn(
            "1000",
            source,
        )


        self.assertIn(
            "No NPZ fallback was used",
            source,
        )


        self.assertNotIn(
            "qdrant_limit = min(",
            source,
        )


if __name__ == "__main__":
    unittest.main()
