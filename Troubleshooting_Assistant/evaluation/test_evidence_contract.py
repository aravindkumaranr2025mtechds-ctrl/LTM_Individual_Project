from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.evidence_contract import (
    build_evidence_contract,
)


class EvidenceContractTests(
    unittest.TestCase
):

    def base(
        self,
        *,
        mode="unknown",
        status="unknown",
        source_result=None,
        bundle=None,
    ):

        response = {
            "mode":
                mode,

            "status":
                status,

            "source_result":
                (
                    source_result
                    if source_result
                    is not None
                    else {}
                ),

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }


        if bundle is not None:

            response[
                "grounded_evidence_bundle"
            ] = bundle


        return response


    def test_enterprise_preserves_native_evidence_id(
        self,
    ):

        response = self.base(
            mode=
                "enterprise_evidence",

            status=
                "evidence_retrieved",

            bundle={
                "items": [
                    {
                        "evidence_id":
                            "ev-native",

                        "document_id":
                            "doc-1",

                        "source_filename":
                            "manual.pdf",

                        "page_numbers":
                            [341],

                        "content":
                            "Supported source text.",

                        "retrieval_mode":
                            "exact_alarm",

                        "source_result_index":
                            0,

                        "metadata": {
                            "alarm_number":
                                "16783",
                        },
                    }
                ]
            },
        )


        contract = build_evidence_contract(
            response
        )


        self.assertEqual(
            contract[
                "schema_version"
            ],
            "evidence_contract_v1",
        )

        self.assertEqual(
            contract[
                "items"
            ][0][
                "evidence_id"
            ],
            "ev-native",
        )

        self.assertEqual(
            contract[
                "items"
            ][0][
                "evidence_id_origin"
            ],
            "source",
        )


    def test_abb_preserves_nested_evidence_id(
        self,
    ):

        response = self.base(
            mode=
                "abb_stall",

            status=
                "source_information",

            source_result={
                "source_validation":
                    "matched_current_prepared_json",

                "source_records": [
                    {
                        "record_id":
                            "r010",

                        "possible_cause":
                            "One phase may be open",

                        "page_numbers":
                            [25],

                        "context_ids":
                            ["context-25"],

                        "evidence": {
                            "evidence_id":
                                "r010:possible_cause",

                            "field":
                                "possible_cause",

                            "quote":
                                "One phase may be open",
                        },
                    }
                ],
            },
        )


        contract = build_evidence_contract(
            response
        )


        item = contract[
            "items"
        ][0]


        self.assertEqual(
            item[
                "evidence_id"
            ],
            "r010:possible_cause",
        )

        self.assertEqual(
            item[
                "page_numbers"
            ],
            [25],
        )

        self.assertEqual(
            item[
                "source_type"
            ],
            "abb_source_record",
        )


    def test_licensing_generates_deterministic_adapter_id(
        self,
    ):

        response = self.base(
            mode=
                "siemens_licensing",

            status=
                "description_supported",

            source_result={
                "prepared_sha256":
                    "prepared-sha",

                "source_validation":
                    "matched_inspected_parent_text_hashes",

                "candidates": [
                    {
                        "alarm_number":
                            "8080",

                        "evidence": {
                            "parent_id":
                                "section-8080",

                            "alarm_number":
                                "8080",

                            "quote":
                                "License evidence.",

                            "page_numbers":
                                [114],
                        },
                    }
                ],
            },
        )


        first = build_evidence_contract(
            response
        )

        second = build_evidence_contract(
            response
        )


        item = first[
            "items"
        ][0]


        self.assertEqual(
            item[
                "evidence_id_origin"
            ],
            "adapter",
        )

        self.assertTrue(
            item[
                "evidence_id"
            ].startswith(
                "ev-adapter-"
            )
        )

        self.assertEqual(
            item[
                "evidence_id"
            ],
            second[
                "items"
            ][0][
                "evidence_id"
            ],
        )


    def test_logfile_preserves_answer_evidence_id(
        self,
    ):

        response = self.base(
            mode=
                "siemens_logfile",

            status=
                "answer_supported",

            source_result={
                "document_id":
                    "doc-1",

                "source_filename":
                    "manual.pdf",

                "source_sections": [
                    {
                        "alarm_number":
                            "61352",

                        "parent_id":
                            "section-1",

                        "section_page_numbers":
                            [610, 611],

                        "answer_evidence": {
                            "evidence_id":
                                "section-1:parameter",

                            "quote":
                                "Check parameter.",

                            "page_numbers":
                                [610, 611],
                        },
                    }
                ],
            },
        )


        contract = build_evidence_contract(
            response
        )


        item = contract[
            "items"
        ][0]


        self.assertEqual(
            item[
                "evidence_id"
            ],
            "section-1:parameter",
        )

        self.assertEqual(
            item[
                "document_id"
            ],
            "doc-1",
        )

        self.assertEqual(
            item[
                "source_filename"
            ],
            "manual.pdf",
        )


    def test_page_numbers_are_normalized(
        self,
    ):

        response = self.base(
            mode=
                "abb_stall",

            source_result={
                "source_records": [
                    {
                        "record_id":
                            "r1",

                        "page_numbers":
                            [
                                25,
                                25,
                                0,
                                -1,
                                "25",
                                26,
                            ],

                        "evidence": {
                            "evidence_id":
                                "ev-1",

                            "quote":
                                "Evidence",
                        },
                    }
                ]
            },
        )


        contract = build_evidence_contract(
            response
        )


        self.assertEqual(
            contract[
                "items"
            ][0][
                "page_numbers"
            ],
            [
                25,
                26,
            ],
        )


    def test_empty_contract_is_safe(
        self,
    ):

        contract = build_evidence_contract(
            self.base()
        )


        self.assertEqual(
            contract[
                "evidence_count"
            ],
            0,
        )

        self.assertEqual(
            contract[
                "items"
            ],
            [],
        )

        self.assertIs(
            contract[
                "diagnosis_confirmed"
            ],
            False,
        )

        self.assertIs(
            contract[
                "approved_for_automatic_execution"
            ],
            False,
        )


    def test_unknown_mode_fails_closed_to_empty_items(
        self,
    ):

        response = self.base(
            mode=
                "future_unknown_mode",

            source_result={
                "unrecognized_records": [
                    {
                        "text":
                            "Do not infer this."
                    }
                ]
            },
        )


        contract = build_evidence_contract(
            response
        )


        self.assertEqual(
            contract[
                "evidence_count"
            ],
            0,
        )


    def test_rejects_confirmed_diagnosis(
        self,
    ):

        response = self.base()

        response[
            "diagnosis_confirmed"
        ] = True


        with self.assertRaises(
            ValueError
        ):

            build_evidence_contract(
                response
            )


    def test_rejects_automatic_execution(
        self,
    ):

        response = self.base()

        response[
            "approved_for_automatic_execution"
        ] = True


        with self.assertRaises(
            ValueError
        ):

            build_evidence_contract(
                response
            )


    def test_public_workflow_adds_contract(
        self,
    ):

        import app.services.assistant_workflow as workflow


        core = {
            "mode":
                "enterprise_evidence",

            "status":
                "evidence_retrieved",

            "source_result":
                {},

            "next_question":
                None,

            "trace": {
                "actions": [],
            },

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }


        with patch.object(
            workflow,
            "_run_conversation_core",
            return_value=
                dict(
                    core
                ),
        ):

            response = (
                workflow.run_conversation(
                    object()
                )
            )


        self.assertIn(
            "final_outcome",
            response,
        )

        self.assertIn(
            "evidence_contract",
            response,
        )

        self.assertEqual(
            response[
                "evidence_contract"
            ][
                "schema_version"
            ],
            "evidence_contract_v1",
        )


    def test_real_enterprise_16783_contract(
        self,
    ):

        os.environ.pop(
            "TA_ENABLE_GROUNDED_SYNTHESIS",
            None,
        )


        from app.main import app


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
                            "What does Siemens alarm 16783 mean?",

                        "manufacturer":
                            "Siemens",

                        "alarm_number":
                            "16783",
                    },
                },
            )


        self.assertEqual(
            response.status_code,
            200,
        )


        body = response.json()

        contract = body[
            "evidence_contract"
        ]


        self.assertEqual(
            contract[
                "evidence_count"
            ],
            1,
        )


        item = contract[
            "items"
        ][0]


        self.assertEqual(
            item[
                "evidence_id"
            ],
            "ev-38cbd3e7e3d8",
        )

        self.assertEqual(
            item[
                "page_numbers"
            ],
            [341],
        )

        self.assertEqual(
            item[
                "metadata"
            ][
                "alarm_number"
            ],
            "16783",
        )


    def test_real_specialist_contracts(
        self,
    ):

        os.environ.pop(
            "TA_ENABLE_GROUNDED_SYNTHESIS",
            None,
        )


        from app.main import app


        with TestClient(
            app
        ) as client:

            abb = client.post(
                "/assistant/turn",
                json={
                    "mode":
                        "abb_stall",

                    "answers": {
                        "requested_information":
                            "list_possible_causes",
                    },
                },
            )

            licensing = client.post(
                "/assistant/turn",
                json={
                    "mode":
                        "siemens_licensing",

                    "answers": {
                        "options_activated":
                            True,

                        "license_key_set":
                            False,
                    },
                },
            )

            logfile = client.post(
                "/assistant/turn",
                json={
                    "mode":
                        "siemens_logfile",

                    "answers": {
                        "alarm_scope":
                            "61352_or_61353",
                    },
                },
            )


        for response in (
            abb,
            licensing,
            logfile,
        ):

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertIn(
                "source_result",
                body,
            )

            self.assertIn(
                "evidence_contract",
                body,
            )

            self.assertGreater(
                body[
                    "evidence_contract"
                ][
                    "evidence_count"
                ],
                0,
            )


        abb_contract = (
            abb.json()[
                "evidence_contract"
            ]
        )

        self.assertEqual(
            abb_contract[
                "evidence_count"
            ],
            5,
        )

        self.assertEqual(
            abb_contract[
                "items"
            ][0][
                "page_numbers"
            ],
            [25],
        )


        licensing_item = (
            licensing.json()[
                "evidence_contract"
            ][
                "items"
            ][0]
        )

        self.assertEqual(
            licensing_item[
                "source_type"
            ],
            "siemens_licensing_candidate",
        )

        self.assertEqual(
            licensing_item[
                "evidence_id_origin"
            ],
            "adapter",
        )


        logfile_item = (
            logfile.json()[
                "evidence_contract"
            ][
                "items"
            ][0]
        )

        self.assertEqual(
            logfile_item[
                "source_type"
            ],
            "siemens_logfile_section",
        )

        self.assertTrue(
            logfile_item[
                "page_numbers"
            ],
        )


if __name__ == "__main__":
    unittest.main()
