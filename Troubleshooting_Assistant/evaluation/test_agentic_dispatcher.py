import unittest
from copy import deepcopy

from app.services.agentic.contracts import (
    AgentDecision,
)

from app.services.agentic.dispatcher import (
    ProtectedToolDispatcher,
)

from app.services.agentic.tool_registry import (
    build_default_tool_registry,
)


class AgenticDispatcherTests(
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

    def call(
        self,
        tool_name,
        arguments,
    ):
        return self.dispatcher.dispatch(
            AgentDecision(
                action=
                    "call_tool",

                reason=
                    "Test protected tool call.",

                tool_name=
                    tool_name,

                tool_arguments=
                    arguments,
            )
        )

    def test_guidance_dispatch(self):
        observation = self.call(
            "troubleshooting_guidance",
            {},
        )

        self.assertEqual(
            observation.result[
                "status"
            ],
            "structured_input_guidance",
        )

        self.assertEqual(
            observation.result[
                "supported_modes"
            ],
            [
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            ],
        )

    def test_question_dispatch_requires_mode(self):
        with self.assertRaises(
            ValueError
        ):
            self.call(
                "troubleshooting_questions",
                {},
            )

    def test_question_dispatch(self):
        observation = self.call(
            "troubleshooting_questions",
            {
                "mode":
                    "siemens_logfile"
            },
        )

        self.assertEqual(
            observation.result[
                "mode"
            ],
            "siemens_logfile",
        )

        self.assertEqual(
            observation.result[
                "form"
            ][
                "fields"
            ][0][
                "field_id"
            ],
            "alarm_scope",
        )

    def test_logfile_dispatch(self):
        observation = self.call(
            "siemens_logfile",
            {
                "alarm_scope":
                    "61352_or_61353"
            },
        )

        assistance = (
            observation.result
        )

        self.assertEqual(
            assistance[
                "selected_policy"
            ],
            "siemens_logfile",
        )

        self.assertEqual(
            assistance[
                "result"
            ][
                "answer"
            ],
            "_PROTNAME[0]",
        )

    def test_logfile_scope_cannot_be_guessed(self):
        with self.assertRaises(
            ValueError
        ):
            self.call(
                "siemens_logfile",
                {
                    "alarm_scope":
                        "guessed_from_text"
                },
            )

    def test_unknown_argument_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            self.call(
                "siemens_logfile",
                {
                    "alarm_scope":
                        "61352",
                    "dangerous_override":
                        True,
                },
            )

    def test_non_tool_decision_rejected(self):
        decision = AgentDecision(
            action=
                "ask_clarification",

            reason=
                "Need explicit scope.",

            question=
                "Which alarm scope applies?",
        )

        with self.assertRaises(
            ValueError
        ):
            self.dispatcher.dispatch(
                decision
            )

    def test_dispatch_does_not_mutate_arguments(self):
        arguments = {
            "alarm_scope":
                "61352"
        }

        before = deepcopy(
            arguments
        )

        self.call(
            "siemens_logfile",
            arguments,
        )

        self.assertEqual(
            before,
            arguments,
        )

    def test_observation_safety_flags_false(self):
        observation = self.call(
            "siemens_logfile",
            {
                "alarm_scope":
                    "61352"
            },
        )

        self.assertFalse(
            observation.diagnosis_confirmed
        )

        self.assertFalse(
            observation.
            approved_for_automatic_execution
        )


if __name__ == "__main__":
    unittest.main()
