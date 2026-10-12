import unittest

from app.services.agentic.completion_policy import (
    assess_terminal_evidence,
)

from app.services.agentic.dispatcher import (
    ToolObservation,
)


class AgenticCompletionPolicyTests(
    unittest.TestCase
):

    def test_logfile_answer_is_terminal(self):

        result = assess_terminal_evidence(
            ToolObservation(
                tool_name=
                    "siemens_logfile",

                result={
                    "result": {
                        "status":
                            "answer_supported",

                        "answer":
                            "_PROTNAME[0]",
                    }
                },
            )
        )

        self.assertTrue(
            result.terminal_supported
        )

        self.assertEqual(
            result.result_status,
            "answer_supported",
        )

    def test_licensing_description_is_terminal(self):

        result = assess_terminal_evidence(
            ToolObservation(
                tool_name=
                    "siemens_licensing",

                result={
                    "result": {
                        "status":
                            "description_supported"
                    }
                },
            )
        )

        self.assertTrue(
            result.terminal_supported
        )

    def test_abb_source_information_is_terminal(self):

        result = assess_terminal_evidence(
            ToolObservation(
                tool_name=
                    "abb_stall",

                result={
                    "result": {
                        "status":
                            "source_information"
                    }
                },
            )
        )

        self.assertTrue(
            result.terminal_supported
        )

    def test_guidance_is_not_terminal_evidence(self):

        result = assess_terminal_evidence(
            ToolObservation(
                tool_name=
                    "troubleshooting_guidance",

                result={
                    "status":
                        "structured_input_guidance",

                    "diagnosis_confirmed":
                        False,

                    "approved_for_automatic_execution":
                        False,
                },
            )
        )

        self.assertFalse(
            result.terminal_supported
        )


if __name__ == "__main__":
    unittest.main()
