import unittest

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.controller import (
    plan_next_action,
)

from app.services.agentic.model_adapter import (
    AgentModelAdapter,
)

from app.services.agentic.tool_registry import (
    build_default_tool_registry,
)


class StaticAdapter(AgentModelAdapter):

    def __init__(self, decision):
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


class AgenticGroundingGuardTests(
    unittest.TestCase
):

    def setUp(self):
        self.registry = (
            build_default_tool_registry()
        )

    def plan(
        self,
        state,
        decision,
    ):
        return plan_next_action(
            state,
            StaticAdapter(decision),
            self.registry,
        )

    def test_invented_alarm_scope_rejected(self):

        state = AgentState(
            user_message=
                "Where is the Siemens logfile?",
            unknown_facts=[
                "alarm_scope"
            ],
        )

        decision = AgentDecision(
            action="call_tool",
            reason="Need logfile evidence.",
            tool_name="siemens_logfile",
            tool_arguments={
                "alarm_scope":
                    "61352"
            },
        )

        with self.assertRaises(
            PermissionError
        ):
            self.plan(
                state,
                decision,
            )

    def test_changed_known_fact_rejected(self):

        state = AgentState(
            user_message="Example",
            known_facts={
                "alarm_scope":
                    "61352"
            },
        )

        decision = AgentDecision(
            action="call_tool",
            reason="Need evidence.",
            tool_name="siemens_logfile",
            tool_arguments={
                "alarm_scope":
                    "61353"
            },
        )

        with self.assertRaises(
            PermissionError
        ):
            self.plan(
                state,
                decision,
            )

    def test_exact_known_fact_is_allowed(self):

        state = AgentState(
            user_message="Example",
            known_facts={
                "alarm_scope":
                    "61352"
            },
        )

        decision = AgentDecision(
            action="call_tool",
            reason="Explicit scope is available.",
            tool_name="siemens_logfile",
            tool_arguments={
                "alarm_scope":
                    "61352"
            },
        )

        result = self.plan(
            state,
            decision,
        )

        self.assertEqual(
            result.tool_arguments[
                "alarm_scope"
            ],
            "61352",
        )

    def test_missing_required_explicit_field_rejected(self):

        state = AgentState(
            user_message="Example"
        )

        decision = AgentDecision(
            action="call_tool",
            reason="Need logfile evidence.",
            tool_name="siemens_logfile",
            tool_arguments={},
        )

        with self.assertRaises(
            PermissionError
        ):
            self.plan(
                state,
                decision,
            )

    def test_clarification_needs_no_grounded_tool_arguments(self):

        decision = AgentDecision(
            action=
                "ask_clarification",
            reason=
                "Alarm scope is unknown.",
            requested_fact=
                "alarm_scope",
            question=
                "Which alarm scope should be checked?",
        )

        result = self.plan(
            AgentState(
                user_message=
                    "Where is the logfile?",
                unknown_facts=[
                    "alarm_scope"
                ],
            ),
            decision,
        )

        self.assertEqual(
            result.action,
            "ask_clarification",
        )


if __name__ == "__main__":
    unittest.main()
