from __future__ import annotations

import unittest

from types import SimpleNamespace
from unittest.mock import patch


from app.services import (
    assistant_workflow,
)

from app.services.assistant_workflow import (
    ConversationRequest,
)


def loop_result(
    body,
):

    return SimpleNamespace(
        status=
            "completed",

        blocked_reason=
            None,

        observations=[
            SimpleNamespace(
                result={
                    "result":
                        body,
                },
            ),
        ],

        final_decision=
            SimpleNamespace(
                action=
                    "return_information",

                reason=
                    "Evidence returned.",
            ),

        decisions=[
            SimpleNamespace(
                action=
                    "call_tool",
            ),
            SimpleNamespace(
                action=
                    "return_information",
            ),
        ],
    )


def request(
    query=
        "motor stalls open phase",
):

    return ConversationRequest(
        mode=
            "enterprise_evidence",

        user_message=
            "",

        answers={
            "query":
                query,
        },
    )


def semantic_body():

    return {
        "status":
            "evidence_retrieved",

        "evidence": {
            "mode":
                "semantic",

            "status":
                "candidates",

            "results_count":
                2,

            "results": [
                {
                    "document_id":
                        "abb",

                    "source_filename":
                        "abb.pdf",

                    "page_numbers":
                        [25],

                    "possible_cause":
                        "One phase may be open.",

                    "manufacturer_guidance":
                        "Check lines for open phase.",

                    "cosine_similarity":
                        0.99,
                },
                {
                    "document_id":
                        "abb",

                    "source_filename":
                        "abb.pdf",

                    "page_numbers":
                        [26],

                    "possible_cause":
                        "Overload.",

                    "manufacturer_guidance":
                        "Check load condition.",

                    "cosine_similarity":
                        0.98,
                },
            ],
        },
    }


def semantic_hold():

    return {
        "status":
            "semantic_relevance_required",

        "reason_code":
            "semantic_candidates_require_relevance_assessment",

        "allow_grounded_synthesis":
            False,

        "requires_relevance_assessment":
            True,

        "evidence_count":
            2,

        "source_page_count":
            2,

        "retrieval_status":
            "candidates",

        "message":
            "Semantic relevance required.",

        "uses_similarity_threshold":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


def relevant(
    indexes=None,
):

    return {
        "status":
            "relevant",

        "reason_code":
            "multiple_query_anchors_supported",

        "message":
            "Relevant evidence.",

        "relevant":
            True,

        "allow_grounded_synthesis":
            True,

        "query_anchor_count":
            4,

        "matched_anchor_count":
            4,

        "matched_result_indexes":
            (
                [0]
                if indexes is None
                else indexes
            ),

        "uses_similarity_threshold":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


def uncertain():

    result = relevant()

    result[
        "status"
    ] = "uncertain"

    result[
        "relevant"
    ] = False

    result[
        "allow_grounded_synthesis"
    ] = False

    return result


def exact_ready():

    return {
        "status":
            "sufficient",

        "reason_code":
            "exact_evidence_ready",

        "allow_grounded_synthesis":
            True,

        "requires_relevance_assessment":
            False,

        "evidence_count":
            1,

        "source_page_count":
            1,

        "retrieval_status":
            "found",

        "message":
            "Exact evidence ready.",

        "uses_similarity_threshold":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


def exact_body():

    return {
        "status":
            "evidence_retrieved",

        "evidence": {
            "document_id":
                "siemens",

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

                    "page_numbers":
                        [130],

                    "text":
                        (
                            "10653 Axis gantry error threshold exceeded. "
                            "Remedy: Check axis."
                        ),
                }
            ],
        },
    }


class GroundedEvidenceWorkflowIntegrationTests(
    unittest.TestCase
):

    def test_relevant_semantic_evidence_is_ready(
        self,
    ):

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                loop_result(
                    semantic_body()
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                semantic_hold(),
        ), patch.object(
            assistant_workflow,
            "assess_semantic_relevance",
            return_value=
                relevant(),
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    request()
                )
            )


        self.assertTrue(
            response[
                "grounded_synthesis_allowed"
            ]
        )

        self.assertTrue(
            response[
                "grounded_evidence_ready"
            ]
        )

        self.assertTrue(
            response[
                "grounded_synthesis_ready"
            ]
        )

        self.assertEqual(
            response[
                "grounded_evidence_reason"
            ],
            "ready",
        )


    def test_only_matched_semantic_results_are_packaged(
        self,
    ):

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                loop_result(
                    semantic_body()
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                semantic_hold(),
        ), patch.object(
            assistant_workflow,
            "assess_semantic_relevance",
            return_value=
                relevant(
                    [1]
                ),
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    request()
                )
            )


        bundle = response[
            "grounded_evidence_bundle"
        ]

        self.assertEqual(
            bundle[
                "evidence_count"
            ],
            1,
        )

        self.assertEqual(
            bundle[
                "items"
            ][
                0
            ][
                "source_result_index"
            ],
            1,
        )


    def test_similarity_is_absent_from_bundle(
        self,
    ):

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                loop_result(
                    semantic_body()
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                semantic_hold(),
        ), patch.object(
            assistant_workflow,
            "assess_semantic_relevance",
            return_value=
                relevant(),
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    request()
                )
            )


        serialized = repr(
            response[
                "grounded_evidence_bundle"
            ]
        )

        self.assertNotIn(
            "cosine_similarity",
            serialized,
        )

        self.assertNotIn(
            "0.99",
            serialized,
        )


    def test_uncertain_semantic_evidence_is_not_ready(
        self,
    ):

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                loop_result(
                    semantic_body()
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                semantic_hold(),
        ), patch.object(
            assistant_workflow,
            "assess_semantic_relevance",
            return_value=
                uncertain(),
        ), patch.object(
            assistant_workflow,
            "build_grounded_evidence_bundle",
        ) as builder:

            response = (
                assistant_workflow
                .run_conversation(
                    request()
                )
            )


        builder.assert_not_called()

        self.assertFalse(
            response[
                "grounded_synthesis_allowed"
            ]
        )

        self.assertFalse(
            response[
                "grounded_evidence_ready"
            ]
        )

        self.assertFalse(
            response[
                "grounded_synthesis_ready"
            ]
        )


    def test_exact_evidence_can_be_ready(
        self,
    ):

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                loop_result(
                    exact_body()
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                exact_ready(),
        ), patch.object(
            assistant_workflow,
            "assess_semantic_relevance",
        ) as semantic_gate:

            response = (
                assistant_workflow
                .run_conversation(
                    request(
                        "Siemens alarm 10653"
                    )
                )
            )


        semantic_gate.assert_not_called()

        self.assertTrue(
            response[
                "grounded_synthesis_allowed"
            ]
        )

        self.assertTrue(
            response[
                "grounded_evidence_ready"
            ]
        )

        self.assertTrue(
            response[
                "grounded_synthesis_ready"
            ]
        )


    def test_missing_payload_preserves_permission_but_blocks_readiness(
        self,
    ):

        incomplete = {
            "status":
                "evidence_retrieved",

            "message":
                "Legacy mocked result.",
        }


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                loop_result(
                    incomplete
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                exact_ready(),
        ), patch.object(
            assistant_workflow,
            "build_grounded_evidence_bundle",
        ) as builder:

            response = (
                assistant_workflow
                .run_conversation(
                    request(
                        "Siemens alarm 10653"
                    )
                )
            )


        builder.assert_not_called()

        self.assertTrue(
            response[
                "grounded_synthesis_allowed"
            ]
        )

        self.assertFalse(
            response[
                "grounded_evidence_ready"
            ]
        )

        self.assertFalse(
            response[
                "grounded_synthesis_ready"
            ]
        )

        self.assertEqual(
            response[
                "grounded_evidence_reason"
            ],
            "missing_retrieval_payload",
        )


    def test_packaging_validation_failure_fails_closed(
        self,
    ):

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                loop_result(
                    exact_body()
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                exact_ready(),
        ), patch.object(
            assistant_workflow,
            "build_grounded_evidence_bundle",
            side_effect=
                ValueError(
                    "invalid bundle"
                ),
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    request(
                        "Siemens alarm 10653"
                    )
                )
            )


        self.assertTrue(
            response[
                "grounded_synthesis_allowed"
            ]
        )

        self.assertFalse(
            response[
                "grounded_evidence_ready"
            ]
        )

        self.assertFalse(
            response[
                "grounded_synthesis_ready"
            ]
        )

        self.assertEqual(
            response[
                "grounded_evidence_reason"
            ],
            "packaging_validation_failed",
        )


    def test_eligible_ids_match_bundle(
        self,
    ):

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                loop_result(
                    exact_body()
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                exact_ready(),
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    request(
                        "Siemens alarm 10653"
                    )
                )
            )


        self.assertEqual(
            response[
                "eligible_evidence_ids"
            ],
            response[
                "grounded_evidence_bundle"
            ][
                "evidence_ids"
            ],
        )


if __name__ == "__main__":
    unittest.main()
