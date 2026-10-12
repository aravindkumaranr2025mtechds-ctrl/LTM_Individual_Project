from __future__ import annotations

import unittest

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

from app.services import (
    assistant_workflow,
)

from app.services.assistant_workflow import (
    ConversationRequest,
)


class AssistantInputGateIntegrationTests(
    unittest.TestCase
):

    def request(
        self,
        query,
        *,
        user_message="",
    ):

        return ConversationRequest(
            mode=
                "enterprise_evidence",

            user_message=
                user_message,

            answers={
                "query":
                    query,
            },
        )


    def test_casual_input_stops_before_agent_loop(
        self,
    ):

        request = self.request(
            "Hi how are you"
        )

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
        ) as agent_loop:

            result = (
                assistant_workflow
                .run_conversation(
                    request
                )
            )


        agent_loop.assert_not_called()

        self.assertEqual(
            result["status"],
            "input_rejected",
        )

        self.assertEqual(
            result["trace"][
                "tool_calls"
            ],
            0,
        )

        self.assertEqual(
            result["trace"][
                "ollama_calls"
            ],
            0,
        )

        self.assertIsNone(
            result[
                "source_result"
            ]
        )


    def test_gibberish_stops_before_agent_loop(
        self,
    ):

        request = self.request(
            "asdfgh xxxxx"
        )

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
        ) as agent_loop:

            result = (
                assistant_workflow
                .run_conversation(
                    request
                )
            )


        agent_loop.assert_not_called()

        self.assertEqual(
            result["status"],
            "input_rejected",
        )

        self.assertEqual(
            result["input_gate"][
                "classification"
            ],
            "invalid_or_gibberish",
        )

        self.assertFalse(
            result["input_gate"][
                "continue_to_retrieval"
            ]
        )


    def test_low_detail_query_requests_clarification_without_agent(
        self,
    ):

        request = self.request(
            "motor issue"
        )

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
        ) as agent_loop:

            result = (
                assistant_workflow
                .run_conversation(
                    request
                )
            )


        agent_loop.assert_not_called()

        self.assertEqual(
            result["status"],
            "needs_more_detail",
        )

        self.assertEqual(
            result["trace"][
                "tool_calls"
            ],
            0,
        )

        self.assertEqual(
            result["trace"][
                "ollama_calls"
            ],
            0,
        )


    def test_user_message_cannot_override_explicit_query(
        self,
    ):

        request = self.request(
            "Hi how are you",
            user_message=(
                "ABB motor stalls while running"
            ),
        )

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
        ) as agent_loop:

            result = (
                assistant_workflow
                .run_conversation(
                    request
                )
            )


        agent_loop.assert_not_called()

        self.assertEqual(
            result["status"],
            "input_rejected",
        )

        self.assertEqual(
            result["input_gate"][
                "reason_code"
            ],
            "casual_input",
        )


    def test_enterprise_validation_runs_before_gate(
        self,
    ):

        with TestClient(
            app
        ) as client:

            response = client.post(
                "/assistant/turn",
                json={
                    "mode":
                        "enterprise_evidence",

                    "answers": {
                        "query":
                            "Hi how are you",

                        "database_path":
                            "forbidden.sqlite3",
                    },
                },
            )


        self.assertEqual(
            response.status_code,
            422,
        )


    def test_http_rejected_query_returns_safe_bounded_response(
        self,
    ):

        with patch.object(
            assistant_workflow,
            "run_agent_loop",
        ) as agent_loop:

            with TestClient(
                app
            ) as client:

                response = client.post(
                    "/assistant/turn",
                    json={
                        "mode":
                            "enterprise_evidence",

                        "answers": {
                            "query":
                                "asdfgh xxxxx",
                        },
                    },
                )


        agent_loop.assert_not_called()

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertEqual(
            body["status"],
            "input_rejected",
        )

        self.assertEqual(
            body["trace"][
                "tool_calls"
            ],
            0,
        )

        self.assertEqual(
            body["trace"][
                "ollama_calls"
            ],
            0,
        )

        self.assertFalse(
            body[
                "diagnosis_confirmed"
            ]
        )

        self.assertFalse(
            body[
                "approved_for_automatic_execution"
            ]
        )


if __name__ == "__main__":
    unittest.main()
