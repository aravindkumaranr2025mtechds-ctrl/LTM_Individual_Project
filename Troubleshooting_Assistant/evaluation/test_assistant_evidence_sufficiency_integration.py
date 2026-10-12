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
                    "Retrieved source evidence.",
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


class AssistantEvidenceSufficiencyIntegrationTests(
    unittest.TestCase
):

    def enterprise_request(
        self,
    ):

        return ConversationRequest(
            mode=
                "enterprise_evidence",

            user_message=
                "",

            answers={
                "query":
                    "ABB motor stalls while running",
            },
        )


    def test_gate_runs_after_retrieval_and_receives_body(
        self,
    ):

        body = {
            "status":
                "evidence_retrieved",

            "message":
                "Registered evidence retrieved.",

            "evidence": {
                "results": [],
            },
        }

        assessment = {
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
                "evidence_retrieved",

            "message":
                "Relevance assessment is required.",

            "uses_similarity_threshold":
                False,

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }

        events = []


        def run_loop(
            *args,
            **kwargs,
        ):

            events.append(
                "retrieval"
            )

            return fake_loop_result(
                body
            )


        def assess(
            source_result,
        ):

            events.append(
                "sufficiency"
            )

            self.assertIs(
                source_result,
                body,
            )

            return deepcopy(
                assessment
            )


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            side_effect=
                run_loop,
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
            side_effect=
                assess,
        ) as gate:

            response = (
                assistant_workflow
                .run_conversation(
                    self.enterprise_request()
                )
            )


        gate.assert_called_once()

        self.assertEqual(
            events,
            [
                "retrieval",
                "sufficiency",
            ],
        )

        self.assertEqual(
            response[
                "evidence_sufficiency"
            ],
            assessment,
        )


    def test_semantic_hold_blocks_grounded_synthesis(
        self,
    ):

        body = {
            "status":
                "evidence_retrieved",

            "message":
                "Semantic candidates retrieved.",
        }

        assessment = {
            "status":
                "semantic_relevance_required",

            "reason_code":
                "semantic_candidates_require_relevance_assessment",

            "allow_grounded_synthesis":
                False,

            "requires_relevance_assessment":
                True,

            "evidence_count":
                3,

            "source_page_count":
                3,

            "retrieval_status":
                "evidence_retrieved",

            "message":
                "Semantic relevance must be assessed.",

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
                assessment,
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    self.enterprise_request()
                )
            )


        self.assertFalse(
            response[
                "grounded_synthesis_allowed"
            ]
        )

        self.assertTrue(
            response[
                "semantic_relevance_assessment_required"
            ]
        )


    def test_exact_ready_evidence_can_expose_synthesis_permission(
        self,
    ):

        body = {
            "status":
                "evidence_retrieved",

            "message":
                "Exact registered evidence retrieved.",
        }

        assessment = {
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
                "evidence_retrieved",

            "message":
                "Evidence may continue to grounded synthesis.",

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
                assessment,
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    self.enterprise_request()
                )
            )


        self.assertTrue(
            response[
                "grounded_synthesis_allowed"
            ]
        )

        self.assertFalse(
            response[
                "semantic_relevance_assessment_required"
            ]
        )


    def test_source_result_is_not_replaced_by_gate(
        self,
    ):

        body = {
            "status":
                "evidence_retrieved",

            "message":
                "Original retrieval body.",

            "nested": {
                "value":
                    7,
            },
        }

        original = deepcopy(
            body
        )

        assessment = {
            "status":
                "insufficient",

            "reason_code":
                "test_hold",

            "allow_grounded_synthesis":
                False,

            "requires_relevance_assessment":
                False,

            "evidence_count":
                0,

            "source_page_count":
                0,

            "retrieval_status":
                "evidence_retrieved",

            "message":
                "Grounded synthesis is blocked.",

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
                assessment,
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    self.enterprise_request()
                )
            )


        self.assertEqual(
            body,
            original,
        )

        self.assertEqual(
            response[
                "source_result"
            ],
            original,
        )


    def test_non_enterprise_workflow_does_not_call_sufficiency_gate(
        self,
    ):

        request = ConversationRequest(
            mode=
                "siemens_logfile",

            user_message=
                "",

            answers={},
        )

        result = SimpleNamespace(
            status=
                "abstained",

            blocked_reason=
                None,

            observations=
                [],

            final_decision=
                SimpleNamespace(
                    action=
                        "abstain",

                    reason=
                        "No source result.",
                ),

            decisions=[
                SimpleNamespace(
                    action=
                        "abstain",
                ),
            ],
        )


        with patch.object(
            assistant_workflow,
            "run_agent_loop",
            return_value=
                result,
        ), patch.object(
            assistant_workflow,
            "assess_enterprise_evidence_sufficiency",
        ) as gate:

            response = (
                assistant_workflow
                .run_conversation(
                    request
                )
            )


        gate.assert_not_called()

        self.assertNotIn(
            "evidence_sufficiency",
            response,
        )

        self.assertNotIn(
            "grounded_synthesis_allowed",
            response,
        )


if __name__ == "__main__":
    unittest.main()
