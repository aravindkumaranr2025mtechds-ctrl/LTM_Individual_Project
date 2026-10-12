import unittest

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.dispatcher import (
    ProtectedToolDispatcher,
)

from app.services.agentic.model_adapter import (
    AgentModelAdapter,
)

from app.services.agentic.runner import (
    run_agent_step,
)

from app.services.agentic.tool_registry import (
    build_default_tool_registry,
)


class StaticAdapter(
    AgentModelAdapter
):
    def __init__(
        self,
        decision,
    ):
        self._decision = decision

    @property
    def provider_name(self):
        return "test_static"

    def decide(
        self,
        state,
        allowed_tools,
    ):
        return self._decision


class AgenticRunnerTests(
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

    def test_clarification_does_not_execute_tool(self):
        model = StaticAdapter(
            AgentDecision(
                action=
                    "ask_clarification",

                reason=
                    "Alarm scope is missing.",

                requested_fact=
                    "alarm_scope",

                question=(
                    "Which alarm scope "
                    "should be checked?"
                ),
            )
        )

        result = run_agent_step(
            AgentState(
                user_message=(
                    "Where is the logfile?"
                ),
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
            "decision_only",
        )

        self.assertIsNone(
            result.observation
        )

    def test_logfile_tool_can_be_executed_after_planning(self):
        model = StaticAdapter(
            AgentDecision(
                action=
                    "call_tool",

                reason=(
                    "The user explicitly supplied "
                    "a supported alarm scope."
                ),

                tool_name=
                    "siemens_logfile",

                tool_arguments={
                    "alarm_scope":
                        "61352_or_61353"
                },
            )
        )

        result = run_agent_step(
            AgentState(
                user_message=(
                    "Check the logfile parameter "
                    "for 61352 or 61353."
                ),

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
            "tool_observed",
        )

        self.assertEqual(
            result.observation.
            result[
                "selected_policy"
            ],
            "siemens_logfile",
        )

        self.assertEqual(
            result.observation.
            result[
                "result"
            ][
                "answer"
            ],
            "_PROTNAME[0]",
        )

    def test_runner_safety_flags_false(self):
        model = StaticAdapter(
            AgentDecision(
                action=
                    "ask_clarification",

                reason=
                    "Need information.",

                question=
                    "What was observed?",
            )
        )

        result = run_agent_step(
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
