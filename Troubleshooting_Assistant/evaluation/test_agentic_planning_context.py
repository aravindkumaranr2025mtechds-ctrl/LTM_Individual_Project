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

from app.services.agentic.planning_context import (
    build_tool_readiness,
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


class AgenticPlanningContextTests(
    unittest.TestCase
):
    def setUp(self):

        self.registry = (
            build_default_tool_registry()
        )

        self.tools = (
            self.registry.list_specs()
        )

    def logfile_readiness(
        self,
        state,
    ):
        result = (
            build_tool_readiness(
                state,
                self.tools,
            )
        )

        return next(
            item
            for item in result
            if item[
                "tool_name"
            ]
            == "siemens_logfile"
        )

    def test_missing_scope_marks_logfile_not_ready(self):

        state = AgentState(
            user_message=
                "Where is the logfile?",
            unknown_facts=[
                "alarm_scope"
            ],
        )

        result = (
            self.logfile_readiness(
                state
            )
        )

        self.assertFalse(
            result[
                "ready_for_call"
            ]
        )

        self.assertEqual(
            result[
                "missing_required_fields"
            ],
            [
                "alarm_scope"
            ],
        )

    def test_known_scope_marks_logfile_ready(self):

        state = AgentState(
            user_message=
                "Check 61352.",
            known_facts={
                "alarm_scope":
                    "61352"
            },
        )

        result = (
            self.logfile_readiness(
                state
            )
        )

        self.assertTrue(
            result[
                "ready_for_call"
            ]
        )

        self.assertEqual(
            result[
                "missing_required_fields"
            ],
            [],
        )

        self.assertEqual(
            result[
                "explicit_arguments"
            ],
            {
                "alarm_scope":
                    "61352"
            },
        )

    def test_known_fact_value_is_preserved_exactly(self):

        state = AgentState(
            user_message="Example",
            known_facts={
                "alarm_scope":
                    "61352_or_61353"
            },
        )

        result = (
            self.logfile_readiness(
                state
            )
        )

        self.assertEqual(
            result[
                "explicit_arguments"
            ][
                "alarm_scope"
            ],
            "61352_or_61353",
        )

    def test_agent_cannot_ask_for_already_known_fact(self):

        state = AgentState(
            user_message="Example",
            known_facts={
                "alarm_scope":
                    "61352"
            },
        )

        decision = AgentDecision(
            action=
                "ask_clarification",

            reason=
                "Need alarm scope.",

            requested_fact=
                "alarm_scope",

            question=
                "Which alarm scope applies?",
        )

        with self.assertRaises(
            PermissionError
        ):
            plan_next_action(
                state,
                StaticAdapter(
                    decision
                ),
                self.registry,
            )

    def test_agent_cannot_suggest_check_for_known_fact(self):

        state = AgentState(
            user_message="Example",
            known_facts={
                "low_voltage_reported":
                    True
            },
        )

        decision = AgentDecision(
            action=
                "suggest_inspection",

            reason=
                "Need voltage information.",

            requested_fact=
                "low_voltage_reported",

            suggestion=
                "Check the reported voltage condition.",
        )

        with self.assertRaises(
            PermissionError
        ):
            plan_next_action(
                state,
                StaticAdapter(
                    decision
                ),
                self.registry,
            )


if __name__ == "__main__":
    unittest.main()
