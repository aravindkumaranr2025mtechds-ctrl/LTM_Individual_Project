from __future__ import annotations

import hashlib

from copy import deepcopy
from typing import Any


_TEXT_FIELDS = (
    "text",
    "evidence",
    "answer_evidence",
    "possible_cause",
    "manufacturer_guidance",
)


_METADATA_FIELDS = (
    "alarm_number",
    "alarm_title",
    "possible_cause",
    "manufacturer_guidance",
    "parent_id",
    "chunk_id",
    "matched_chunk_id",
    "section_title",
)


def _nonempty_text(
    value,
):
    return (
        isinstance(
            value,
            str,
        )
        and bool(
            value.strip()
        )
    )


def _normalize_pages(
    value,
):
    if not isinstance(
        value,
        list,
    ):
        return []


    pages = []


    for page in value:

        if (
            type(page)
            is not int
            or page < 1
        ):
            continue

        if page not in pages:
            pages.append(
                page
            )


    return sorted(
        pages
    )


def _item_pages(
    item,
):

    for key in (
        "page_numbers",
        "section_page_numbers",
        "matched_chunk_pages",
    ):

        pages = _normalize_pages(
            item.get(
                key
            )
        )

        if pages:
            return pages


    source = item.get(
        "source"
    )

    if isinstance(
        source,
        dict,
    ):

        for key in (
            "page_numbers",
            "section_page_numbers",
        ):

            pages = _normalize_pages(
                source.get(
                    key
                )
            )

            if pages:
                return pages


    return []


def _document_id(
    retrieval_result,
    item,
):

    value = item.get(
        "document_id"
    )

    if _nonempty_text(
        value
    ):
        return value.strip()


    source = item.get(
        "source"
    )

    if isinstance(
        source,
        dict,
    ):

        value = source.get(
            "document_id"
        )

        if _nonempty_text(
            value
        ):
            return value.strip()


    value = retrieval_result.get(
        "document_id"
    )

    if _nonempty_text(
        value
    ):
        return value.strip()


    return None


def _source_filename(
    retrieval_result,
    item,
):

    value = item.get(
        "source_filename"
    )

    if _nonempty_text(
        value
    ):
        return value.strip()


    source = item.get(
        "source"
    )

    if isinstance(
        source,
        dict,
    ):

        value = source.get(
            "source_filename"
        )

        if _nonempty_text(
            value
        ):
            return value.strip()


    value = retrieval_result.get(
        "source_filename"
    )

    if _nonempty_text(
        value
    ):
        return value.strip()


    return None


def _content(
    item,
):

    parts = []


    for field in _TEXT_FIELDS:

        value = item.get(
            field
        )

        if not _nonempty_text(
            value
        ):
            continue

        value = value.strip()

        if value not in parts:
            parts.append(
                value
            )


    return "\n".join(
        parts
    )


def _stable_evidence_id(
    *,
    document_id,
    page_numbers,
    content,
):

    material = (
        document_id
        + "\n"
        + ",".join(
            str(page)
            for page
            in page_numbers
        )
        + "\n"
        + content
    )


    digest = hashlib.sha256(
        material.encode(
            "utf-8"
        )
    ).hexdigest()


    return (
        "ev-"
        + digest[:12]
    )


def _selected_indexes(
    *,
    results,
    evidence_sufficiency,
    semantic_relevance,
):

    requires_relevance = bool(
        evidence_sufficiency.get(
            "requires_relevance_assessment"
        )
    )


    if requires_relevance:

        if not isinstance(
            semantic_relevance,
            dict,
        ):
            raise ValueError(
                "Semantic relevance assessment is required "
                "before packaging semantic candidates."
            )


        if not semantic_relevance.get(
            "allow_grounded_synthesis"
        ):
            raise ValueError(
                "Semantic relevance does not permit grounded synthesis."
            )


        indexes = semantic_relevance.get(
            "matched_result_indexes"
        )


        if not isinstance(
            indexes,
            list,
        ) or not indexes:
            raise ValueError(
                "Relevant semantic evidence must identify matched "
                "result indexes."
            )


        normalized = []


        for index in indexes:

            if (
                type(index)
                is not int
                or index < 0
                or index >= len(
                    results
                )
            ):
                raise ValueError(
                    "Semantic relevance contains an invalid result index."
                )

            if index not in normalized:
                normalized.append(
                    index
                )


        return normalized


    if not evidence_sufficiency.get(
        "allow_grounded_synthesis"
    ):
        raise ValueError(
            "Evidence sufficiency does not permit grounded synthesis."
        )


    return list(
        range(
            len(
                results
            )
        )
    )


def build_grounded_evidence_bundle(
    retrieval_result: dict[str, Any],
    evidence_sufficiency: dict[str, Any],
    semantic_relevance: (
        dict[str, Any]
        | None
    ) = None,
):
    """
    Package only evidence that has passed the existing evidence gates.

    The returned bundle is intended for a later grounded synthesizer.
    Retrieval similarity is deliberately not copied into this bundle
    and is never represented as confidence.
    """

    if not isinstance(
        retrieval_result,
        dict,
    ):
        raise TypeError(
            "retrieval_result must be a dictionary."
        )


    if not isinstance(
        evidence_sufficiency,
        dict,
    ):
        raise TypeError(
            "evidence_sufficiency must be a dictionary."
        )


    results = retrieval_result.get(
        "results"
    )


    if not isinstance(
        results,
        list,
    ) or not results:

        raise ValueError(
            "Grounded evidence packaging requires retrieval results."
        )


    indexes = _selected_indexes(
        results=
            results,

        evidence_sufficiency=
            evidence_sufficiency,

        semantic_relevance=
            semantic_relevance,
    )


    items = []

    seen_ids = set()


    for result_index in indexes:

        item = results[
            result_index
        ]


        if not isinstance(
            item,
            dict,
        ):
            raise ValueError(
                "Every eligible retrieval result must be an object."
            )


        document_id = _document_id(
            retrieval_result,
            item,
        )


        if not document_id:
            raise ValueError(
                "Eligible evidence is missing document identity."
            )


        pages = _item_pages(
            item
        )


        if not pages:
            raise ValueError(
                "Eligible evidence is missing attributable source pages."
            )


        content = _content(
            item
        )


        if not content:
            raise ValueError(
                "Eligible evidence is missing source-supported text."
            )


        evidence_id = (
            _stable_evidence_id(
                document_id=
                    document_id,

                page_numbers=
                    pages,

                content=
                    content,
            )
        )


        if evidence_id in seen_ids:
            continue


        seen_ids.add(
            evidence_id
        )


        packaged = {
            "evidence_id":
                evidence_id,

            "document_id":
                document_id,

            "source_filename":
                _source_filename(
                    retrieval_result,
                    item,
                ),

            "page_numbers":
                pages,

            "content":
                content,

            "retrieval_mode":
                retrieval_result.get(
                    "mode"
                ),

            "source_result_index":
                result_index,
        }


        metadata = {}


        for field in _METADATA_FIELDS:

            value = item.get(
                field
            )

            if value is None:
                continue

            if isinstance(
                value,
                str,
            ):
                value = value.strip()

                if not value:
                    continue

            metadata[
                field
            ] = deepcopy(
                value
            )


        packaged[
            "metadata"
        ] = metadata


        items.append(
            packaged
        )


    if not items:
        raise ValueError(
            "No eligible evidence remained after packaging."
        )


    return {
        "schema_version":
            "grounded_evidence_bundle_v1",

        "retrieval_mode":
            retrieval_result.get(
                "mode"
            ),

        "evidence_count":
            len(
                items
            ),

        "evidence_ids": [
            item[
                "evidence_id"
            ]

            for item
            in items
        ],

        "items":
            items,

        "similarity_values_exposed":
            False,

        "similarity_used_as_confidence":
            False,

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }
