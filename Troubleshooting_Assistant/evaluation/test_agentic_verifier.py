import unittest

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.dispatcher import (
    ToolObservation,
)

from app.services.agentic.verifier import (
    verify_return_information,
    verify_tool_observation,
)


class AgenticVerifierTests(
    unittest.TestCase
):

    def test_safe_tool_observation_passes(self):

        observation = ToolObservation(
            tool_name=
                "siemens_logfile",

            result={
                "status":
                    "answer_supported",

                "diagnosis_confirmed":
                    False,

                "approved_for_automatic_execution":
                    False,
            },
        )

        self.assertTrue(
            verify_tool_observation(
                observation
            )
        )

    def test_nested_unsafe_diagnosis_rejected(self):

        observation = ToolObservation(
            tool_name=
                "siemens_logfile",

            result={
                "nested": {
                    "diagnosis_confirmed":
                        True
                }
            },
        )

        with self.assertRaises(
            PermissionError
        ):
            verify_tool_observation(
                observation
            )

    def test_nested_automatic_execution_rejected(self):

        observation = ToolObservation(
            tool_name=
                "siemens_logfile",

            result={
                "nested": {
                    "approved_for_automatic_execution":
                        True
                }
            },
        )

        with self.assertRaises(
            PermissionError
        ):
            verify_tool_observation(
                observation
            )

    def test_return_information_requires_evidence(self):

        state = AgentState(
            user_message="Example"
        )

        decision = AgentDecision(
            action=
                "return_information",

            reason=
                "Provide supported information.",
        )

        with self.assertRaises(
            PermissionError
        ):
            verify_return_information(
                state,
                decision,
            )

    def test_return_information_allowed_after_tool_result(self):

        state = AgentState(
            user_message="Example",

            last_tool_result={
                "tool_name":
                    "siemens_logfile",

                "result": {
                    "status":
                        "answer_supported",

                    "diagnosis_confirmed":
                        False,

                    "approved_for_automatic_execution":
                        False,
                },
            },
        )

        decision = AgentDecision(
            action=
                "return_information",

            reason=
                "Evidence is available.",
        )

        self.assertTrue(
            verify_return_information(
                state,
                decision,
            )
        )


if __name__ == "__main__":
    unittest.main()
