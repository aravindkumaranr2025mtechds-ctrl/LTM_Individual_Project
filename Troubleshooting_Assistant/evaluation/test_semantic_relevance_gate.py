from __future__ import annotations

import copy
import unittest


from app.services.semantic_relevance_gate import (
    assess_semantic_relevance,
)


def semantic_result(
    *,
    text,
    similarity=0.91,
):
    return {
        "mode":
            "semantic",

        "status":
            "candidates",

        "results_count":
            1,

        "message":
            (
                "Ranked source candidates, not verified answers. "
                "Similarity is not confidence."
            ),

        "results": [
            {
                "rank":
                    1,

                "document_id":
                    "manual",

                "page_numbers":
                    [25],

                "text":
                    text,

                "cosine_similarity":
                    similarity,
            }
        ],
    }


class SemanticRelevanceGateTests(
    unittest.TestCase
):

    def test_explicit_alarm_identifier_is_relevant(
        self,
    ):

        result = assess_semantic_relevance(
            "Siemens alarm 10653 gantry error",
            semantic_result(
                text=(
                    "10653 Axis gantry error threshold exceeded. "
                    "Remedy: Check axis."
                )
            ),
        )

        self.assertEqual(
            result["status"],
            "relevant",
        )

        self.assertEqual(
            result["reason_code"],
            "explicit_identifier_supported",
        )

        self.assertTrue(
            result["allow_grounded_synthesis"]
        )


    def test_multiple_technical_terms_can_establish_relevance(
        self,
    ):

        result = assess_semantic_relevance(
            "motor stalls open phase",
            semantic_result(
                text=(
                    "Motor stalls. One phase may be open. "
                    "Check lines for open phase."
                )
            ),
        )

        self.assertEqual(
            result["status"],
            "relevant",
        )

        self.assertEqual(
            result["reason_code"],
            "multiple_query_anchors_supported",
        )

        self.assertTrue(
            result["relevant"]
        )


    def test_single_generic_overlap_remains_uncertain(
        self,
    ):

        result = assess_semantic_relevance(
            "motor vibration",
            semantic_result(
                text=(
                    "Motor installation and general operating information."
                )
            ),
        )

        self.assertEqual(
            result["status"],
            "uncertain",
        )

        self.assertFalse(
            result["allow_grounded_synthesis"]
        )


    def test_high_similarity_cannot_override_missing_support(
        self,
    ):

        result = assess_semantic_relevance(
            "ethernet printer offline",
            semantic_result(
                text=(
                    "Hydraulic pump maintenance instructions."
                ),
                similarity=0.9999,
            ),
        )

        self.assertEqual(
            result["status"],
            "uncertain",
        )

        self.assertFalse(
            result["allow_grounded_synthesis"]
        )

        self.assertFalse(
            result["uses_similarity_threshold"]
        )


    def test_low_similarity_does_not_force_irrelevance(
        self,
    ):

        result = assess_semantic_relevance(
            "motor stalls open phase",
            semantic_result(
                text=(
                    "Motor stalls. One phase may be open."
                ),
                similarity=-0.4,
            ),
        )

        self.assertEqual(
            result["status"],
            "relevant",
        )

        self.assertFalse(
            result["uses_similarity_threshold"]
        )


    def test_non_semantic_result_is_not_applicable(
        self,
    ):

        result = assess_semantic_relevance(
            "alarm 10653",
            {
                "mode":
                    "exact_alarm",

                "status":
                    "found",

                "results":
                    [],
            },
        )

        self.assertEqual(
            result["status"],
            "not_applicable",
        )

        self.assertFalse(
            result["allow_grounded_synthesis"]
        )


    def test_no_candidates_is_insufficient(
        self,
    ):

        result = assess_semantic_relevance(
            "motor stalls",
            {
                "mode":
                    "semantic",

                "status":
                    "candidates",

                "results":
                    [],
            },
        )

        self.assertEqual(
            result["status"],
            "insufficient",
        )

        self.assertFalse(
            result["allow_grounded_synthesis"]
        )


    def test_query_without_technical_anchor_is_uncertain(
        self,
    ):

        result = assess_semantic_relevance(
            "what is it",
            semantic_result(
                text="Motor stalls."
            ),
        )

        self.assertEqual(
            result["status"],
            "uncertain",
        )

        self.assertEqual(
            result["reason_code"],
            "no_explicit_query_anchors",
        )


    def test_gate_does_not_mutate_source_result(
        self,
    ):

        source = semantic_result(
            text=(
                "Motor stalls. One phase may be open."
            )
        )

        before = copy.deepcopy(
            source
        )

        assess_semantic_relevance(
            "motor stalls open phase",
            source,
        )

        self.assertEqual(
            source,
            before,
        )


    def test_non_dictionary_source_is_rejected(
        self,
    ):

        result = assess_semantic_relevance(
            "motor stalls",
            [],
        )

        self.assertEqual(
            result["status"],
            "invalid",
        )


    def test_non_string_query_raises_type_error(
        self,
    ):

        with self.assertRaises(
            TypeError
        ):

            assess_semantic_relevance(
                None,
                semantic_result(
                    text="Motor stalls."
                ),
            )


    def test_result_never_confirms_diagnosis_or_execution(
        self,
    ):

        result = assess_semantic_relevance(
            "motor stalls open phase",
            semantic_result(
                text=(
                    "Motor stalls. One phase may be open."
                )
            ),
        )

        self.assertFalse(
            result["diagnosis_confirmed"]
        )

        self.assertFalse(
            result["approved_for_automatic_execution"]
        )


if __name__ == "__main__":
    unittest.main()
