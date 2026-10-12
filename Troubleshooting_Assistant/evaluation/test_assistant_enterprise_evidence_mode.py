from __future__ import annotations

import unittest

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

from app.services import (
    assistant_workflow,
    retrieval_service,
)


class AssistantEnterpriseEvidenceModeTests(
    unittest.TestCase
):

    def test_free_text_alone_does_not_become_query(
        self,
    ):

        request = (
            assistant_workflow
            .ConversationRequest(
                mode=
                    "enterprise_evidence",

                user_message=
                    "motor stalls one phase",

                answers={},
            )
        )


        with self.assertRaises(
            ValueError
        ):

            assistant_workflow.run_conversation(
                request
            )


    def test_explicit_query_uses_protected_tool_without_ollama(
        self,
    ):

        retrieved = {
            "results": [
                {
                    "parent_id":
                        "abb_parent",

                    "matched_chunk_id":
                        "abb_chunk",

                    "cosine_similarity":
                        0.8,
                }
            ],

            "qdrant_used":
                True,
        }


        with patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_configured",
            return_value=
                retrieved,
        ):

            response = (
                assistant_workflow
                .run_conversation(
                    assistant_workflow
                    .ConversationRequest(
                        mode=
                            "enterprise_evidence",

                        user_message=
                            "Search registered evidence",

                        answers={
                            "query":
                                "motor stalls",

                            "manufacturer":
                                "ABB",

                            "top_k":
                                5,
                        },
                    )
                )
            )


        self.assertEqual(
            response[
                "status"
            ],
            "evidence_retrieved",
        )


        self.assertEqual(
            response[
                "trace"
            ][
                "ollama_calls"
            ],
            0,
        )


        self.assertEqual(
            response[
                "trace"
            ][
                "tool_calls"
            ],
            1,
        )


        self.assertFalse(
            response[
                "diagnosis_confirmed"
            ]
        )


        self.assertFalse(
            response[
                "approved_for_automatic_execution"
            ]
        )


        self.assertIn(
            "itrs",
            response,
        )


    def test_metadata_is_forwarded_exactly(
        self,
    ):

        with patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_configured",
            return_value={
                "results": [],
                "qdrant_used": True,
            },
        ) as retrieval:

            response = (
                assistant_workflow
                .run_conversation(
                    assistant_workflow
                    .ConversationRequest(
                        mode=
                            "enterprise_evidence",

                        answers={
                            "query":
                                "  motor stalls  ",

                            "manufacturer":
                                "  Siemens  ",

                            "equipment_type":
                                "  motor  ",

                            "top_k":
                                3,
                        },
                    )
                )
            )


        retrieval.assert_called_once_with(
            query=
                "motor stalls",

            alarm_number=
                None,

            top_k=
                3,

            metadata_filters={
                "manufacturer":
                    "Siemens",

                "equipment_type":
                    "motor",
            },
        )


        self.assertEqual(
            response[
                "status"
            ],
            "not_found",
        )


    def test_forbidden_infrastructure_field_is_rejected(
        self,
    ):

        request = (
            assistant_workflow
            .ConversationRequest(
                mode=
                    "enterprise_evidence",

                answers={
                    "query":
                        "motor",

                    "backend":
                        "npz",
                },
            )
        )


        with patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_configured",
        ) as retrieval:

            with self.assertRaises(
                ValueError
            ):

                assistant_workflow.run_conversation(
                    request
                )


            retrieval.assert_not_called()


    def test_http_assistant_turn_exposes_enterprise_mode(
        self,
    ):

        with patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_configured",
            return_value={
                "results": [
                    {
                        "parent_id":
                            "abb_parent",

                        "matched_chunk_id":
                            "abb_chunk",

                        "cosine_similarity":
                            0.7,
                    }
                ],

                "qdrant_used":
                    True,
            },
        ):

            with TestClient(
                app
            ) as client:

                response = client.post(
                    "/assistant/turn",

                    json={
                        "mode":
                            "enterprise_evidence",

                        "user_message":
                            "Search evidence",

                        "answers": {
                            "query":
                                "motor stalls",

                            "manufacturer":
                                "ABB",
                        },
                    },
                )


        self.assertEqual(
            response.status_code,
            200,
        )


        payload = response.json()


        self.assertEqual(
            payload[
                "mode"
            ],
            "enterprise_evidence",
        )


        self.assertEqual(
            payload[
                "status"
            ],
            "evidence_retrieved",
        )


        self.assertEqual(
            payload[
                "trace"
            ][
                "ollama_calls"
            ],
            0,
        )


        self.assertFalse(
            payload[
                "diagnosis_confirmed"
            ]
        )


        self.assertFalse(
            payload[
                "approved_for_automatic_execution"
            ]
        )


if __name__ == "__main__":
    unittest.main()
