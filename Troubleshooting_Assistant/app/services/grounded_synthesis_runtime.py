from __future__ import annotations

import os
from typing import Any

from app.services.grounded_synthesis import (
    GroundedEvidenceBlock,
    GroundedSynthesisRequest,
    GroundedSynthesizer,
)
from app.services.grounded_synthesis_input import (
    build_grounded_synthesis_input,
)
from app.services.grounded_synthesis_verifier import (
    verify_grounded_synthesis,
)
from app.services.ollama_grounded_synthesizer import (
    GroundedSynthesisProviderError,
    OllamaGroundedSynthesizer,
)


_ENABLE_VALUES = {
    "1",
    "true",
    "yes",
    "on",
}


def grounded_synthesis_runtime_enabled() -> bool:
    """
    Grounded synthesis is opt-in for the live runtime.

    Automated regression therefore never starts a real
    Ollama request unless the environment explicitly enables it.
    """

    value = os.getenv(
        "TA_ENABLE_GROUNDED_SYNTHESIS",
        "",
    )

    return (
        isinstance(value, str)
        and value.strip().casefold()
        in _ENABLE_VALUES
    )


def _build_provider_request(
    provider_input: dict[str, Any],
) -> GroundedSynthesisRequest:

    if not isinstance(
        provider_input,
        dict,
    ):
        raise TypeError(
            "Grounded provider input must be an object."
        )

    raw_evidence = provider_input.get(
        "evidence"
    )

    if not isinstance(
        raw_evidence,
        list,
    ) or not raw_evidence:
        raise ValueError(
            "Grounded provider input has no evidence."
        )

    evidence = []

    for item in raw_evidence:

        if not isinstance(
            item,
            dict,
        ):
            raise TypeError(
                "Grounded evidence item must be an object."
            )

        source_label = (
            item.get("source_filename")
            or item.get("document_id")
        )

        if source_label is not None:
            source_label = str(
                source_label
            )[:255]

        evidence.append(
            GroundedEvidenceBlock(
                evidence_id=
                    item["evidence_id"],

                text=
                    item["content"],

                source_label=
                    source_label,

                page_numbers=
                    list(
                        item.get(
                            "page_numbers",
                            [],
                        )
                    ),
            )
        )

    return GroundedSynthesisRequest(
        query=
            provider_input[
                "query"
            ],

        grounded_synthesis_ready=True,

        evidence=evidence,
    )


def execute_grounded_synthesis(
    query: str,
    grounded_evidence_bundle: dict[str, Any],
    *,
    grounded_synthesis_ready: bool,
    synthesizer: GroundedSynthesizer | None = None,
) -> dict[str, Any]:
    """
    Execute the bounded grounded-generation path.

    The generated model text is never marked as diagnosis-confirmed,
    automatically executable, or technician-release approved.
    """

    provider_input = (
        build_grounded_synthesis_input(
            query,
            grounded_evidence_bundle,
            grounded_synthesis_ready=
                grounded_synthesis_ready,
        )
    )

    request = _build_provider_request(
        provider_input
    )

    if synthesizer is None:
        synthesizer = (
            OllamaGroundedSynthesizer()
        )

    try:

        generated = synthesizer.synthesize(
            request
        )

    except GroundedSynthesisProviderError:

        return {
            "status":
                "provider_unavailable",

            "provider":
                getattr(
                    synthesizer,
                    "provider_name",
                    "ollama",
                ),

            "candidate_answer":
                None,

            "generation":
                None,

            "verification":
                None,

            "verification_required":
                True,

            "technician_release_approved":
                False,

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }

    verification = (
        verify_grounded_synthesis(
            request,
            generated,
        )
    )

    accepted = (
        verification.status
        == "accepted_for_review"
    )

    return {
        "status":
            verification.status,

        "provider":
            generated.provider,

        "model":
            generated.model,

        "candidate_answer":
            (
                verification.answer_text
                if accepted
                else None
            ),

        "generation":
            generated.model_dump(
                mode="json"
            ),

        "verification":
            verification.model_dump(
                mode="json"
            ),

        "verification_required":
            True,

        # Important boundary:
        # deterministic acceptance means only
        # "accepted_for_review".
        # It does NOT mean technician release.
        "technician_release_approved":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }
