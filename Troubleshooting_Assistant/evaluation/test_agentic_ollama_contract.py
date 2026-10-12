import json
import unittest

from app.services.agentic.contracts import (
    AgentState,
)

from app.services.agentic.ollama_adapter import (
    OllamaAgentModelAdapter,
)

from app.services.agentic.tool_registry import (
    build_default_tool_registry,
)


class CaptureAdapter(
    OllamaAgentModelAdapter
):
    def __init__(self):
        super().__init__(
            model="fake-model"
        )

        self.payload = None

    def _post_json(
        self,
        endpoint,
        payload,
    ):
        self.payload = payload

        return {
            "message": {
                "content": json.dumps(
                    {
                        "action":
                            "ask_clarification",

                        "reason":
                            "Alarm scope is missing.",

                        "tool_name":
                            None,

                        "tool_arguments":
                            {},

                        "requested_fact":
                            "alarm_scope",

                        "question":
                            "Which alarm scope should be checked?",

                        "suggestion":
                            None,
                    }
                )
            }
        }


class OllamaContractTests(
    unittest.TestCase
):
    def test_prompt_contains_exact_field_contract(self):

        registry = (
            build_default_tool_registry()
        )

        adapter = CaptureAdapter()

        adapter.decide(
            AgentState(
                user_message=
                    "Where is the logfile?",
                unknown_facts=[
                    "alarm_scope"
                ],
            ),
            registry.list_specs(),
        )

        user_prompt = (
            adapter.payload[
                "messages"
            ][1][
                "content"
            ]
        )

        self.assertIn(
            '"required_field_names"',
            user_prompt,
        )

        self.assertIn(
            '"action"',
            user_prompt,
        )

        self.assertIn(
            '"reason"',
            user_prompt,
        )

        self.assertIn(
            '"tool_arguments"',
            user_prompt,
        )

        self.assertIn(
            '"example_ask_clarification"',
            user_prompt,
        )

        self.assertIn(
            '"example_call_tool"',
            user_prompt,
        )


if __name__ == "__main__":
    unittest.main()
