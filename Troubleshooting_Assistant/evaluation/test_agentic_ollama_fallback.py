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


class GrammarFailureAdapter(
    OllamaAgentModelAdapter
):
    def __init__(self):
        super().__init__(
            model="fake-model"
        )

        self.calls = []

    def _post_json(
        self,
        endpoint,
        payload,
    ):
        self.calls.append(
            payload
        )

        if len(self.calls) == 1:
            raise RuntimeError(
                "Ollama HTTP 400: "
                "Failed to initialize samplers: "
                "failed to parse grammar"
            )

        return {
            "message": {
                "content": json.dumps(
                    {
                        "action":
                            "ask_clarification",

                        "reason":
                            "Alarm scope is unknown.",

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


class OtherFailureAdapter(
    OllamaAgentModelAdapter
):
    def __init__(self):
        super().__init__(
            model="fake-model"
        )

    def _post_json(
        self,
        endpoint,
        payload,
    ):
        raise RuntimeError(
            "Cannot reach the local Ollama service."
        )


class OllamaFallbackTests(
    unittest.TestCase
):
    def setUp(self):
        self.tools = (
            build_default_tool_registry().
            list_specs()
        )

    def test_grammar_failure_falls_back_to_json(self):
        adapter = (
            GrammarFailureAdapter()
        )

        decision = adapter.decide(
            AgentState(
                user_message=
                    "Where is the logfile?",
                unknown_facts=[
                    "alarm_scope"
                ],
            ),
            self.tools,
        )

        self.assertEqual(
            len(adapter.calls),
            2,
        )

        self.assertIsInstance(
            adapter.calls[0]["format"],
            dict,
        )

        self.assertEqual(
            adapter.calls[1]["format"],
            "json",
        )

        self.assertEqual(
            decision.action,
            "ask_clarification",
        )

        self.assertEqual(
            decision.requested_fact,
            "alarm_scope",
        )

    def test_non_grammar_failure_does_not_fallback(self):
        adapter = (
            OtherFailureAdapter()
        )

        with self.assertRaises(
            RuntimeError
        ):
            adapter.decide(
                AgentState(
                    user_message="Example"
                ),
                self.tools,
            )


if __name__ == "__main__":
    unittest.main()
