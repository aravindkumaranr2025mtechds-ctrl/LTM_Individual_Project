from __future__ import annotations

import copy
import unittest

from pydantic import ValidationError


from app.services.grounded_guidance_contract import (
    GroundedGuidance,
    validate_grounded_guidance,
)


def valid_payload():

    return {
        "schema_version":
            "grounded_guidance_v1",

        "status":
            "ready",

        "reported_problem":
            "Motor stalls while running.",

        "ordering_basis":
            "source_list_no_mandatory_order",

        "ordering_note":
            (
                "The source lists these checks but "
                "no mandatory order is established."
            ),

        "steps": [
            {
                "step_id":
                    "start-1",

                "phase":
                    "start",

                "instruction":
                    (
                        "Begin with the source-supported "
                        "motor-stall checks."
                    ),

                "evidence_ids":
                    ["ev-001"],

                "page_numbers":
                    [25],

                "actionable":
                    False,
            },
            {
                "step_id":
                    "check-1",

                "phase":
                    "check",

                "instruction":
                    "Check lines for an open phase.",

                "evidence_ids":
                    ["ev-001"],

                "page_numbers":
                    [25],

                "actionable":
                    True,
            },
            {
                "step_id":
                    "observe-1",

                "phase":
                    "observe",

                "instruction":
                    "Record whether an open phase is reported.",

                "observation_request":
                    (
                        "Report whether the line check "
                        "shows an open phase."
                    ),

                "evidence_ids":
                    ["ev-001"],

                "page_numbers":
                    [25],

                "actionable":
                    False,
            },
        ],

        "limitations": [
            (
                "This evidence identifies a possible cause; "
                "it does not confirm a unique diagnosis."
            )
        ],

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


class GroundedGuidanceContractTests(
    unittest.TestCase
):

    def test_valid_grounded_guidance_passes(
        self,
    ):

        result = validate_grounded_guidance(
            valid_payload(),
            allowed_evidence_ids={
                "ev-001",
            },
        )

        self.assertEqual(
            result[
                "schema_version"
            ],
            "grounded_guidance_v1",
        )

        self.assertFalse(
            result[
                "diagnosis_confirmed"
            ]
        )

        self.assertFalse(
            result[
                "approved_for_automatic_execution"
            ]
        )


    def test_extra_fields_are_forbidden(
        self,
    ):

        payload = valid_payload()

        payload[
            "confidence"
        ] = 0.99


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_first_step_must_be_start(
        self,
    ):

        payload = valid_payload()

        payload[
            "steps"
        ][
            0
        ][
            "phase"
        ] = "check"


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_duplicate_step_ids_are_rejected(
        self,
    ):

        payload = valid_payload()

        payload[
            "steps"
        ][
            1
        ][
            "step_id"
        ] = "start-1"


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_every_step_requires_evidence(
        self,
    ):

        payload = valid_payload()

        payload[
            "steps"
        ][
            1
        ][
            "evidence_ids"
        ] = []


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_every_step_requires_source_page(
        self,
    ):

        payload = valid_payload()

        payload[
            "steps"
        ][
            1
        ][
            "page_numbers"
        ] = []


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_unknown_evidence_reference_is_rejected(
        self,
    ):

        payload = valid_payload()

        payload[
            "steps"
        ][
            1
        ][
            "evidence_ids"
        ] = [
            "invented-evidence",
        ]


        with self.assertRaisesRegex(
            ValueError,
            "outside the eligible evidence set",
        ):

            validate_grounded_guidance(
                payload,
                allowed_evidence_ids={
                    "ev-001",
                },
            )


    def test_observe_step_requires_observation_request(
        self,
    ):

        payload = valid_payload()

        del payload[
            "steps"
        ][
            2
        ][
            "observation_request"
        ]


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_stop_step_requires_stop_condition(
        self,
    ):

        payload = valid_payload()

        payload[
            "status"
        ] = "stop"

        payload[
            "steps"
        ].append(
            {
                "step_id":
                    "stop-1",

                "phase":
                    "stop",

                "instruction":
                    "Stop this troubleshooting sequence.",

                "evidence_ids":
                    ["ev-001"],

                "page_numbers":
                    [25],

                "actionable":
                    False,
            }
        )


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_terminal_step_must_be_last(
        self,
    ):

        payload = valid_payload()

        payload[
            "steps"
        ].insert(
            1,
            {
                "step_id":
                    "stop-1",

                "phase":
                    "stop",

                "instruction":
                    "Stop.",

                "stop_condition":
                    "Stop if safe continuation is not supported.",

                "evidence_ids":
                    ["ev-001"],

                "page_numbers":
                    [25],

                "actionable":
                    False,
            },
        )


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_escalate_status_requires_final_escalate_step(
        self,
    ):

        payload = valid_payload()

        payload[
            "status"
        ] = "escalate"


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_no_mandatory_order_requires_explicit_note(
        self,
    ):

        payload = valid_payload()

        payload[
            "ordering_note"
        ] = (
            "Checks are listed below."
        )


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_diagnosis_cannot_be_confirmed(
        self,
    ):

        payload = valid_payload()

        payload[
            "diagnosis_confirmed"
        ] = True


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_automatic_execution_cannot_be_approved(
        self,
    ):

        payload = valid_payload()

        payload[
            "approved_for_automatic_execution"
        ] = True


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_similarity_or_confidence_fields_are_not_contract_fields(
        self,
    ):

        payload = valid_payload()

        payload[
            "similarity_confidence"
        ] = 0.92


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_duplicate_evidence_ids_within_step_rejected(
        self,
    ):

        payload = valid_payload()

        payload[
            "steps"
        ][
            1
        ][
            "evidence_ids"
        ] = [
            "ev-001",
            "ev-001",
        ]


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_duplicate_pages_within_step_rejected(
        self,
    ):

        payload = valid_payload()

        payload[
            "steps"
        ][
            1
        ][
            "page_numbers"
        ] = [
            25,
            25,
        ]


        with self.assertRaises(
            ValidationError
        ):

            GroundedGuidance.model_validate(
                payload
            )


    def test_source_payload_not_mutated(
        self,
    ):

        payload = valid_payload()

        before = copy.deepcopy(
            payload
        )

        validate_grounded_guidance(
            payload,
            allowed_evidence_ids={
                "ev-001",
            },
        )

        self.assertEqual(
            payload,
            before,
        )


    def test_allowed_evidence_ids_must_be_set(
        self,
    ):

        with self.assertRaises(
            TypeError
        ):

            validate_grounded_guidance(
                valid_payload(),
                allowed_evidence_ids=[
                    "ev-001",
                ],
            )


if __name__ == "__main__":
    unittest.main()
