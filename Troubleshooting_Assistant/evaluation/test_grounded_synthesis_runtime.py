from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.services.grounded_synthesis import (
    GroundedSynthesisResult,
)
from app.services.grounded_synthesis_runtime import (
    execute_grounded_synthesis,
    grounded_synthesis_runtime_enabled,
)


class FakeSynthesizer:

    provider_name = "fake_test_provider"

    def __init__(
        self,
        answer,
    ):
        self.answer = answer
        self.calls = 0

    def synthesize(
        self,
        request,
    ):
        self.calls += 1

        return GroundedSynthesisResult(
            answer_text=
                self.answer,

            provider=
                self.provider_name,

            model=
                "fake-test-model",
        )


def bundle(
    content=(
        "Motor overload may cause the motor "
        "to stall. Reduce load."
    ),
):
    return {
        "schema_version":
            "grounded_evidence_bundle_v1",

        "retrieval_mode":
            "exact_source",

        "evidence_count":
            1,

        "evidence_ids":
            [
                "ev-test-1",
            ],

        "items":
            [
                {
                    "evidence_id":
                        "ev-test-1",

                    "document_id":
                        "doc-test",

                    "source_filename":
                        "manual.pdf",

                    "page_numbers":
                        [25],

                    "content":
                        content,

                    "retrieval_mode":
                        "exact_source",

                    "source_result_index":
                        0,

                    "metadata":
                        {},
                }
            ],

        "similarity_values_exposed":
            False,

        "similarity_used_as_confidence":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


class GroundedSynthesisRuntimeTests(
    unittest.TestCase
):

    def test_runtime_disabled_by_default(
        self,
    ):

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            self.assertFalse(
                grounded_synthesis_runtime_enabled()
            )


    def test_runtime_enable_flag(
        self,
    ):

        for value in (
            "1",
            "true",
            "YES",
            "On",
        ):
            with self.subTest(
                value=value
            ):

                with patch.dict(
                    os.environ,
                    {
                        "TA_ENABLE_GROUNDED_SYNTHESIS":
                            value,
                    },
                    clear=True,
                ):
                    self.assertTrue(
                        grounded_synthesis_runtime_enabled()
                    )


    def test_verified_candidate_is_accepted_for_review(
        self,
    ):

        fake = FakeSynthesizer(
            "Motor overload may cause the motor "
            "to stall. Reduce load."
        )

        result = execute_grounded_synthesis(
            "Why may this motor stall?",
            bundle(),
            grounded_synthesis_ready=True,
            synthesizer=fake,
        )

        self.assertEqual(
            fake.calls,
            1,
        )

        self.assertEqual(
            result["status"],
            "accepted_for_review",
        )

        self.assertIsNotNone(
            result["candidate_answer"]
        )

        self.assertFalse(
            result[
                "technician_release_approved"
            ]
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


    def test_unsupported_generated_number_is_rejected(
        self,
    ):

        fake = FakeSynthesizer(
            "Motor overload may cause stalling. "
            "Set the system to 9999."
        )

        result = execute_grounded_synthesis(
            "Why may this motor stall?",
            bundle(),
            grounded_synthesis_ready=True,
            synthesizer=fake,
        )

        self.assertEqual(
            result["status"],
            "rejected",
        )

        self.assertIsNone(
            result["candidate_answer"]
        )

        self.assertIn(
            "9999",
            result[
                "verification"
            ][
                "unsupported_numbers"
            ],
        )


    def test_false_ready_boundary_is_rejected_before_model(
        self,
    ):

        fake = FakeSynthesizer(
            "Motor overload."
        )

        with self.assertRaises(
            ValueError
        ):
            execute_grounded_synthesis(
                "Why may this motor stall?",
                bundle(),
                grounded_synthesis_ready=False,
                synthesizer=fake,
            )

        self.assertEqual(
            fake.calls,
            0,
        )


if __name__ == "__main__":
    unittest.main()
