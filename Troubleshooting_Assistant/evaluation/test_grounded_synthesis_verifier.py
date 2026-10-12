import unittest

from app.services.grounded_synthesis import (
    GroundedEvidenceBlock,
    GroundedSynthesisRequest,
    GroundedSynthesisResult,
)
from app.services.grounded_synthesis_verifier import (
    verify_grounded_synthesis,
)


def make_request(
    text=(
        "Alarm 8080 indicates a licensing condition. "
        "Check the entered license key."
    ),
):
    return GroundedSynthesisRequest(
        query=(
            "What does alarm 8080 indicate?"
        ),
        grounded_synthesis_ready=True,
        evidence=[
            GroundedEvidenceBlock(
                evidence_id="E-8080",
                source_label=
                    "Siemens diagnostics manual",
                page_numbers=[25],
                text=text,
            )
        ],
    )


def make_result(answer):
    return GroundedSynthesisResult(
        answer_text=answer,
        provider="ollama",
        model="llama3.2:3b",
    )


class GroundedSynthesisVerifierTests(
    unittest.TestCase
):

    def test_supported_answer_is_accepted_for_review(self):

        result = verify_grounded_synthesis(
            make_request(),
            make_result(
                "Alarm 8080 indicates a licensing "
                "condition. Check the entered license key."
            ),
        )

        self.assertEqual(
            result.status,
            "accepted_for_review",
        )

        self.assertEqual(
            result.rejection_reasons,
            [],
        )

        self.assertFalse(
            result.semantic_entailment_verified
        )

        self.assertFalse(
            result.technician_release_approved
        )

        self.assertFalse(
            result.diagnosis_confirmed
        )

        self.assertFalse(
            result.approved_for_automatic_execution
        )


    def test_unsupported_number_is_rejected(self):

        result = verify_grounded_synthesis(
            make_request(),
            make_result(
                "Alarm 9999 indicates a licensing condition."
            ),
        )

        self.assertEqual(
            result.status,
            "rejected",
        )

        self.assertIn(
            "9999",
            result.unsupported_numbers,
        )


    def test_unsupported_identifier_is_rejected(self):

        request = GroundedSynthesisRequest(
            query="What marker is present?",
            grounded_synthesis_ready=True,
            evidence=[
                GroundedEvidenceBlock(
                    evidence_id="E1",
                    text=(
                        "The supported marker is "
                        "MOTOR_R32."
                    ),
                )
            ],
        )

        result = verify_grounded_synthesis(
            request,
            make_result(
                "The marker MOTOR_X99 is present."
            ),
        )

        self.assertEqual(
            result.status,
            "rejected",
        )

        self.assertIn(
            "MOTOR_X99",
            result.unsupported_technical_tokens,
        )


    def test_evidence_identifier_and_page_are_supported(self):

        result = verify_grounded_synthesis(
            make_request(),
            make_result(
                "Evidence E-8080 on page 25 describes "
                "alarm 8080 as a licensing condition."
            ),
        )

        self.assertEqual(
            result.status,
            "accepted_for_review",
        )


    def test_new_maintenance_action_is_rejected(self):

        request = make_request(
            "Alarm 8080 indicates a licensing condition."
        )

        result = verify_grounded_synthesis(
            request,
            make_result(
                "Alarm 8080 indicates a licensing "
                "condition. Restart the machine."
            ),
        )

        self.assertEqual(
            result.status,
            "rejected",
        )

        self.assertIn(
            "restart",
            result.unsupported_action_terms,
        )


    def test_action_present_in_evidence_is_allowed(self):

        result = verify_grounded_synthesis(
            make_request(),
            make_result(
                "Alarm 8080 indicates a licensing "
                "condition. Check the entered license key."
            ),
        )

        self.assertEqual(
            result.status,
            "accepted_for_review",
        )


    def test_diagnostic_certainty_is_rejected(self):

        result = verify_grounded_synthesis(
            make_request(),
            make_result(
                "The diagnosis is confirmed. "
                "Alarm 8080 indicates a licensing condition."
            ),
        )

        self.assertEqual(
            result.status,
            "rejected",
        )

        self.assertTrue(
            any(
                "certainty"
                in reason
                for reason
                in result.rejection_reasons
            )
        )


    def test_unsupported_url_is_rejected(self):

        result = verify_grounded_synthesis(
            make_request(),
            make_result(
                "Alarm 8080 indicates a licensing "
                "condition. See https://example.invalid/8080"
            ),
        )

        self.assertEqual(
            result.status,
            "rejected",
        )

        self.assertEqual(
            result.unsupported_urls,
            [
                "https://example.invalid/8080"
            ],
        )


    def test_no_evidence_overlap_is_rejected(self):

        result = verify_grounded_synthesis(
            make_request(),
            make_result(
                "There is unrelated contextual material available."
            ),
        )

        self.assertEqual(
            result.status,
            "rejected",
        )

        self.assertEqual(
            result.evidence_overlap_terms,
            [],
        )


if __name__ == "__main__":
    unittest.main()