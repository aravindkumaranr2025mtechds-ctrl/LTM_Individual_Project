from __future__ import annotations

import copy
import unittest

from app.services.evidence_sufficiency_gate import (
    assess_enterprise_evidence_sufficiency,
)


def item(
    *,
    score=0.70,
):

    return {
        "document_id":
            "doc-001",

        "parent_id":
            "doc-001-section-1",

        "page_numbers":
            [
                25
            ],

        "text":
            (
                "Manufacturer troubleshooting evidence "
                "for the reported condition."
            ),

        "cosine_similarity":
            score,
    }


def source_result(
    *,
    retrieval_status="candidates",
    results=None,
):

    if results is None:

        results = [
            item()
        ]


    return {
        "status":
            "evidence_retrieved",

        "evidence": {
            "status":
                retrieval_status,

            "document_id":
                "doc-001",

            "results_count":
                len(
                    results
                ),

            "results":
                results,
        },

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


class EvidenceSufficiencyGateTests(
    unittest.TestCase
):

    def test_semantic_candidates_require_relevance_assessment(
        self,
    ):

        result = (
            assess_enterprise_evidence_sufficiency(
                source_result()
            )
        )

        self.assertEqual(
            result["status"],
            "needs_relevance_assessment",
        )

        self.assertTrue(
            result[
                "requires_relevance_assessment"
            ]
        )

        self.assertFalse(
            result[
                "allow_grounded_synthesis"
            ]
        )


    def test_exact_found_evidence_can_continue_to_synthesis(
        self,
    ):

        result = (
            assess_enterprise_evidence_sufficiency(
                source_result(
                    retrieval_status=
                        "found"
                )
            )
        )

        self.assertEqual(
            result["status"],
            "ready_for_grounded_synthesis",
        )

        self.assertTrue(
            result[
                "allow_grounded_synthesis"
            ]
        )


    def test_confirmed_selection_can_continue_to_synthesis(
        self,
    ):

        result = (
            assess_enterprise_evidence_sufficiency(
                source_result(
                    retrieval_status=
                        "confirmed_selection"
                )
            )
        )

        self.assertEqual(
            result["status"],
            "ready_for_grounded_synthesis",
        )


    def test_not_found_is_insufficient(
        self,
    ):

        result = (
            assess_enterprise_evidence_sufficiency(
                {
                    "status":
                        "not_found",

                    "evidence": {
                        "status":
                            "not_found",

                        "results_count":
                            0,

                        "results":
                            [],
                    },

                    "diagnosis_confirmed":
                        False,

                    "approved_for_automatic_execution":
                        False,
                }
            )
        )

        self.assertEqual(
            result["status"],
            "insufficient_evidence",
        )

        self.assertFalse(
            result[
                "allow_grounded_synthesis"
            ]
        )


    def test_empty_candidate_list_is_insufficient(
        self,
    ):

        result = (
            assess_enterprise_evidence_sufficiency(
                source_result(
                    results=[]
                )
            )
        )

        self.assertEqual(
            result["reason_code"],
            "empty_evidence_results",
        )


    def test_missing_retrieval_payload_is_invalid(
        self,
    ):

        result = (
            assess_enterprise_evidence_sufficiency(
                {
                    "status":
                        "evidence_retrieved",

                    "diagnosis_confirmed":
                        False,

                    "approved_for_automatic_execution":
                        False,
                }
            )
        )

        self.assertEqual(
            result["status"],
            "invalid_evidence_contract",
        )


    def test_results_count_mismatch_is_invalid(
        self,
    ):

        value = source_result()

        value["evidence"][
            "results_count"
        ] = 7

        result = (
            assess_enterprise_evidence_sufficiency(
                value
            )
        )

        self.assertEqual(
            result["reason_code"],
            "results_count_mismatch",
        )


    def test_missing_source_page_is_invalid(
        self,
    ):

        broken = item()

        broken.pop(
            "page_numbers"
        )

        result = (
            assess_enterprise_evidence_sufficiency(
                source_result(
                    results=[
                        broken
                    ]
                )
            )
        )

        self.assertEqual(
            result["reason_code"],
            "missing_source_pages",
        )


    def test_missing_evidence_text_is_invalid(
        self,
    ):

        broken = item()

        broken.pop(
            "text"
        )

        result = (
            assess_enterprise_evidence_sufficiency(
                source_result(
                    results=[
                        broken
                    ]
                )
            )
        )

        self.assertEqual(
            result["reason_code"],
            "missing_evidence_text",
        )


    def test_unsafe_nested_flag_is_rejected(
        self,
    ):

        value = source_result()

        value["evidence"][
            "results"
        ][0][
            "diagnosis_confirmed"
        ] = True

        result = (
            assess_enterprise_evidence_sufficiency(
                value
            )
        )

        self.assertEqual(
            result["reason_code"],
            "unsafe_evidence_flags",
        )

        self.assertFalse(
            result[
                "allow_grounded_synthesis"
            ]
        )


    def test_similarity_is_not_used_as_confidence_threshold(
        self,
    ):

        low = (
            assess_enterprise_evidence_sufficiency(
                source_result(
                    results=[
                        item(
                            score=-0.50
                        )
                    ]
                )
            )
        )

        high = (
            assess_enterprise_evidence_sufficiency(
                source_result(
                    results=[
                        item(
                            score=0.999
                        )
                    ]
                )
            )
        )

        self.assertEqual(
            low["status"],
            "needs_relevance_assessment",
        )

        self.assertEqual(
            high["status"],
            "needs_relevance_assessment",
        )

        self.assertFalse(
            low[
                "uses_similarity_threshold"
            ]
        )

        self.assertFalse(
            high[
                "uses_similarity_threshold"
            ]
        )


    def test_gate_does_not_mutate_retrieval_result(
        self,
    ):

        value = source_result()

        before = copy.deepcopy(
            value
        )

        assess_enterprise_evidence_sufficiency(
            value
        )

        self.assertEqual(
            value,
            before,
        )


    def test_non_dictionary_input_rejected(
        self,
    ):

        with self.assertRaises(
            TypeError
        ):

            assess_enterprise_evidence_sufficiency(
                []
            )


if __name__ == "__main__":
    unittest.main()
