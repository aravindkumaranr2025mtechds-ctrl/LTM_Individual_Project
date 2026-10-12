"""Deterministic safety verification for generated grounded synthesis.

This verifier intentionally does not claim semantic entailment.

It performs conservative checks before generated LLM text may move
toward a technician-facing presentation layer.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.grounded_synthesis import (
    GroundedSynthesisRequest,
    GroundedSynthesisResult,
)


_VERIFICATION_METHOD = (
    "deterministic_grounded_output_v1"
)


_TOKEN_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9_.:/\-]*[A-Za-z0-9]\b"
)

_WORD_RE = re.compile(
    r"\b[A-Za-z][A-Za-z\-']*\b"
)

_URL_RE = re.compile(
    r"https?://[^\s]+",
    flags=re.IGNORECASE,
)

_NUMBER_RE = re.compile(
    r"(?<![A-Za-z])"
    r"\d+(?:\.\d+)?"
    r"(?![A-Za-z])"
)


_STOP_WORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "into",
    "your",
    "using",
    "only",
    "what",
    "does",
    "according",
    "supplied",
    "grounded",
    "evidence",
    "query",
    "answer",
    "reported",
    "supports",
    "support",
    "technical",
    "information",
    "manual",
}


_ACTION_TERMS = {
    "adjust",
    "check",
    "delete",
    "disable",
    "disconnect",
    "enable",
    "energize",
    "inspect",
    "install",
    "isolate",
    "loosen",
    "measure",
    "open",
    "reboot",
    "reconfigure",
    "remove",
    "repair",
    "replace",
    "reset",
    "restart",
    "start",
    "stop",
    "tighten",
}


_FORBIDDEN_CERTAINTY_PHRASES = {
    "diagnosis confirmed",
    "diagnosis is confirmed",
    "confirmed diagnosis",
    "definitely caused by",
    "automatic execution approved",
    "safe to execute automatically",
    "proves that",
}


class GroundedSynthesisVerificationResult(
    BaseModel
):
    """Deterministic verification outcome."""

    model_config = ConfigDict(
        extra="forbid"
    )

    status: Literal[
        "accepted_for_review",
        "rejected",
    ]

    verification_method: Literal[
        "deterministic_grounded_output_v1"
    ] = _VERIFICATION_METHOD

    answer_text: str = Field(
        min_length=1,
        max_length=16000,
        strict=True,
    )

    rejection_reasons: list[str] = Field(
        default_factory=list
    )

    unsupported_technical_tokens: list[str] = Field(
        default_factory=list
    )

    unsupported_numbers: list[str] = Field(
        default_factory=list
    )

    unsupported_urls: list[str] = Field(
        default_factory=list
    )

    unsupported_action_terms: list[str] = Field(
        default_factory=list
    )

    evidence_overlap_terms: list[str] = Field(
        default_factory=list
    )

    semantic_entailment_verified: Literal[
        False
    ] = False

    technician_release_approved: Literal[
        False
    ] = False

    diagnosis_confirmed: Literal[
        False
    ] = False

    approved_for_automatic_execution: Literal[
        False
    ] = False


def _support_text(
    request: GroundedSynthesisRequest,
) -> str:

    pieces = [
        request.query,
    ]

    for evidence in request.evidence:

        pieces.append(
            evidence.evidence_id
        )

        pieces.append(
            evidence.text
        )

        if evidence.source_label:
            pieces.append(
                evidence.source_label
            )

        pieces.extend(
            str(page)
            for page in evidence.page_numbers
        )

    return "\n".join(pieces)


def _evidence_text(
    request: GroundedSynthesisRequest,
) -> str:

    return "\n".join(
        evidence.text
        for evidence in request.evidence
    )


def _technical_tokens(
    value: str,
) -> set[str]:

    result = set()

    for token in _TOKEN_RE.findall(
        value
    ):

        has_alpha = any(
            character.isalpha()
            for character in token
        )

        has_digit = any(
            character.isdigit()
            for character in token
        )

        looks_identifier = (
            "_" in token
            or (
                has_alpha
                and has_digit
            )
            or (
                len(token) >= 3
                and token.isupper()
            )
        )

        if looks_identifier:
            result.add(token)

    return result


def _numbers(
    value: str,
) -> set[str]:

    return set(
        _NUMBER_RE.findall(value)
    )


def _urls(
    value: str,
) -> set[str]:

    return {
        match.rstrip(
            ".,);]"
        )
        for match in _URL_RE.findall(
            value
        )
    }


def _words(
    value: str,
) -> set[str]:

    return {
        word.casefold()
        for word in _WORD_RE.findall(
            value
        )
        if (
            len(word) >= 3
            and word.casefold()
            not in _STOP_WORDS
        )
    }


def _unsupported_exact_items(
    answer_items: set[str],
    support_text: str,
) -> list[str]:

    support_folded = (
        support_text.casefold()
    )

    return sorted(
        item
        for item in answer_items
        if item.casefold()
        not in support_folded
    )


def verify_grounded_synthesis(
    request: GroundedSynthesisRequest,
    result: GroundedSynthesisResult,
) -> GroundedSynthesisVerificationResult:
    """Apply deterministic grounding and safety checks."""

    if not isinstance(
        request,
        GroundedSynthesisRequest,
    ):
        raise TypeError(
            "request must be a GroundedSynthesisRequest."
        )

    if not isinstance(
        result,
        GroundedSynthesisResult,
    ):
        raise TypeError(
            "result must be a GroundedSynthesisResult."
        )

    answer = result.answer_text.strip()

    support = _support_text(
        request
    )

    evidence_only = _evidence_text(
        request
    )

    rejection_reasons = []


    # --------------------------------------------------------
    # 1. VERIFY THE EXPECTED PRE-VERIFICATION STATE
    # --------------------------------------------------------

    if (
        result.status
        != "generated_unverified"
    ):
        rejection_reasons.append(
            "Unexpected synthesis status."
        )

    if (
        result.grounded_synthesis_ready
        is not True
    ):
        rejection_reasons.append(
            "Grounded synthesis boundary was not preserved."
        )

    if (
        result.verification_required
        is not True
    ):
        rejection_reasons.append(
            "Generated synthesis unexpectedly bypassed verification."
        )

    if (
        result.diagnosis_confirmed
        is not False
    ):
        rejection_reasons.append(
            "Generated synthesis attempted to confirm a diagnosis."
        )

    if (
        result.approved_for_automatic_execution
        is not False
    ):
        rejection_reasons.append(
            "Generated synthesis attempted to approve automatic execution."
        )


    # --------------------------------------------------------
    # 2. TECHNICAL IDENTIFIER SUPPORT
    # --------------------------------------------------------

    answer_technical = (
        _technical_tokens(
            answer
        )
    )

    unsupported_technical = (
        _unsupported_exact_items(
            answer_technical,
            support,
        )
    )

    if unsupported_technical:
        rejection_reasons.append(
            "Generated text introduced unsupported technical identifiers."
        )


    # --------------------------------------------------------
    # 3. NUMERIC SUPPORT
    # --------------------------------------------------------

    answer_numbers = _numbers(
        answer
    )

    unsupported_numbers = (
        _unsupported_exact_items(
            answer_numbers,
            support,
        )
    )

    if unsupported_numbers:
        rejection_reasons.append(
            "Generated text introduced unsupported numeric values."
        )


    # --------------------------------------------------------
    # 4. URL SUPPORT
    # --------------------------------------------------------

    answer_urls = _urls(
        answer
    )

    unsupported_urls = (
        _unsupported_exact_items(
            answer_urls,
            support,
        )
    )

    if unsupported_urls:
        rejection_reasons.append(
            "Generated text introduced unsupported URLs."
        )


    # --------------------------------------------------------
    # 5. MAINTENANCE ACTION SUPPORT
    # --------------------------------------------------------

    answer_words = _words(
        answer
    )

    evidence_words = _words(
        evidence_only
    )

    unsupported_actions = sorted(
        term
        for term in _ACTION_TERMS
        if (
            term in answer_words
            and term not in evidence_words
        )
    )

    if unsupported_actions:
        rejection_reasons.append(
            "Generated text introduced maintenance actions not present in evidence."
        )


    # --------------------------------------------------------
    # 6. UNSAFE CERTAINTY
    # --------------------------------------------------------

    answer_folded = (
        answer.casefold()
    )

    certainty_hits = sorted(
        phrase
        for phrase
        in _FORBIDDEN_CERTAINTY_PHRASES
        if phrase in answer_folded
    )

    if certainty_hits:
        rejection_reasons.append(
            "Generated text used prohibited diagnostic or execution certainty."
        )


    # --------------------------------------------------------
    # 7. MINIMUM EVIDENCE OVERLAP
    # --------------------------------------------------------

    overlap = sorted(
        answer_words
        & evidence_words
    )

    insufficient_statement = (
        "insufficient" in answer_folded
        or "not enough evidence"
        in answer_folded
    )

    if (
        not overlap
        and not insufficient_statement
    ):
        rejection_reasons.append(
            "Generated text has no meaningful lexical overlap with the supplied evidence."
        )


    status = (
        "rejected"
        if rejection_reasons
        else "accepted_for_review"
    )


    return GroundedSynthesisVerificationResult(
        status=status,
        answer_text=answer,
        rejection_reasons=
            rejection_reasons,
        unsupported_technical_tokens=
            unsupported_technical,
        unsupported_numbers=
            unsupported_numbers,
        unsupported_urls=
            unsupported_urls,
        unsupported_action_terms=
            unsupported_actions,
        evidence_overlap_terms=
            overlap,
    )