"""Evidence-sufficiency boundary for enterprise RAG.

This module does not decide diagnosis and does not treat vector
similarity as confidence.

It performs deterministic structural/provenance checks before
retrieved material may proceed toward grounded generation.

Semantic retrieval candidates require a later relevance assessment.
"""

from __future__ import annotations

from typing import (
    Any,
    Literal,
    TypedDict,
)


SufficiencyStatus = Literal[
    "ready_for_grounded_synthesis",
    "needs_relevance_assessment",
    "insufficient_evidence",
    "invalid_evidence_contract",
]


class EvidenceSufficiencyResult(
    TypedDict
):

    status: SufficiencyStatus

    allow_grounded_synthesis: bool

    requires_relevance_assessment: bool

    reason_code: str

    message: str

    evidence_count: int

    source_page_count: int

    retrieval_status: str | None

    uses_similarity_threshold: Literal[
        False
    ]

    diagnosis_confirmed: Literal[
        False
    ]

    approved_for_automatic_execution: Literal[
        False
    ]


_EXACT_READY_STATUSES = {
    "found",
    "confirmed_selection",
}


_SEMANTIC_CANDIDATE_STATUSES = {
    "candidates",
}


_INSUFFICIENT_STATUSES = {
    "not_found",
    "insufficient_evidence",
    "no_eligible_documents",
    "no_eligible_artifacts",
    "artifact_absent",
    "ambiguous_document",
    "ambiguous_source",
}


_TEXT_FIELDS = (
    "text",
    "matched_chunk_text",
    "manufacturer_guidance",
    "possible_cause",
    "alarm_title",
    "explanation",
    "reaction",
    "remedy",
)


def _result(
    *,
    status: SufficiencyStatus,
    allow_grounded_synthesis: bool,
    requires_relevance_assessment: bool,
    reason_code: str,
    message: str,
    evidence_count: int = 0,
    source_page_count: int = 0,
    retrieval_status: str | None = None,
) -> EvidenceSufficiencyResult:

    return {
        "status":
            status,

        "allow_grounded_synthesis":
            allow_grounded_synthesis,

        "requires_relevance_assessment":
            requires_relevance_assessment,

        "reason_code":
            reason_code,

        "message":
            message,

        "evidence_count":
            evidence_count,

        "source_page_count":
            source_page_count,

        "retrieval_status":
            retrieval_status,

        "uses_similarity_threshold":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }


def _nonempty_text(
    value: Any,
) -> bool:

    return (
        isinstance(
            value,
            str,
        )
        and bool(
            value.strip()
        )
    )


def _valid_pages(
    value: Any,
) -> list[int]:

    if not isinstance(
        value,
        list,
    ):

        return []

    pages = []

    for page in value:

        if (
            type(page) is int
            and page > 0
        ):

            pages.append(
                page
            )

        else:

            return []

    return pages


def _item_pages(
    item: dict,
) -> list[int]:

    for key in (
        "page_numbers",
        "section_page_numbers",
    ):

        pages = _valid_pages(
            item.get(
                key
            )
        )

        if pages:
            return pages


    for key in (
        "evidence",
        "answer_evidence",
    ):

        nested = item.get(
            key
        )

        if isinstance(
            nested,
            dict,
        ):

            pages = _valid_pages(
                nested.get(
                    "page_numbers"
                )
            )

            if pages:
                return pages


    source_cell = item.get(
        "source_cell"
    )

    if isinstance(
        source_cell,
        dict,
    ):

        page = source_cell.get(
            "pdf_page"
        )

        if (
            type(page) is int
            and page > 0
        ):

            return [
                page
            ]


    return []


def _item_has_text(
    item: dict,
) -> bool:

    for key in _TEXT_FIELDS:

        if _nonempty_text(
            item.get(
                key
            )
        ):

            return True


    for key in (
        "evidence",
        "answer_evidence",
    ):

        nested = item.get(
            key
        )

        if (
            isinstance(
                nested,
                dict,
            )
            and _nonempty_text(
                nested.get(
                    "quote"
                )
            )
        ):

            return True


    return False


def _has_document_identity(
    retrieval: dict,
    item: dict,
) -> bool:

    if _nonempty_text(
        retrieval.get(
            "document_id"
        )
    ):

        return True


    if _nonempty_text(
        item.get(
            "document_id"
        )
    ):

        return True


    nested = item.get(
        "evidence"
    )

    if isinstance(
        nested,
        dict,
    ):

        if _nonempty_text(
            nested.get(
                "document_id"
            )
        ):

            return True


        if _nonempty_text(
            nested.get(
                "parent_id"
            )
        ):

            return True


    # parent_id is a source-linked identity used by
    # several existing evidence contracts.
    if _nonempty_text(
        item.get(
            "parent_id"
        )
    ):

        return True


    if _nonempty_text(
        item.get(
            "record_id"
        )
    ):

        return True


    return False


def _unsafe_flag_present(
    value: Any,
) -> bool:

    if isinstance(
        value,
        dict,
    ):

        if (
            "diagnosis_confirmed"
            in value
            and value[
                "diagnosis_confirmed"
            ]
            is not False
        ):

            return True


        if (
            "approved_for_automatic_execution"
            in value
            and value[
                "approved_for_automatic_execution"
            ]
            is not False
        ):

            return True


        return any(
            _unsafe_flag_present(
                nested
            )

            for nested
            in value.values()
        )


    if isinstance(
        value,
        list,
    ):

        return any(
            _unsafe_flag_present(
                nested
            )

            for nested
            in value
        )


    return False


def assess_enterprise_evidence_sufficiency(
    source_result: dict,
) -> EvidenceSufficiencyResult:
    """Assess whether retrieved enterprise evidence may continue.

    This function performs structural and provenance sufficiency
    checks only.

    It deliberately does not:
    - use a cosine threshold,
    - convert similarity into confidence,
    - determine diagnosis,
    - decide whether semantic candidates truly answer the query.

    Semantic candidates therefore move to a later relevance
    assessment rather than directly to grounded synthesis.
    """

    if type(source_result) is not dict:

        raise TypeError(
            "source_result must be a dictionary."
        )


    if _unsafe_flag_present(
        source_result
    ):

        return _result(
            status=
                "invalid_evidence_contract",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "unsafe_evidence_flags",

            message=(
                "Retrieved evidence contains an unsafe "
                "diagnosis or automatic-execution flag."
            ),
        )


    source_status = (
        source_result.get(
            "status"
        )
    )


    if not isinstance(
        source_status,
        str,
    ):

        return _result(
            status=
                "invalid_evidence_contract",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "missing_source_status",

            message=(
                "The protected retrieval result has no "
                "valid status."
            ),
        )


    retrieval = source_result.get(
        "evidence"
    )


    if source_status in _INSUFFICIENT_STATUSES:

        retrieval_status = (
            retrieval.get(
                "status"
            )

            if isinstance(
                retrieval,
                dict,
            )

            else None
        )

        return _result(
            status=
                "insufficient_evidence",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "protected_retrieval_not_found",

            message=(
                "No eligible registered evidence was found "
                "for grounded guidance."
            ),

            retrieval_status=
                retrieval_status,
        )


    if source_status != "evidence_retrieved":

        return _result(
            status=
                "invalid_evidence_contract",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "unexpected_protected_tool_status",

            message=(
                "The protected enterprise evidence result "
                "has an unsupported status."
            ),
        )


    if not isinstance(
        retrieval,
        dict,
    ):

        return _result(
            status=
                "invalid_evidence_contract",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "missing_retrieval_payload",

            message=(
                "The protected result does not contain a "
                "valid retrieval evidence object."
            ),
        )


    retrieval_status = retrieval.get(
        "status"
    )


    if not isinstance(
        retrieval_status,
        str,
    ):

        return _result(
            status=
                "invalid_evidence_contract",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "missing_retrieval_status",

            message=(
                "The retrieval evidence has no valid status."
            ),
        )


    if retrieval_status in _INSUFFICIENT_STATUSES:

        return _result(
            status=
                "insufficient_evidence",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "retrieval_not_found",

            message=(
                "The registered knowledge sources did not "
                "return usable evidence for this request."
            ),

            retrieval_status=
                retrieval_status,
        )


    allowed_retrieval_statuses = (
        _EXACT_READY_STATUSES
        | _SEMANTIC_CANDIDATE_STATUSES
    )


    if (
        retrieval_status
        not in allowed_retrieval_statuses
    ):

        return _result(
            status=
                "invalid_evidence_contract",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "unexpected_retrieval_status",

            message=(
                "The retrieval result status is not part of "
                "the supported evidence-sufficiency contract."
            ),

            retrieval_status=
                retrieval_status,
        )


    results = retrieval.get(
        "results"
    )


    if not isinstance(
        results,
        list,
    ):

        return _result(
            status=
                "invalid_evidence_contract",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "results_not_list",

            message=(
                "Retrieved evidence results must be a list."
            ),

            retrieval_status=
                retrieval_status,
        )


    if not results:

        return _result(
            status=
                "insufficient_evidence",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "empty_evidence_results",

            message=(
                "Retrieval completed but returned no "
                "source evidence."
            ),

            retrieval_status=
                retrieval_status,
        )


    declared_count = retrieval.get(
        "results_count"
    )


    if (
        declared_count is not None
        and (
            type(declared_count) is not int
            or declared_count
            != len(
                results
            )
        )
    ):

        return _result(
            status=
                "invalid_evidence_contract",

            allow_grounded_synthesis=
                False,

            requires_relevance_assessment=
                False,

            reason_code=
                "results_count_mismatch",

            message=(
                "Retrieved evidence count does not match "
                "the returned result list."
            ),

            retrieval_status=
                retrieval_status,
        )


    pages = set()


    for index, item in enumerate(
        results,
        start=1,
    ):

        if type(item) is not dict:

            return _result(
                status=
                    "invalid_evidence_contract",

                allow_grounded_synthesis=
                    False,

                requires_relevance_assessment=
                    False,

                reason_code=
                    "invalid_evidence_item",

                message=(
                    "Retrieved evidence item "
                    f"{index} is not an object."
                ),

                evidence_count=
                    len(
                        results
                    ),

                retrieval_status=
                    retrieval_status,
            )


        if not _has_document_identity(
            retrieval,
            item,
        ):

            return _result(
                status=
                    "invalid_evidence_contract",

                allow_grounded_synthesis=
                    False,

                requires_relevance_assessment=
                    False,

                reason_code=
                    "missing_source_identity",

                message=(
                    "Retrieved evidence item "
                    f"{index} has no source-linked identity."
                ),

                evidence_count=
                    len(
                        results
                    ),

                retrieval_status=
                    retrieval_status,
            )


        item_pages = _item_pages(
            item
        )


        if not item_pages:

            return _result(
                status=
                    "invalid_evidence_contract",

                allow_grounded_synthesis=
                    False,

                requires_relevance_assessment=
                    False,

                reason_code=
                    "missing_source_pages",

                message=(
                    "Retrieved evidence item "
                    f"{index} has no valid source-page "
                    "reference."
                ),

                evidence_count=
                    len(
                        results
                    ),

                retrieval_status=
                    retrieval_status,
            )


        pages.update(
            item_pages
        )


        if not _item_has_text(
            item
        ):

            return _result(
                status=
                    "invalid_evidence_contract",

                allow_grounded_synthesis=
                    False,

                requires_relevance_assessment=
                    False,

                reason_code=
                    "missing_evidence_text",

                message=(
                    "Retrieved evidence item "
                    f"{index} contains no usable "
                    "source-supported text."
                ),

                evidence_count=
                    len(
                        results
                    ),

                source_page_count=
                    len(
                        pages
                    ),

                retrieval_status=
                    retrieval_status,
            )


    evidence_count = len(
        results
    )

    page_count = len(
        pages
    )


    # Exact / explicitly confirmed retrieval may proceed to
    # grounded synthesis once its structure is valid.
    if (
        retrieval_status
        in _EXACT_READY_STATUSES
    ):

        return _result(
            status=
                "ready_for_grounded_synthesis",

            allow_grounded_synthesis=
                True,

            requires_relevance_assessment=
                False,

            reason_code=
                "exact_source_evidence_available",

            message=(
                "Source-linked evidence is structurally "
                "sufficient for grounded synthesis."
            ),

            evidence_count=
                evidence_count,

            source_page_count=
                page_count,

            retrieval_status=
                retrieval_status,
        )


    # Semantic retrieval returns candidates. Their cosine ranking
    # is deliberately NOT interpreted as answer confidence.
    return _result(
        status=
            "needs_relevance_assessment",

        allow_grounded_synthesis=
            False,

        requires_relevance_assessment=
            True,

        reason_code=
            "semantic_candidates_require_relevance_check",

        message=(
            "Source-linked semantic candidates are available, "
            "but relevance to the requested guidance must be "
            "assessed before generation."
        ),

        evidence_count=
            evidence_count,

        source_page_count=
            page_count,

        retrieval_status=
            retrieval_status,
    )
