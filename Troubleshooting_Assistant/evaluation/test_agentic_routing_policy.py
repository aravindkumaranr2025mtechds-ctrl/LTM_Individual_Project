import unittest

from app.services.agentic.contracts import (
    AgentState,
)

from app.services.agentic.routing_policy import (
    choose_deterministic_ready_tool,
)

from app.services.agentic.tool_registry import (
    build_default_tool_registry,
)


class AgenticRoutingPolicyTests(
    unittest.TestCase
):

    def setUp(self):

        self.registry = (
            build_default_tool_registry()
        )

        self.tools = (
            self.registry.list_specs()
        )

    def test_explicit_ready_logfile_routes_without_llm(self):

        state = AgentState(
            user_message=
                "Which logfile parameter applies?",

            detected_intent=
                "request_logfile_parameter",

            known_facts={
                "alarm_scope":
                    "61352_or_61353"
            },
        )

        decision = (
            choose_deterministic_ready_tool(
                state,
                self.tools,
            )
        )

        self.assertIsNotNone(
            decision
        )

        self.assertEqual(
            decision.action,
            "call_tool",
        )

        self.assertEqual(
            decision.tool_name,
            "siemens_logfile",
        )

        self.assertEqual(
            decision.tool_arguments,
            {
                "alarm_scope":
                    "61352_or_61353"
            },
        )

    def test_missing_scope_does_not_route(self):

        state = AgentState(
            user_message=
                "Where is the logfile?",

            detected_intent=
                "request_logfile_parameter",

            unknown_facts=[
                "alarm_scope"
            ],
        )

        decision = (
            choose_deterministic_ready_tool(
                state,
                self.tools,
            )
        )

        self.assertIsNone(
            decision
        )

    def test_unknown_intent_does_not_route(self):

        state = AgentState(
            user_message="Example",

            detected_intent=
                "unmapped_intent",

            known_facts={
                "alarm_scope":
                    "61352"
            },
        )

        self.assertIsNone(
            choose_deterministic_ready_tool(
                state,
                self.tools,
            )
        )

    def test_previous_same_tool_is_not_repeated(self):

        state = AgentState(
            user_message="Example",

            detected_intent=
                "request_logfile_parameter",

            known_facts={
                "alarm_scope":
                    "61352"
            },

            last_tool_result={
                "tool_name":
                    "siemens_logfile",

                "result": {
                    "status":
                        "answer_supported"
                },

                "diagnosis_confirmed":
                    False,

                "approved_for_automatic_execution":
                    False,
            },
        )

        self.assertIsNone(
            choose_deterministic_ready_tool(
                state,
                self.tools,
            )
        )


if __name__ == "__main__":
    unittest.main()
