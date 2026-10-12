from __future__ import annotations

import os
import tempfile
import unittest

from pathlib import Path

from app.services import qdrant_store


ENV_NAMES = (
    qdrant_store.VECTOR_RETRIEVAL_BACKEND_ENV,
    qdrant_store.QDRANT_PATH_ENV,
    qdrant_store.QDRANT_COLLECTION_ENV,
)


class QdrantApplicationConfigTests(
    unittest.TestCase
):

    def setUp(self):

        qdrant_store.close_application_qdrant_client()

        self.original = {
            name: os.environ.get(name)
            for name in ENV_NAMES
        }


        for name in ENV_NAMES:

            os.environ.pop(
                name,
                None,
            )


    def tearDown(self):

        qdrant_store.close_application_qdrant_client()


        for name, value in self.original.items():

            if value is None:

                os.environ.pop(
                    name,
                    None,
                )

            else:

                os.environ[name] = value


    def test_default_backend_is_npz_and_does_not_create_qdrant(
        self,
    ):

        self.assertEqual(
            qdrant_store.get_vector_retrieval_backend(),
            "npz",
        )


        default_path = (
            qdrant_store.DEFAULT_APPLICATION_QDRANT_PATH
        )


        existed_before = (
            default_path.exists()
        )


        with self.assertRaises(
            RuntimeError
        ):

            qdrant_store.get_application_qdrant_client()


        self.assertEqual(
            default_path.exists(),
            existed_before,
        )


    def test_explicit_qdrant_backend_is_accepted(
        self,
    ):

        os.environ[
            qdrant_store.VECTOR_RETRIEVAL_BACKEND_ENV
        ] = "QDRANT"


        self.assertEqual(
            qdrant_store.get_vector_retrieval_backend(),
            "qdrant",
        )


    def test_unknown_and_blank_backends_fail_closed(
        self,
    ):

        os.environ[
            qdrant_store.VECTOR_RETRIEVAL_BACKEND_ENV
        ] = "milvus"


        with self.assertRaises(
            ValueError
        ):

            qdrant_store.get_vector_retrieval_backend()


        os.environ[
            qdrant_store.VECTOR_RETRIEVAL_BACKEND_ENV
        ] = "   "


        with self.assertRaises(
            ValueError
        ):

            qdrant_store.get_vector_retrieval_backend()


    def test_qdrant_path_requires_absolute_path(
        self,
    ):

        os.environ[
            qdrant_store.QDRANT_PATH_ENV
        ] = "data/relative-qdrant"


        with self.assertRaises(
            ValueError
        ):

            qdrant_store.get_application_qdrant_path()


    def test_collection_name_is_trusted_and_validated(
        self,
    ):

        self.assertEqual(
            qdrant_store.get_application_qdrant_collection_name(),
            qdrant_store.DEFAULT_COLLECTION_NAME,
        )


        os.environ[
            qdrant_store.QDRANT_COLLECTION_ENV
        ] = "industrial_test_v1"


        self.assertEqual(
            qdrant_store.get_application_qdrant_collection_name(),
            "industrial_test_v1",
        )


        os.environ[
            qdrant_store.QDRANT_COLLECTION_ENV
        ] = "../../unsafe"


        with self.assertRaises(
            ValueError
        ):

            qdrant_store.get_application_qdrant_collection_name()


    def test_application_client_is_process_owned_and_path_change_fails_closed(
        self,
    ):

        with tempfile.TemporaryDirectory(
            prefix="ta_qdrant_provider_"
        ) as directory:

            root = (
                Path(
                    directory
                )
                .resolve()
            )


            first_path = (
                root
                / "first"
            )


            second_path = (
                root
                / "second"
            )


            os.environ[
                qdrant_store.VECTOR_RETRIEVAL_BACKEND_ENV
            ] = "qdrant"


            os.environ[
                qdrant_store.QDRANT_PATH_ENV
            ] = str(
                first_path
            )


            first_client = (
                qdrant_store.get_application_qdrant_client()
            )


            same_client = (
                qdrant_store.get_application_qdrant_client()
            )


            self.assertIs(
                first_client,
                same_client,
            )


            self.assertTrue(
                first_path.exists()
            )


            os.environ[
                qdrant_store.QDRANT_PATH_ENV
            ] = str(
                second_path
            )


            with self.assertRaises(
                RuntimeError
            ):

                qdrant_store.get_application_qdrant_client()


            self.assertFalse(
                second_path.exists()
            )


            self.assertTrue(
                qdrant_store.close_application_qdrant_client()
            )


            self.assertFalse(
                qdrant_store.close_application_qdrant_client()
            )


            replacement = (
                qdrant_store.get_application_qdrant_client()
            )


            self.assertIsNotNone(
                replacement
            )


            self.assertTrue(
                second_path.exists()
            )


            # Windows/local-Qdrant holds a .lock file while
            # the client is open. Close it BEFORE leaving the
            # TemporaryDirectory context.
            self.assertTrue(
                qdrant_store.close_application_qdrant_client()
            )


            self.assertFalse(
                qdrant_store.close_application_qdrant_client()
            )


if __name__ == "__main__":
    unittest.main()
