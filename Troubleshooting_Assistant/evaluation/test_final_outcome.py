from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.final_outcome import (
    build_final_outcome,
)


class FinalOutcomeTests(
    unittest.TestCase
):

    def base(
        self,
        *,
        status="unknown",
        actions=None,
    ):

        return {
            "status":
                status,

            "next_question":
                None,

            "trace": {
                "actions":
                    list(
                        actions
                        or []
                    ),
            },

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }


    def test_return_information_maps_to_answer(
        self,
    ):

        outcome = build_final_outcome(
            self.base(
                status=
                    "reports_complete",

                actions=[
                    "call_tool",
                    "return_information",
                ],
            )
        )

        self.assertEqual(
            outcome[
                "decision"
            ],
            "ANSWER",
        )


    def test_source_information_maps_to_answer(
        self,
    ):

        outcome = build_final_outcome(
            self.base(
                status=
                    "source_information",
            )
        )

        self.assertEqual(
            outcome[
                "decision"
            ],
            "ANSWER",
        )


    def test_enterprise_evidence_maps_to_answer(
        self,
    ):

        outcome = build_final_outcome(
            self.base(
                status=
                    "evidence_retrieved",
            )
        )

        self.assertEqual(
            outcome[
                "decision"
            ],
            "ANSWER",
        )


    def test_next_question_maps_to_clarify(
        self,
    ):

        response = self.base(
            status=
                "evidence_retrieved",
        )

        response[
            "next_question"
        ] = {
            "fact_id":
                "test_fact",

            "text":
                "Please clarify.",
        }


        outcome = build_final_outcome(
            response
        )


        self.assertEqual(
            outcome[
                "decision"
            ],
            "CLARIFY",
        )


    def test_agent_clarification_maps_to_clarify(
        self,
    ):

        outcome = build_final_outcome(
            self.base(
                actions=[
                    "ask_clarification",
                ],
            )
        )

        self.assertEqual(
            outcome[
                "decision"
            ],
            "CLARIFY",
        )


    def test_needs_clarification_status_maps_to_clarify(
        self,
    ):

        outcome = build_final_outcome(
            self.base(
                status=
                    "needs_clarification",
            )
        )

        self.assertEqual(
            outcome[
                "decision"
            ],
            "CLARIFY",
        )


    def test_agent_abstain_maps_to_abstain(
        self,
    ):

        outcome = build_final_outcome(
            self.base(
                status=
                    "evidence_retrieved",

                actions=[
                    "call_tool",
                    "abstain",
                ],
            )
        )

        self.assertEqual(
            outcome[
                "decision"
            ],
            "ABSTAIN",
        )


    def test_insufficient_evidence_maps_to_abstain(
        self,
    ):

        outcome = build_final_outcome(
            self.base(
                status=
                    "insufficient_evidence",
            )
        )

        self.assertEqual(
            outcome[
                "decision"
            ],
            "ABSTAIN",
        )


    def test_explicit_structured_escalation_maps_to_escalate(
        self,
    ):

        response = self.base(
            status=
                "evidence_retrieved",

            actions=[
                "return_information",
            ],
        )

        response[
            "grounded_guidance"
        ] = {
            "status":
                "escalate",

            "steps": [
                {
                    "action":
                        "review_evidence",
                },

                {
                    "action":
                        "escalate",
                },
            ],
        }


        outcome = build_final_outcome(
            response
        )


        self.assertEqual(
            outcome[
                "decision"
            ],
            "ESCALATE",
        )


    def test_escalate_word_without_final_step_does_not_escalate(
        self,
    ):

        response = self.base()

        response[
            "grounded_guidance"
        ] = {
            "status":
                "escalate",

            "steps": [
                {
                    "action":
                        "review_evidence",
                },
            ],
        }


        outcome = build_final_outcome(
            response
        )


        self.assertNotEqual(
            outcome[
                "decision"
            ],
            "ESCALATE",
        )


    def test_unknown_state_fails_closed(
        self,
    ):

        outcome = build_final_outcome(
            self.base(
                status=
                    "future_unknown_state",
            )
        )


        self.assertEqual(
            outcome[
                "decision"
            ],
            "ABSTAIN",
        )

        self.assertEqual(
            outcome[
                "reason_code"
            ],
            "conservative_default",
        )


    def test_public_workflow_preserves_detailed_status(
        self,
    ):

        import app.services.assistant_workflow as workflow


        core_response = self.base(
            status=
                "evidence_retrieved",
        )


        with patch.object(
            workflow,
            "_run_conversation_core",
            return_value=
                dict(
                    core_response
                ),
        ):

            response = (
                workflow.run_conversation(
                    object()
                )
            )


        self.assertEqual(
            response[
                "status"
            ],
            "evidence_retrieved",
        )


        self.assertEqual(
            response[
                "final_outcome"
            ][
                "decision"
            ],
            "ANSWER",
        )


        self.assertIs(
            response[
                "final_outcome"
            ][
                "diagnosis_confirmed"
            ],
            False,
        )


        self.assertIs(
            response[
                "final_outcome"
            ][
                "approved_for_automatic_execution"
            ],
            False,
        )


if __name__ == "__main__":
    unittest.main()
