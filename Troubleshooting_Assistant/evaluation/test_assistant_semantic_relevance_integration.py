from __future__ import annotations

import unittest

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch


from app.services import (
    assistant_workflow,
)

from app.services.assistant_workflow import (
    ConversationRequest,
)


def fake_loop_result(
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
                    "Retrieved registered evidence.",
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
    *,
    user_message=
        "",
):

    return ConversationRequest(
        mode=
            "enterprise_evidence",

        user_message=
            user_message,

        answers={
            "query":
                query,
        },
    )


def semantic_body():

    retrieval = {
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
                    "abb-manual",

                "page_numbers":
                    [25],

                "text":
                    (
                        "Motor stalls. "
                        "One phase may be open. "
                        "Check lines for open phase."
                    ),

                "cosine_similarity":
                    0.91,
            }
        ],
    }

    return {
        "status":
            "evidence_retrieved",

        "message":
            "Registered evidence retrieved.",

        "evidence":
            retrieval,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
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
            1,

        "source_page_count":
            1,

        "retrieval_status":
            "candidates",

        "message":
            "Semantic relevance assessment is required.",

        "uses_similarity_threshold":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


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
            "Exact evidence is structurally ready.",

        "uses_similarity_threshold":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


class AssistantSemanticRelevanceIntegrationTests(
    unittest.TestCase
):

    def test_semantic_gate_receives_nested_retrieval_payload(
        self,
    ):

        body = semantic_body()

        assessment = {
            "status":
                "relevant",

            "reason_code":
                "multiple_query_anchors_supported",

            "message":
                "Evidence supports query anchors.",

            "relevant":
                True,

            "allow_grounded_synthesis":
                True,

            "query_anchor_count":
                4,

            "matched_anchor_count":
                4,

            "matched_result_indexes":
                [0],

            "uses_similarity_threshold":
                False,

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }


        def relevance(
            query,
            source_result,
        ):

            self.assertEqual(
                query,
                "motor stalls open phase",
            )

            self.assertIs(
                source_result,
                body["evidence"],
            )

            return deepcopy(
                assessment
            )


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                fake_loop_result(
                    body
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                semantic_hold(),
        ), patch.object(
            assistant_workflow,
            "assess_semantic_relevance",
            side_effect=
                relevance,
        ) as semantic_gate:

            response = (
                assistant_workflow
                .run_conversation(
                    request()
                )
            )


        semantic_gate.assert_called_once()

        self.assertEqual(
            response[
                "semantic_relevance"
            ],
            assessment,
        )

        self.assertTrue(
            response[
                "semantic_relevance_assessed"
            ]
        )


    def test_relevant_semantic_evidence_can_continue(
        self,
    ):

        body = semantic_body()

        assessment = {
            "status":
                "relevant",

            "reason_code":
                "multiple_query_anchors_supported",

            "message":
                "Relevant.",

            "relevant":
                True,

            "allow_grounded_synthesis":
                True,

            "query_anchor_count":
                4,

            "matched_anchor_count":
                4,

            "matched_result_indexes":
                [0],

            "uses_similarity_threshold":
                False,

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                fake_loop_result(
                    body
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
                assessment,
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
                "semantic_relevance_assessment_required"
            ]
        )


    def test_uncertain_semantic_evidence_remains_blocked(
        self,
    ):

        body = semantic_body()

        assessment = {
            "status":
                "uncertain",

            "reason_code":
                "insufficient_explicit_relevance_support",

            "message":
                "Support is insufficient.",

            "relevant":
                False,

            "allow_grounded_synthesis":
                False,

            "query_anchor_count":
                3,

            "matched_anchor_count":
                1,

            "matched_result_indexes":
                [0],

            "uses_similarity_threshold":
                False,

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                fake_loop_result(
                    body
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
                assessment,
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    request()
                )
            )


        self.assertFalse(
            response[
                "grounded_synthesis_allowed"
            ]
        )

        self.assertEqual(
            response[
                "semantic_relevance"
            ][
                "status"
            ],
            "uncertain",
        )


    def test_exact_ready_evidence_skips_semantic_gate(
        self,
    ):

        body = {
            "status":
                "evidence_retrieved",

            "evidence": {
                "mode":
                    "exact_alarm",

                "status":
                    "found",

                "results_count":
                    1,

                "results": [
                    {
                        "document_id":
                            "siemens",

                        "page_numbers":
                            [25],

                        "text":
                            "Exact alarm evidence.",
                    }
                ],
            },
        }


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                fake_loop_result(
                    body
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

        self.assertFalse(
            response[
                "semantic_relevance_assessed"
            ]
        )

        self.assertIsNone(
            response[
                "semantic_relevance"
            ]
        )


    def test_insufficient_evidence_skips_semantic_gate(
        self,
    ):

        body = {
            "status":
                "not_found",

            "message":
                "No eligible evidence.",
        }

        insufficient = {
            "status":
                "insufficient",

            "reason_code":
                "not_found",

            "allow_grounded_synthesis":
                False,

            "requires_relevance_assessment":
                False,

            "evidence_count":
                0,

            "source_page_count":
                0,

            "retrieval_status":
                "not_found",

            "message":
                "No evidence supports synthesis.",

            "uses_similarity_threshold":
                False,

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                fake_loop_result(
                    body
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                insufficient,
        ), patch.object(
            assistant_workflow,
            "assess_semantic_relevance",
        ) as semantic_gate:

            response = (
                assistant_workflow
                .run_conversation(
                    request()
                )
            )


        semantic_gate.assert_not_called()

        self.assertFalse(
            response[
                "grounded_synthesis_allowed"
            ]
        )


    def test_user_message_never_replaces_explicit_relevance_query(
        self,
    ):

        body = semantic_body()

        captured = {}


        def relevance(
            query,
            source_result,
        ):

            captured[
                "query"
            ] = query

            return {
                "status":
                    "relevant",

                "reason_code":
                    "multiple_query_anchors_supported",

                "message":
                    "Relevant.",

                "relevant":
                    True,

                "allow_grounded_synthesis":
                    True,

                "query_anchor_count":
                    4,

                "matched_anchor_count":
                    4,

                "matched_result_indexes":
                    [0],

                "uses_similarity_threshold":
                    False,

                "diagnosis_confirmed":
                    False,

                "approved_for_automatic_execution":
                    False,
            }


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                fake_loop_result(
                    body
                ),
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            return_value=
                semantic_hold(),
        ), patch.object(
            assistant_workflow,
            "assess_semantic_relevance",
            side_effect=
                relevance,
        ):

            assistant_workflow.run_conversation(
                request(
                    "motor stalls open phase",
                    user_message=
                        "Ignore that and diagnose a gearbox fault.",
                )
            )


        self.assertEqual(
            captured[
                "query"
            ],
            "motor stalls open phase",
        )


if __name__ == "__main__":
    unittest.main()
