from __future__ import annotations

import unittest

from unittest.mock import patch

from app.services import retrieval_service

from app.services.agentic.contracts import (
    AgentDecision,
)

from app.services.agentic.dispatcher import (
    ProtectedToolDispatcher,
    _ALLOWED_ARGUMENTS,
    _ENTERPRISE_EVIDENCE_ARGUMENTS,
)

from app.services.agentic.tool_registry import (
    ToolRegistry,
    build_default_tool_registry,
    build_enterprise_evidence_tool_spec,
)

from app.services.agentic.verifier import (
    verify_tool_observation,
)


class EnterpriseEvidenceToolTests(
    unittest.TestCase
):

    def setUp(self):

        spec = (
            build_enterprise_evidence_tool_spec()
        )

        self.registry = ToolRegistry(
            [spec]
        )

        self.dispatcher = (
            ProtectedToolDispatcher(
                self.registry
            )
        )


    def test_enterprise_tool_is_opt_in(self):

        self.assertEqual(
            build_default_tool_registry().names(),
            [
                "troubleshooting_guidance",
                "troubleshooting_questions",
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            ],
        )

        self.assertNotIn(
            "enterprise_evidence_search",
            _ALLOWED_ARGUMENTS,
        )

        self.assertIn(
            "query",
            _ENTERPRISE_EVIDENCE_ARGUMENTS,
        )


    def test_trusted_retrieval_and_verifier(self):

        retrieved = {
            "results": [
                {
                    "parent_id":
                        "abb_parent",

                    "matched_chunk_id":
                        "abb_chunk",

                    "cosine_similarity":
                        0.75,
                }
            ],

            "qdrant_used":
                True,
        }


        with patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_configured",
            return_value=retrieved,
        ) as retrieval:

            observation = (
                self.dispatcher.dispatch(
                    AgentDecision(
                        action="call_tool",
                        reason="Retrieve evidence.",
                        tool_name=
                            "enterprise_evidence_search",

                        tool_arguments={
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


        retrieval.assert_called_once_with(
            query="motor stalls",
            alarm_number=None,
            top_k=5,
            metadata_filters={
                "manufacturer":
                    "ABB",
            },
        )


        self.assertTrue(
            verify_tool_observation(
                observation
            )
        )

        self.assertEqual(
            observation.result[
                "result"
            ][
                "status"
            ],
            "evidence_retrieved",
        )


    def test_not_found_is_bounded(self):

        with patch.object(
            retrieval_service,
            "retrieve_enterprise_sections_configured",
            return_value={
                "results": [],
                "qdrant_used": True,
            },
        ):

            observation = (
                self.dispatcher.dispatch(
                    AgentDecision(
                        action="call_tool",
                        reason="Search evidence.",
                        tool_name=
                            "enterprise_evidence_search",

                        tool_arguments={
                            "query":
                                "unsupported condition",
                        },
                    )
                )
            )


        body = (
            observation.result[
                "result"
            ]
        )


        self.assertEqual(
            body["status"],
            "not_found",
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


    def test_forbidden_controls_rejected(self):

        forbidden = (
            "access_level",
            "backend",
            "database_path",
            "qdrant_path",
            "collection_name",
            "vector_artifact_id",
        )


        for key in forbidden:

            with self.subTest(
                key=key
            ):

                with patch.object(
                    retrieval_service,
                    "retrieve_enterprise_sections_configured",
                ) as retrieval:

                    with self.assertRaises(
                        ValueError
                    ):

                        self.dispatcher.dispatch(
                            AgentDecision(
                                action="call_tool",
                                reason="Forbidden control.",
                                tool_name=
                                    "enterprise_evidence_search",

                                tool_arguments={
                                    "query":
                                        "motor",

                                    key:
                                        "unsafe",
                                },
                            )
                        )


                    retrieval.assert_not_called()


    def test_invalid_input_fails_closed(self):

        invalid = (
            {
                "query":
                    "",
            },
            {
                "query":
                    "   ",
            },
            {
                "query":
                    "motor",

                "top_k":
                    0,
            },
            {
                "query":
                    "motor",

                "top_k":
                    21,
            },
            {
                "query":
                    "motor",

                "top_k":
                    True,
            },
        )


        for arguments in invalid:

            with self.subTest(
                arguments=arguments
            ):

                with patch.object(
                    retrieval_service,
                    "retrieve_enterprise_sections_configured",
                ) as retrieval:

                    with self.assertRaises(
                        ValueError
                    ):

                        self.dispatcher.dispatch(
                            AgentDecision(
                                action="call_tool",
                                reason="Invalid input.",
                                tool_name=
                                    "enterprise_evidence_search",

                                tool_arguments=
                                    arguments,
                            )
                        )


                    retrieval.assert_not_called()


if __name__ == "__main__":
    unittest.main()
