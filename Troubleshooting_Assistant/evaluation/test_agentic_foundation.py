import unittest

from pydantic import ValidationError

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
    ToolRegistry,
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
        self.seen_state = None
        self.seen_tools = None

    @property
    def provider_name(self):
        return "test_static"

    def decide(
        self,
        state,
        allowed_tools,
    ):
        self.seen_state = state
        self.seen_tools = allowed_tools

        return self._decision


class AgenticFoundationTests(
    unittest.TestCase
):
    def test_state_safety_defaults(self):
        state = AgentState(
            user_message="Motor stalls"
        )

        self.assertFalse(
            state.diagnosis_confirmed
        )

        self.assertFalse(
            state.approved_for_automatic_execution
        )

    def test_state_rejects_confirmed_diagnosis(self):
        with self.assertRaises(
            ValidationError
        ):
            AgentState(
                user_message="Example",
                diagnosis_confirmed=True,
            )

    def test_call_tool_requires_tool_name(self):
        with self.assertRaises(
            ValidationError
        ):
            AgentDecision(
                action="call_tool",
                reason="Need evidence.",
            )

    def test_non_tool_action_cannot_hide_tool_call(self):
        with self.assertRaises(
            ValidationError
        ):
            AgentDecision(
                action="return_information",
                reason="Return information.",
                tool_name="abb_stall",
            )

    def test_clarification_requires_question(self):
        with self.assertRaises(
            ValidationError
        ):
            AgentDecision(
                action="ask_clarification",
                reason="Missing information.",
            )

    def test_inspection_requires_fact_and_suggestion(self):
        with self.assertRaises(
            ValidationError
        ):
            AgentDecision(
                action="suggest_inspection",
                reason="Need measurement.",
                requested_fact=
                    "low_voltage_reported",
            )

    def test_default_registry_has_exact_initial_tools(self):
        registry = (
            build_default_tool_registry()
        )

        self.assertEqual(
            registry.names(),
            [
                "troubleshooting_guidance",
                "troubleshooting_questions",
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            ],
        )

    def test_registry_returns_copies(self):
        registry = (
            build_default_tool_registry()
        )

        first = registry.get(
            "siemens_logfile"
        )

        first.safety_notes.append(
            "CHANGED"
        )

        second = registry.get(
            "siemens_logfile"
        )

        self.assertNotIn(
            "CHANGED",
            second.safety_notes,
        )

    def test_registry_execution_is_disabled(self):
        registry = (
            build_default_tool_registry()
        )

        with self.assertRaises(
            PermissionError
        ):
            registry.execute(
                "abb_stall",
                {},
            )

    def test_controller_accepts_allowed_tool_plan(self):
        registry = (
            build_default_tool_registry()
        )

        adapter = StaticAdapter(
            AgentDecision(
                action="call_tool",
                reason=(
                    "Explicit logfile scope "
                    "requires source evidence."
                ),
                tool_name=
                    "siemens_logfile",
                tool_arguments={
                    "alarm_scope":
                        "61352_or_61353"
                },
            )
        )

        result = plan_next_action(
            AgentState(
                user_message=(
                    "Check logfile evidence."
                ),
                known_facts={
                    "alarm_scope":
                        "61352_or_61353"
                },
            ),
            adapter,
            registry,
        )

        self.assertEqual(
            result.tool_name,
            "siemens_logfile",
        )

        self.assertEqual(
            adapter.provider_name,
            "test_static",
        )

    def test_controller_does_not_mutate_original_state(self):
        registry = (
            build_default_tool_registry()
        )

        state = AgentState(
            user_message="Example",
            unknown_facts=[
                "low_voltage_reported"
            ],
        )

        before = state.model_dump(
            mode="python"
        )

        adapter = StaticAdapter(
            AgentDecision(
                action=
                    "ask_clarification",
                reason=
                    "A required fact is unknown.",
                requested_fact=
                    "low_voltage_reported",
                question=(
                    "Has low voltage been "
                    "explicitly reported?"
                ),
            )
        )

        plan_next_action(
            state,
            adapter,
            registry,
        )

        adapter.seen_state.unknown_facts.clear()

        self.assertEqual(
            before,
            state.model_dump(
                mode="python"
            ),
        )

    def test_custom_registry_can_restrict_available_tools(self):
        full = (
            build_default_tool_registry()
        )

        restricted = ToolRegistry(
            [
                full.get(
                    "abb_stall"
                )
            ]
        )

        adapter = StaticAdapter(
            AgentDecision(
                action="call_tool",
                reason="Need Siemens evidence.",
                tool_name=
                    "siemens_logfile",
                tool_arguments={
                    "alarm_scope": "61352"
                },
            )
        )

        with self.assertRaises(
            PermissionError
        ):
            plan_next_action(
                AgentState(
                    user_message="Example"
                ),
                adapter,
                restricted,
            )


if __name__ == "__main__":
    unittest.main()
