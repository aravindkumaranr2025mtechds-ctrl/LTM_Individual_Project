from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


_TOKEN = re.compile(
    r"[A-Za-z0-9_$.-]+"
)

_IDENTIFIER = re.compile(
    r"""
    (?:
        [A-Za-z_$]+[A-Za-z0-9_$.-]*\d[A-Za-z0-9_$.-]*
        |
        \d+[A-Za-z_$.-]+[A-Za-z0-9_$.-]*
        |
        \d{3,}
    )
    """,
    re.VERBOSE,
)


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "check",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "machine",
    "manual",
    "my",
    "of",
    "on",
    "or",
    "please",
    "problem",
    "show",
    "system",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "why",
    "with",
}


def _result(
    *,
    status: str,
    reason_code: str,
    message: str,
    relevant: bool,
    query_anchor_count: int = 0,
    matched_anchor_count: int = 0,
    matched_result_indexes: list[int] | None = None,
):
    return {
        "status":
            status,

        "reason_code":
            reason_code,

        "message":
            message,

        "relevant":
            bool(
                relevant
            ),

        "allow_grounded_synthesis":
            bool(
                relevant
            ),

        "query_anchor_count":
            int(
                query_anchor_count
            ),

        "matched_anchor_count":
            int(
                matched_anchor_count
            ),

        "matched_result_indexes":
            list(
                matched_result_indexes
                or []
            ),

        "uses_similarity_threshold":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


def _normalize_tokens(
    text: str,
) -> list[str]:

    return [
        token.casefold()

        for token
        in _TOKEN.findall(
            text
        )

        if token.strip()
    ]


def _query_anchors(
    query: str,
) -> set[str]:

    anchors = set()

    for raw in _TOKEN.findall(
        query
    ):

        token = raw.casefold()

        if not token:
            continue

        if (
            token in _STOPWORDS
        ):
            continue

        if _IDENTIFIER.fullmatch(
            raw
        ):
            anchors.add(
                token
            )
            continue

        if (
            len(token) >= 4
            and not token.isdigit()
        ):
            anchors.add(
                token
            )

    return anchors


def _item_text(
    item: dict[str, Any],
) -> str:

    parts = []

    for key in (
        "text",
        "alarm_number",
        "alarm_title",
        "possible_cause",
        "manufacturer_guidance",
        "matched_text",
        "section_title",
        "title",
    ):

        value = item.get(
            key
        )

        if isinstance(
            value,
            str,
        ):

            value = value.strip()

            if value:
                parts.append(
                    value
                )

    return "\n".join(
        parts
    )


def assess_semantic_relevance(
    query: str,
    source_result: dict[str, Any],
):
    """
    Conservative deterministic relevance assessment for semantic
    retrieval candidates.

    This gate does not use cosine similarity as a confidence or
    relevance threshold. It only checks explicit textual/technical
    anchors between the user's validated query and attributable
    retrieved evidence.

    Lack of deterministic support produces an uncertain result,
    not an irrelevant diagnosis.
    """

    if not isinstance(
        query,
        str,
    ):
        raise TypeError(
            "query must be a string."
        )

    query = query.strip()

    if not query:
        return _result(
            status=
                "invalid",

            reason_code=
                "missing_query",

            message=
                "Semantic relevance cannot be assessed without "
                "an explicit query.",

            relevant=
                False,
        )


    if not isinstance(
        source_result,
        dict,
    ):
        return _result(
            status=
                "invalid",

            reason_code=
                "invalid_source_result",

            message=
                "Semantic relevance requires a retrieval result object.",

            relevant=
                False,
        )


    if (
        source_result.get(
            "mode"
        )
        != "semantic"
    ):
        return _result(
            status=
                "not_applicable",

            reason_code=
                "non_semantic_retrieval",

            message=
                "Semantic relevance assessment is not required for "
                "this retrieval mode.",

            relevant=
                False,
        )


    if (
        source_result.get(
            "status"
        )
        != "candidates"
    ):
        return _result(
            status=
                "invalid",

            reason_code=
                "semantic_candidates_not_available",

            message=
                "The retrieval result does not contain semantic "
                "candidate status.",

            relevant=
                False,
        )


    results = source_result.get(
        "results"
    )


    if not isinstance(
        results,
        list,
    ) or not results:

        return _result(
            status=
                "insufficient",

            reason_code=
                "no_semantic_candidates",

            message=
                "No semantic evidence candidates are available "
                "for relevance assessment.",

            relevant=
                False,
        )


    anchors = _query_anchors(
        query
    )


    if not anchors:

        return _result(
            status=
                "uncertain",

            reason_code=
                "no_explicit_query_anchors",

            message=
                "The query does not contain enough explicit technical "
                "anchors for deterministic relevance assessment.",

            relevant=
                False,
        )


    matched_anchors = set()

    matched_indexes = []


    for index, item in enumerate(
        results
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        text = _item_text(
            item
        )

        if not text:
            continue

        evidence_tokens = set(
            _normalize_tokens(
                text
            )
        )

        overlap = (
            anchors
            & evidence_tokens
        )

        if overlap:

            matched_anchors.update(
                overlap
            )

            matched_indexes.append(
                index
            )


    identifier_anchors = {
        anchor

        for anchor
        in anchors

        if _IDENTIFIER.fullmatch(
            anchor
        )
    }


    identifier_matches = (
        identifier_anchors
        & matched_anchors
    )


    if identifier_matches:

        return _result(
            status=
                "relevant",

            reason_code=
                "explicit_identifier_supported",

            message=
                "Retrieved evidence contains an explicit technical "
                "identifier from the validated query.",

            relevant=
                True,

            query_anchor_count=
                len(
                    anchors
                ),

            matched_anchor_count=
                len(
                    matched_anchors
                ),

            matched_result_indexes=
                matched_indexes,
        )


    if (
        len(
            matched_anchors
        )
        >= 2
    ):

        return _result(
            status=
                "relevant",

            reason_code=
                "multiple_query_anchors_supported",

            message=
                "Retrieved evidence contains multiple explicit "
                "technical anchors from the validated query.",

            relevant=
                True,

            query_anchor_count=
                len(
                    anchors
                ),

            matched_anchor_count=
                len(
                    matched_anchors
                ),

            matched_result_indexes=
                matched_indexes,
        )


    return _result(
        status=
            "uncertain",

        reason_code=
            "insufficient_explicit_relevance_support",

        message=
            "Semantic candidates were retrieved, but deterministic "
            "query-to-evidence support is insufficient. Similarity "
            "alone does not authorize grounded synthesis.",

        relevant=
            False,

        query_anchor_count=
            len(
                anchors
            ),

        matched_anchor_count=
            len(
                matched_anchors
            ),

        matched_result_indexes=
            matched_indexes,
    )
