"""Bounded ABB routing for enterprise evidence retrieval."""

from copy import deepcopy

from app.services import retrieval_service
from app.services.abb_retrieval_service import (
    retrieve_abb_records,
)


_APPROVED_ABB_VECTOR_STORE_FILENAME = (
    "dde3696f00424107b1253d4dfd44a05b_"
    "ABB_LV_Motors_RevH_2022_"
    "structured_v1_ready_bge_small.npz"
)


def _is_explicit_abb(
    metadata_filters,
):
    if not isinstance(
        metadata_filters,
        dict,
    ):
        return False

    manufacturer = (
        metadata_filters.get(
            "manufacturer"
        )
    )

    return (
        isinstance(
            manufacturer,
            str,
        )
        and
        manufacturer.strip().casefold()
        == "abb"
    )


def _pages(
    record,
):
    value = (
        record.get("pages")
        or
        record.get("page_numbers")
    )

    if isinstance(value, int):
        return [value]

    if isinstance(value, list):
        return [
            page
            for page in value
            if isinstance(page, int)
        ]

    return []


def _record_text(
    record,
):
    parts = []

    symptom = record.get(
        "symptom"
    )

    cause = record.get(
        "possible_cause"
    )

    guidance = record.get(
        "manufacturer_guidance"
    )

    if (
        isinstance(symptom, str)
        and symptom.strip()
    ):
        parts.append(
            "Symptom: "
            + symptom.strip()
        )

    if (
        isinstance(cause, str)
        and cause.strip()
    ):
        parts.append(
            "Possible cause: "
            + cause.strip()
        )

    if (
        isinstance(guidance, str)
        and guidance.strip()
    ):
        parts.append(
            "Manufacturer guidance: "
            + guidance.strip()
        )

    return "\n".join(parts)


def _normalize_record(
    abb,
    record,
    rank,
):
    pages = _pages(record)

    content = _record_text(
        record
    )

    record_id = record.get(
        "record_id"
    )

    symptom_id = record.get(
        "symptom_id"
    )

    similarity = (
        record.get(
            "cosine_similarity"
        )
        if record.get(
            "cosine_similarity"
        )
        is not None
        else record.get(
            "similarity"
        )
    )

    return {
        "rank":
            rank,

        "document_id":
            abb.get(
                "document_id"
            ),

        "source_filename":
            abb.get(
                "source_filename"
            ),

        "page_numbers":
            pages,

        "pages":
            pages,

        "source_page_numbers":
            pages,

        "content":
            content,

        "text":
            content,

        "record_id":
            record_id,

        "chunk_id":
            record_id,

        "parent_id":
            record_id,

        "symptom_id":
            symptom_id,

        "similarity":
            similarity,

        "cosine_similarity":
            similarity,

        "metadata": {
            "manufacturer":
                "ABB",

            "record_id":
                record_id,

            "symptom_id":
                symptom_id,

            "symptom":
                record.get(
                    "symptom"
                ),

            "possible_cause":
                record.get(
                    "possible_cause"
                ),

            "manufacturer_guidance":
                record.get(
                    "manufacturer_guidance"
                ),

            "document_reference":
                abb.get(
                    "document_reference"
                ),

            "revision":
                abb.get(
                    "revision"
                ),

            "source_row_number":
                (
                    record.get(
                        "source_row_number"
                    )
                    or
                    record.get(
                        "row_number"
                    )
                ),

            "context_ids":
                deepcopy(
                    record.get(
                        "context_ids",
                        [],
                    )
                ),
        },
    }


def _registered_search(
    *,
    query,
    alarm_number,
    top_k,
    metadata_filters,
):
    return (
        retrieval_service
        .retrieve_enterprise_sections_configured(
            query=query,
            alarm_number=alarm_number,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )
    )


def retrieve_enterprise_evidence_with_abb(
    *,
    query,
    alarm_number=None,
    top_k=5,
    metadata_filters=None,
):
    """
    Explicit ABB + non-alarm request:
        use approved ABB symptom router.

    Everything else:
        preserve existing registered enterprise retrieval.
    """

    if not _is_explicit_abb(
        metadata_filters
    ):
        return _registered_search(
            query=query,
            alarm_number=alarm_number,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )

    if alarm_number is not None:
        return _registered_search(
            query=query,
            alarm_number=alarm_number,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )

    abb = retrieve_abb_records(
        vector_store_filename=
            _APPROVED_ABB_VECTOR_STORE_FILENAME,

        query=query,

        top_k=min(
            top_k,
            10,
        ),
    )

    # Use the normal enterprise envelope as a template.
    try:

        enterprise = _registered_search(
            query=query,
            alarm_number=None,
            top_k=top_k,
            metadata_filters=
                metadata_filters,
        )

        if not isinstance(
            enterprise,
            dict,
        ):
            enterprise = {}

    except Exception:
        enterprise = {}

    enterprise = deepcopy(
        enterprise
    )

    enterprise[
        "retrieval_route"
    ] = (
        "approved_abb_symptom_router"
    )

    enterprise[
        "manufacturer"
    ] = "ABB"

    enterprise[
        "document_id"
    ] = abb.get(
        "document_id"
    )

    enterprise[
        "source_filename"
    ] = abb.get(
        "source_filename"
    )

    enterprise[
        "abb_symptom_routing"
    ] = {
        "selected_symptom_id":
            abb.get(
                "selected_symptom_id"
            ),

        "selected_symptom":
            abb.get(
                "selected_symptom"
            ),

        "symptom_candidates":
            deepcopy(
                abb.get(
                    "symptom_candidates",
                    [],
                )
            ),
    }

    selected_symptom = abb.get(
        "selected_symptom"
    )

    # The user may describe the same symptom with different wording.
    # ABB semantic routing has already selected one canonical symptom
    # under the existing ambiguity-margin control. Downstream
    # deterministic relevance checking may use that canonical wording,
    # while the original user query remains unchanged elsewhere.
    enterprise[
        "relevance_query"
    ] = (
        selected_symptom.strip()
        if (
            isinstance(
                selected_symptom,
                str,
            )
            and selected_symptom.strip()
        )
        else query
    )

    abb_status = abb.get(
        "status"
    )

    if (
        abb_status
        == "needs_clarification"
    ):

        clarification = deepcopy(
            abb.get(
                "clarification"
            )
            or {}
        )

        enterprise[
            "status"
        ] = "needs_clarification"

        enterprise[
            "results"
        ] = []

        enterprise[
            "results_count"
        ] = 0

        enterprise[
            "clarification"
        ] = clarification

        enterprise[
            "message"
        ] = (
            clarification.get(
                "question"
            )
            or
            abb.get(
                "message"
            )
            or
            (
                "More detail is required "
                "to identify the ABB symptom."
            )
        )

        enterprise[
            "diagnosis_confirmed"
        ] = False

        enterprise[
            "approved_for_automatic_execution"
        ] = False

        return enterprise

    records = abb.get(
        "results"
    )

    if not isinstance(
        records,
        list,
    ):
        records = []

    normalized = [
        _normalize_record(
            abb,
            record,
            rank,
        )

        for rank, record
        in enumerate(
            records,
            start=1,
        )

        if isinstance(
            record,
            dict,
        )
    ]

    enterprise[
        "results"
    ] = normalized

    enterprise[
        "results_count"
    ] = len(
        normalized
    )

    if normalized:

        # ABB symptom selection is semantic retrieval.
        # It must enter the existing semantic-relevance gate
        # rather than being treated as exact/confirmed evidence.
        enterprise[
            "status"
        ] = "candidates"

        enterprise[
            "message"
        ] = (
            "Approved ABB manufacturer "
            "evidence was retrieved for "
            "the routed symptom."
        )

    else:

        enterprise[
            "status"
        ] = "not_found"

        enterprise[
            "message"
        ] = (
            abb.get(
                "message"
            )
            or
            (
                "No approved ABB manufacturer "
                "records matched the symptom."
            )
        )

    enterprise[
        "diagnosis_confirmed"
    ] = False

    enterprise[
        "approved_for_automatic_execution"
    ] = False

    return enterprise
