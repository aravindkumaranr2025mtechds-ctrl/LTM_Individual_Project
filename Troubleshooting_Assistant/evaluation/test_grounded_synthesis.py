import unittest

from pydantic import ValidationError

from app.services.grounded_synthesis import (
    GROUNDING_SYSTEM_INSTRUCTIONS,
    GroundedEvidenceBlock,
    GroundedSynthesisRequest,
    GroundedSynthesisResult,
    GroundedSynthesizer,
    build_grounded_prompt,
)
from app.services.ollama_grounded_synthesizer import (
    GroundedSynthesisProviderError,
    OllamaGroundedSynthesizer,
)


def make_request():
    return GroundedSynthesisRequest(
        query="What does alarm 8080 indicate?",
        grounded_synthesis_ready=True,
        evidence=[
            GroundedEvidenceBlock(
                evidence_id="E-001",
                source_label="Siemens manual",
                page_numbers=[25, 26],
                text=(
                    "Alarm 8080 evidence prepared "
                    "from the registered source."
                ),
            )
        ],
    )


class FakeProvider:
    @property
    def provider_name(self):
        return "fake"

    def synthesize(self, request):
        return GroundedSynthesisResult(
            answer_text="Grounded result.",
            provider="fake",
            model="fake-model",
        )


class RecordingOllama(
    OllamaGroundedSynthesizer
):
    def __init__(
        self,
        response=None,
    ):
        super().__init__()
        self.calls = []
        self.response = (
            response
            if response is not None
            else {
                "message": {
                    "content":
                        "The supplied evidence supports "
                        "this bounded explanation."
                }
            }
        )

    def _post_json(
        self,
        endpoint,
        payload,
    ):
        self.calls.append(
            (endpoint, payload)
        )

        return self.response


class GroundedSynthesisTests(
    unittest.TestCase
):

    def test_provider_interface_is_independent(self):
        self.assertIsInstance(
            FakeProvider(),
            GroundedSynthesizer,
        )

    def test_boundary_must_be_ready(self):
        with self.assertRaises(
            ValidationError
        ):
            GroundedSynthesisRequest(
                query="Motor does not start",
                grounded_synthesis_ready=False,
                evidence=[
                    {
                        "evidence_id": "E1",
                        "text": "Check source evidence.",
                    }
                ],
            )

    def test_evidence_is_required(self):
        with self.assertRaises(
            ValidationError
        ):
            GroundedSynthesisRequest(
                query="Motor does not start",
                grounded_synthesis_ready=True,
                evidence=[],
            )

    def test_provider_controls_not_accepted_in_request(self):
        payload = {
            "query": "Motor stalls",
            "grounded_synthesis_ready": True,
            "evidence": [
                {
                    "evidence_id": "E1",
                    "text": "One phase may be open.",
                }
            ],
            "model": "caller-selected-model",
        }

        with self.assertRaises(
            ValidationError
        ):
            GroundedSynthesisRequest(
                **payload
            )

    def test_prompt_contains_query_and_exact_evidence(self):
        request = make_request()

        prompt = build_grounded_prompt(
            request
        )

        self.assertIn(
            request.query,
            prompt,
        )
        self.assertIn(
            "[EVIDENCE E-001]",
            prompt,
        )
        self.assertIn(
            "Siemens manual",
            prompt,
        )
        self.assertIn(
            "Pages: 25, 26",
            prompt,
        )
        self.assertIn(
            request.evidence[0].text,
            prompt,
        )

        self.assertIn(
            "Use only the supplied grounded evidence",
            GROUNDING_SYSTEM_INSTRUCTIONS,
        )

    def test_ollama_adapter_uses_existing_local_model(self):
        provider = RecordingOllama()

        result = provider.synthesize(
            make_request()
        )

        self.assertEqual(
            len(provider.calls),
            1,
        )

        endpoint, payload = (
            provider.calls[0]
        )

        self.assertEqual(
            endpoint,
            "/api/chat",
        )
        self.assertEqual(
            payload["model"],
            "llama3.2:3b",
        )
        self.assertIs(
            payload["stream"],
            False,
        )
        self.assertEqual(
            payload["options"]["temperature"],
            0,
        )

        self.assertEqual(
            payload["messages"][0]["role"],
            "system",
        )
        self.assertEqual(
            payload["messages"][1]["role"],
            "user",
        )

        self.assertEqual(
            result.provider,
            "ollama",
        )
        self.assertEqual(
            result.model,
            "llama3.2:3b",
        )

    def test_empty_provider_response_fails_closed(self):
        provider = RecordingOllama(
            {
                "message": {
                    "content": "   "
                }
            }
        )

        with self.assertRaises(
            GroundedSynthesisProviderError
        ):
            provider.synthesize(
                make_request()
            )

    def test_generated_result_remains_unverified_and_safe(self):
        provider = RecordingOllama()

        result = provider.synthesize(
            make_request()
        )

        self.assertEqual(
            result.status,
            "generated_unverified",
        )
        self.assertIs(
            result.grounded_synthesis_ready,
            True,
        )
        self.assertIs(
            result.verification_required,
            True,
        )
        self.assertIs(
            result.diagnosis_confirmed,
            False,
        )
        self.assertIs(
            result.approved_for_automatic_execution,
            False,
        )


if __name__ == "__main__":
    unittest.main()