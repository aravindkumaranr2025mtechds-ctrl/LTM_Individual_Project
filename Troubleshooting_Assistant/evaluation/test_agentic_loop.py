import unittest

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.dispatcher import (
    ProtectedToolDispatcher,
)

from app.services.agentic.loop import (
    run_agent_loop,
)

from app.services.agentic.model_adapter import (
    AgentModelAdapter,
)

from app.services.agentic.tool_registry import (
    build_default_tool_registry,
)


class SequenceAdapter(
    AgentModelAdapter
):
    def __init__(
        self,
        decisions,
    ):
        self._decisions = list(
            decisions
        )

        self.calls = 0

    @property
    def provider_name(self):
        return "test_sequence"

    def decide(
        self,
        state,
        allowed_tools,
    ):

        if (
            self.calls
            >= len(
                self._decisions
            )
        ):
            raise RuntimeError(
                "Test adapter exhausted."
            )

        decision = self._decisions[
            self.calls
        ]

        self.calls += 1

        return decision


class AgenticLoopTests(
    unittest.TestCase
):

    def setUp(self):

        self.registry = (
            build_default_tool_registry()
        )

        self.dispatcher = (
            ProtectedToolDispatcher(
                self.registry
            )
        )

    def test_tool_then_return_information_completes(self):

        model = SequenceAdapter(
            [
                AgentDecision(
                    action=
                        "call_tool",

                    reason=
                        "Explicit scope available.",

                    tool_name=
                        "siemens_logfile",

                    tool_arguments={
                        "alarm_scope":
                            "61352_or_61353"
                    },
                ),

                AgentDecision(
                    action=
                        "return_information",

                    reason=
                        "Protected evidence is available.",
                ),
            ]
        )

        result = run_agent_loop(
            AgentState(
                user_message=
                    "Which logfile parameter applies?",

                known_facts={
                    "alarm_scope":
                        "61352_or_61353"
                },
            ),
            model,
            self.registry,
            self.dispatcher,
        )

        self.assertEqual(
            result.status,
            "completed",
        )

        self.assertEqual(
            len(result.observations),
            1,
        )

        self.assertEqual(
            result.state.
            last_tool_result[
                "result"
            ][
                "selected_policy"
            ],
            "siemens_logfile",
        )

    def test_clarification_stops_for_user_input(self):

        model = SequenceAdapter(
            [
                AgentDecision(
                    action=
                        "ask_clarification",

                    reason=
                        "Scope is missing.",

                    requested_fact=
                        "alarm_scope",

                    question=
                        "Which alarm scope applies?",
                )
            ]
        )

        result = run_agent_loop(
            AgentState(
                user_message=
                    "Where is the logfile?",
                unknown_facts=[
                    "alarm_scope"
                ],
            ),
            model,
            self.registry,
            self.dispatcher,
        )

        self.assertEqual(
            result.status,
            "needs_user_input",
        )

        self.assertEqual(
            result.final_decision.
            requested_fact,
            "alarm_scope",
        )

    def test_inspection_stops_for_observation(self):

        model = SequenceAdapter(
            [
                AgentDecision(
                    action=
                        "suggest_inspection",

                    reason=
                        "A physical observation is missing.",

                    requested_fact=
                        "low_voltage_reported",

                    suggestion=
                        "Verify whether low voltage "
                        "has been explicitly observed.",
                )
            ]
        )

        result = run_agent_loop(
            AgentState(
                user_message=
                    "Motor stalls.",
                unknown_facts=[
                    "low_voltage_reported"
                ],
            ),
            model,
            self.registry,
            self.dispatcher,
        )

        self.assertEqual(
            result.status,
            "inspection_suggested",
        )

    def test_return_without_evidence_is_blocked(self):

        model = SequenceAdapter(
            [
                AgentDecision(
                    action=
                        "return_information",

                    reason=
                        "Answer immediately.",
                )
            ]
        )

        result = run_agent_loop(
            AgentState(
                user_message="Example"
            ),
            model,
            self.registry,
            self.dispatcher,
        )

        self.assertEqual(
            result.status,
            "guard_blocked",
        )

    def test_duplicate_tool_call_is_blocked(self):

        call = AgentDecision(
            action=
                "call_tool",

            reason=
                "Need structured guidance.",

            tool_name=
                "troubleshooting_guidance",

            tool_arguments={},
        )

        model = SequenceAdapter(
            [
                call,
                call,
            ]
        )

        result = run_agent_loop(
            AgentState(
                user_message=
                    "Show supported troubleshooting guidance."
            ),
            model,
            self.registry,
            self.dispatcher,
        )

        self.assertEqual(
            result.status,
            "guard_blocked",
        )

        self.assertIn(
            "repeat",
            result.blocked_reason.lower(),
        )



    def test_abstain_is_supported(self):

        model = SequenceAdapter(
            [
                AgentDecision(
                    action=
                        "abstain",

                    reason=
                        "Outside supported evidence scope.",
                )
            ]
        )

        result = run_agent_loop(
            AgentState(
                user_message=
                    "Unsupported machine"
            ),
            model,
            self.registry,
            self.dispatcher,
        )

        self.assertEqual(
            result.status,
            "abstained",
        )

    def test_loop_safety_flags_remain_false(self):

        model = SequenceAdapter(
            [
                AgentDecision(
                    action=
                        "ask_clarification",

                    reason=
                        "Need information.",

                    requested_fact=
                        "alarm_scope",

                    question=
                        "Which alarm scope applies?",
                )
            ]
        )

        result = run_agent_loop(
            AgentState(
                user_message="Example"
            ),
            model,
            self.registry,
            self.dispatcher,
        )

        self.assertFalse(
            result.diagnosis_confirmed
        )

        self.assertFalse(
            result.
            approved_for_automatic_execution
        )


if __name__ == "__main__":
    unittest.main()
