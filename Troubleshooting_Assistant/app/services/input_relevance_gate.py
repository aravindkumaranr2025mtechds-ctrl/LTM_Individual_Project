"""Conservative deterministic relevance gate.

This module screens free-form text before later domain routing.

It does not:
- infer manufacturer or equipment,
- extract machine observations,
- diagnose a fault,
- choose a retrieval backend,
- convert user free text into trusted structured facts.
"""

from __future__ import annotations

import re

from typing import (
    Literal,
    TypedDict,
)


GateStatus = Literal[
    "accepted",
    "needs_more_detail",
    "rejected",
]


InputClassification = Literal[
    "candidate_query",
    "needs_more_detail",
    "casual_or_irrelevant",
    "invalid_or_gibberish",
]


class InputRelevanceResult(
    TypedDict
):

    status: GateStatus

    classification: InputClassification

    continue_to_retrieval: bool

    reason_code: str

    message: str

    diagnosis_confirmed: Literal[
        False
    ]

    approved_for_automatic_execution: Literal[
        False
    ]


_CASUAL_EXACT = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "how are you doing",
    "hi how are you",
    "hello how are you",
    "thanks",
    "thank you",
    "bye",
    "goodbye",
    "who are you",
    "what can you do",
}


_CLEARLY_IRRELEVANT_PREFIXES = (
    "tell me a joke",
    "write me a poem",
    "write a poem",
    "sing a song",
    "what is the weather",
    "weather today",
    "cricket score",
    "football score",
)


_LOW_DETAIL_EXACT = {
    "help",
    "issue",
    "problem",
    "fault",
    "error",
    "machine",
    "machine issue",
    "machine problem",
    "motor",
    "motor issue",
    "motor problem",
    "network",
    "network issue",
    "system issue",
    "system problem",
    "not working",
}


_GIBBERISH_TOKENS = {
    "asdf",
    "asdfg",
    "asdfgh",
    "asdfghj",
    "qwerty",
    "qwertyui",
    "zxcv",
    "zxcvb",
    "xxxxx",
    "xxxxxx",
    "abcabc",
}


def _normalize_for_matching(
    text: str,
) -> str:
    """Normalize only for gate matching.

    This transformed text is never promoted into trusted facts.
    """

    characters = []

    for character in text.casefold():

        if character.isalnum():
            characters.append(
                character
            )

        else:
            characters.append(
                " "
            )

    return " ".join(
        "".join(
            characters
        ).split()
    )


def _result(
    *,
    status: GateStatus,
    classification: InputClassification,
    continue_to_retrieval: bool,
    reason_code: str,
    message: str,
) -> InputRelevanceResult:

    return {
        "status":
            status,

        "classification":
            classification,

        "continue_to_retrieval":
            continue_to_retrieval,

        "reason_code":
            reason_code,

        "message":
            message,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


def assess_input_relevance(
    text: str,
) -> InputRelevanceResult:
    """Screen text before domain routing and evidence retrieval.

    An accepted result means only that the text may continue to
    later routing. It does not mean the domain is supported or
    that any technical statement has been established as fact.
    """

    if type(text) is not str:

        raise TypeError(
            "Input text must be a string."
        )


    cleaned = " ".join(
        text.split()
    )


    if not cleaned:

        return _result(
            status=
                "rejected",

            classification=
                "invalid_or_gibberish",

            continue_to_retrieval=
                False,

            reason_code=
                "empty_input",

            message=(
                "Enter a usable request describing the "
                "equipment or system and what happened."
            ),
        )


    if len(cleaned) > 4000:

        return _result(
            status=
                "rejected",

            classification=
                "invalid_or_gibberish",

            continue_to_retrieval=
                False,

            reason_code=
                "input_too_long",

            message=(
                "The request is too long. Provide the main "
                "problem, relevant alarm or error, and the "
                "important observed condition."
            ),
        )


    normalized = (
        _normalize_for_matching(
            cleaned
        )
    )


    if not normalized:

        return _result(
            status=
                "rejected",

            classification=
                "invalid_or_gibberish",

            continue_to_retrieval=
                False,

            reason_code=
                "no_usable_characters",

            message=(
                "I could not identify a usable request. "
                "Describe the equipment or system and "
                "what happened."
            ),
        )


    # --------------------------------------------------------
    # Clearly conversational / casual input
    # --------------------------------------------------------

    if normalized in _CASUAL_EXACT:

        return _result(
            status=
                "rejected",

            classification=
                "casual_or_irrelevant",

            continue_to_retrieval=
                False,

            reason_code=
                "casual_input",

            message=(
                "This assistant is intended for industrial "
                "and workplace technical assistance. Describe "
                "the equipment, system, fault, alarm, error, "
                "or technical task you need help with."
            ),
        )


    # --------------------------------------------------------
    # Clearly non-technical tasks
    # --------------------------------------------------------

    if any(
        normalized.startswith(
            prefix
        )

        for prefix
        in _CLEARLY_IRRELEVANT_PREFIXES
    ):

        return _result(
            status=
                "rejected",

            classification=
                "casual_or_irrelevant",

            continue_to_retrieval=
                False,

            reason_code=
                "clearly_irrelevant_request",

            message=(
                "That request is outside the current technical "
                "assistance workflow. Describe an industrial "
                "equipment, IT, maintenance, or workplace "
                "technical problem instead."
            ),
        )


    # --------------------------------------------------------
    # Conservative obvious-gibberish handling
    #
    # Important:
    # We reject only known obvious nonsense patterns.
    # Unknown industrial abbreviations must not be discarded.
    # --------------------------------------------------------

    tokens = normalized.split()


    all_known_gibberish = bool(
        tokens
        and all(
            token
            in _GIBBERISH_TOKENS

            for token
            in tokens
        )
    )


    compact_letters = "".join(
        character

        for character
        in normalized

        if character.isalpha()
    )


    repeated_letter_only = bool(
        compact_letters
        and re.fullmatch(
            r"([a-z])\1{4,}",
            compact_letters,
        )
    )


    if (
        all_known_gibberish
        or repeated_letter_only
    ):

        return _result(
            status=
                "rejected",

            classification=
                "invalid_or_gibberish",

            continue_to_retrieval=
                False,

            reason_code=
                "obvious_gibberish",

            message=(
                "I could not identify a meaningful technical "
                "request. Describe the equipment or system, "
                "what happened, and any alarm, error, or "
                "observation."
            ),
        )


    # --------------------------------------------------------
    # Valid-looking but insufficiently detailed input
    # --------------------------------------------------------

    if normalized in _LOW_DETAIL_EXACT:

        return _result(
            status=
                "needs_more_detail",

            classification=
                "needs_more_detail",

            continue_to_retrieval=
                False,

            reason_code=
                "insufficient_problem_detail",

            message=(
                "Please provide more detail: identify the "
                "equipment or system, describe what happened, "
                "and include any alarm, error, symptom, or "
                "observed condition."
            ),
        )


    # --------------------------------------------------------
    # Candidate only.
    #
    # Actual domain support is intentionally NOT decided here.
    # --------------------------------------------------------

    return _result(
        status=
            "accepted",

        classification=
            "candidate_query",

        continue_to_retrieval=
            True,

        reason_code=
            "candidate_for_domain_routing",

        message=(
            "The request can continue to domain routing and "
            "evidence lookup. No technical facts were inferred "
            "from the free text."
        ),
    )
