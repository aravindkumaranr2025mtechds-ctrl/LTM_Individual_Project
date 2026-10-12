from __future__ import annotations

import copy
import unittest


from app.services.grounded_evidence_bundle import (
    build_grounded_evidence_bundle,
)


def exact_retrieval():

    return {
        "document_id":
            "siemens-manual",

        "source_filename":
            "siemens.pdf",

        "mode":
            "exact_alarm",

        "status":
            "found",

        "results_count":
            1,

        "results": [
            {
                "alarm_number":
                    "10653",

                "alarm_title":
                    "Axis gantry error threshold exceeded",

                "page_numbers":
                    [130, 131],

                "text":
                    (
                        "10653 Axis gantry error threshold exceeded. "
                        "Remedy: Check axis."
                    ),

                "cosine_similarity":
                    None,
            }
        ],
    }


def exact_sufficiency():

    return {
        "status":
            "sufficient",

        "allow_grounded_synthesis":
            True,

        "requires_relevance_assessment":
            False,
    }


def semantic_retrieval():

    return {
        "mode":
            "semantic",

        "status":
            "candidates",

        "results_count":
            3,

        "results": [
            {
                "document_id":
                    "abb-manual",

                "source_filename":
                    "abb.pdf",

                "page_numbers":
                    [25],

                "possible_cause":
                    "One phase may be open.",

                "manufacturer_guidance":
                    "Check lines for open phase.",

                "cosine_similarity":
                    0.95,
            },
            {
                "document_id":
                    "abb-manual",

                "source_filename":
                    "abb.pdf",

                "page_numbers":
                    [25],

                "possible_cause":
                    "Wrong application.",

                "manufacturer_guidance":
                    "Review the application.",

                "cosine_similarity":
                    0.93,
            },
            {
                "document_id":
                    "abb-manual",

                "source_filename":
                    "abb.pdf",

                "page_numbers":
                    [26],

                "possible_cause":
                    "Overload.",

                "manufacturer_guidance":
                    "Check load condition.",

                "cosine_similarity":
                    0.90,
            },
        ],
    }


def semantic_hold():

    return {
        "status":
            "semantic_relevance_required",

        "allow_grounded_synthesis":
            False,

        "requires_relevance_assessment":
            True,
    }


def semantic_relevant(
    indexes=None,
):

    return {
        "status":
            "relevant",

        "allow_grounded_synthesis":
            True,

        "matched_result_indexes":
            (
                [0]
                if indexes is None
                else indexes
            ),
    }


class GroundedEvidenceBundleTests(
    unittest.TestCase
):

    def test_exact_ready_evidence_builds_bundle(
        self,
    ):

        bundle = (
            build_grounded_evidence_bundle(
                exact_retrieval(),
                exact_sufficiency(),
            )
        )

        self.assertEqual(
            bundle[
                "schema_version"
            ],
            "grounded_evidence_bundle_v1",
        )

        self.assertEqual(
            bundle[
                "evidence_count"
            ],
            1,
        )

        self.assertTrue(
            bundle[
                "evidence_ids"
        ][
            0
        ].startswith(
            "ev-"
        ))


    def test_stable_id_is_deterministic(
        self,
    ):

        first = (
            build_grounded_evidence_bundle(
                exact_retrieval(),
                exact_sufficiency(),
            )
        )

        second = (
            build_grounded_evidence_bundle(
                exact_retrieval(),
                exact_sufficiency(),
            )
        )

        self.assertEqual(
            first[
                "evidence_ids"
            ],
            second[
                "evidence_ids"
            ],
        )


    def test_source_change_changes_stable_id(
        self,
    ):

        first_source = (
            exact_retrieval()
        )

        second_source = (
            exact_retrieval()
        )

        second_source[
            "results"
        ][
            0
        ][
            "text"
        ] += " Additional source text."


        first = (
            build_grounded_evidence_bundle(
                first_source,
                exact_sufficiency(),
            )
        )

        second = (
            build_grounded_evidence_bundle(
                second_source,
                exact_sufficiency(),
            )
        )

        self.assertNotEqual(
            first[
                "evidence_ids"
            ],
            second[
                "evidence_ids"
            ],
        )


    def test_semantic_bundle_contains_only_relevant_indexes(
        self,
    ):

        bundle = (
            build_grounded_evidence_bundle(
                semantic_retrieval(),
                semantic_hold(),
                semantic_relevant(
                    [0, 2]
                ),
            )
        )

        self.assertEqual(
            bundle[
                "evidence_count"
            ],
            2,
        )

        self.assertEqual(
            [
                item[
                    "source_result_index"
                ]

                for item
                in bundle[
                    "items"
                ]
            ],
            [0, 2],
        )


    def test_semantic_hold_requires_relevance_assessment(
        self,
    ):

        with self.assertRaisesRegex(
            ValueError,
            "Semantic relevance assessment is required",
        ):

            build_grounded_evidence_bundle(
                semantic_retrieval(),
                semantic_hold(),
                None,
            )


    def test_uncertain_semantic_result_cannot_be_packaged(
        self,
    ):

        relevance = {
            "status":
                "uncertain",

            "allow_grounded_synthesis":
                False,

            "matched_result_indexes":
                [0],
        }


        with self.assertRaisesRegex(
            ValueError,
            "does not permit grounded synthesis",
        ):

            build_grounded_evidence_bundle(
                semantic_retrieval(),
                semantic_hold(),
                relevance,
            )


    def test_insufficient_evidence_cannot_be_packaged(
        self,
    ):

        sufficiency = {
            "status":
                "insufficient",

            "allow_grounded_synthesis":
                False,

            "requires_relevance_assessment":
                False,
        }


        with self.assertRaisesRegex(
            ValueError,
            "does not permit grounded synthesis",
        ):

            build_grounded_evidence_bundle(
                exact_retrieval(),
                sufficiency,
            )


    def test_missing_document_identity_rejected(
        self,
    ):

        retrieval = (
            exact_retrieval()
        )

        retrieval.pop(
            "document_id"
        )

        retrieval[
            "results"
        ][
            0
        ].pop(
            "document_id",
            None,
        )


        with self.assertRaisesRegex(
            ValueError,
            "missing document identity",
        ):

            build_grounded_evidence_bundle(
                retrieval,
                exact_sufficiency(),
            )


    def test_missing_source_pages_rejected(
        self,
    ):

        retrieval = (
            exact_retrieval()
        )

        retrieval[
            "results"
        ][
            0
        ][
            "page_numbers"
        ] = []


        with self.assertRaisesRegex(
            ValueError,
            "missing attributable source pages",
        ):

            build_grounded_evidence_bundle(
                retrieval,
                exact_sufficiency(),
            )


    def test_missing_evidence_text_rejected(
        self,
    ):

        retrieval = (
            exact_retrieval()
        )

        retrieval[
            "results"
        ][
            0
        ][
            "text"
        ] = ""


        with self.assertRaisesRegex(
            ValueError,
            "missing source-supported text",
        ):

            build_grounded_evidence_bundle(
                retrieval,
                exact_sufficiency(),
            )


    def test_structured_cause_and_guidance_are_packaged(
        self,
    ):

        bundle = (
            build_grounded_evidence_bundle(
                semantic_retrieval(),
                semantic_hold(),
                semantic_relevant(),
            )
        )

        content = (
            bundle[
                "items"
            ][
                0
            ][
                "content"
            ]
        )

        self.assertIn(
            "One phase may be open.",
            content,
        )

        self.assertIn(
            "Check lines for open phase.",
            content,
        )


    def test_similarity_values_are_not_exposed(
        self,
    ):

        bundle = (
            build_grounded_evidence_bundle(
                semantic_retrieval(),
                semantic_hold(),
                semantic_relevant(),
            )
        )

        serialized = repr(
            bundle
        )

        self.assertNotIn(
            "cosine_similarity",
            serialized,
        )

        self.assertNotIn(
            "0.95",
            serialized,
        )

        self.assertFalse(
            bundle[
                "similarity_values_exposed"
            ]
        )

        self.assertFalse(
            bundle[
                "similarity_used_as_confidence"
            ]
        )


    def test_invalid_semantic_result_index_rejected(
        self,
    ):

        with self.assertRaisesRegex(
            ValueError,
            "invalid result index",
        ):

            build_grounded_evidence_bundle(
                semantic_retrieval(),
                semantic_hold(),
                semantic_relevant(
                    [99]
                ),
            )


    def test_duplicate_semantic_indexes_are_deduplicated(
        self,
    ):

        bundle = (
            build_grounded_evidence_bundle(
                semantic_retrieval(),
                semantic_hold(),
                semantic_relevant(
                    [0, 0]
                ),
            )
        )

        self.assertEqual(
            bundle[
                "evidence_count"
            ],
            1,
        )


    def test_bundle_does_not_mutate_inputs(
        self,
    ):

        retrieval = (
            semantic_retrieval()
        )

        sufficiency = (
            semantic_hold()
        )

        relevance = (
            semantic_relevant()
        )

        originals = (
            copy.deepcopy(
                retrieval
            ),
            copy.deepcopy(
                sufficiency
            ),
            copy.deepcopy(
                relevance
            ),
        )


        build_grounded_evidence_bundle(
            retrieval,
            sufficiency,
            relevance,
        )


        self.assertEqual(
            retrieval,
            originals[0],
        )

        self.assertEqual(
            sufficiency,
            originals[1],
        )

        self.assertEqual(
            relevance,
            originals[2],
        )


    def test_non_dictionary_retrieval_rejected(
        self,
    ):

        with self.assertRaises(
            TypeError
        ):

            build_grounded_evidence_bundle(
                [],
                exact_sufficiency(),
            )


    def test_non_dictionary_sufficiency_rejected(
        self,
    ):

        with self.assertRaises(
            TypeError
        ):

            build_grounded_evidence_bundle(
                exact_retrieval(),
                [],
            )


    def test_safety_flags_remain_false(
        self,
    ):

        bundle = (
            build_grounded_evidence_bundle(
                exact_retrieval(),
                exact_sufficiency(),
            )
        )

        self.assertFalse(
            bundle[
                "diagnosis_confirmed"
            ]
        )

        self.assertFalse(
            bundle[
                "approved_for_automatic_execution"
            ]
        )


if __name__ == "__main__":
    unittest.main()
