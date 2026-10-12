"""Additive normalized provenance contract.

Existing source_result, specialist source structures, and
grounded_evidence_bundle remain authoritative and unchanged.

This module converts those existing structures into a stable
cross-workflow evidence_contract_v1 representation.
"""

from __future__ import annotations

import hashlib
import json

from copy import deepcopy
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class EvidenceContractItem(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    evidence_id: str = Field(
        min_length=1
    )

    evidence_id_origin: Literal[
        "source",
        "adapter",
    ]

    source_type: str = Field(
        min_length=1
    )

    document_id: str | None = None

    source_filename: str | None = None

    page_numbers: list[int] = Field(
        default_factory=list
    )

    content: str = ""

    metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class EvidenceContract(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    schema_version: Literal[
        "evidence_contract_v1"
    ] = "evidence_contract_v1"

    mode: str | None = None

    source_status: str | None = None

    source_validation: str | None = None

    evidence_count: int = Field(
        ge=0
    )

    items: list[
        EvidenceContractItem
    ] = Field(
        default_factory=list
    )

    diagnosis_confirmed: Literal[
        False
    ] = False

    approved_for_automatic_execution: Literal[
        False
    ] = False


def _text(
    value: Any,
) -> str | None:

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    return (
        value
        if value
        else None
    )


def _pages(
    value: Any,
) -> list[int]:

    if not isinstance(
        value,
        list,
    ):
        return []

    normalized = []

    for item in value:

        if (
            type(item) is int
            and item > 0
            and item not in normalized
        ):
            normalized.append(
                item
            )

    return normalized


def _adapter_id(
    *parts: Any,
) -> str:

    payload = json.dumps(
        parts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        default=str,
    )

    value = hashlib.sha256(
        payload.encode(
            "utf-8"
        )
    ).hexdigest()[:16]

    return (
        "ev-adapter-"
        + value
    )


def _make_item(
    *,
    evidence_id: str | None,
    source_type: str,
    document_id: str | None,
    source_filename: str | None,
    page_numbers: Any,
    content: Any,
    metadata: dict[str, Any],
    id_parts: tuple[Any, ...],
):

    normalized_id = _text(
        evidence_id
    )

    if normalized_id:

        origin = "source"

    else:

        normalized_id = _adapter_id(
            *id_parts
        )

        origin = "adapter"


    return EvidenceContractItem(
        evidence_id=
            normalized_id,

        evidence_id_origin=
            origin,

        source_type=
            source_type,

        document_id=
            _text(
                document_id
            ),

        source_filename=
            _text(
                source_filename
            ),

        page_numbers=
            _pages(
                page_numbers
            ),

        content=
            _text(
                content
            )
            or "",

        metadata=
            deepcopy(
                metadata
            ),
    )


def _grounded_bundle_items(
    response: dict[str, Any],
):

    bundle = response.get(
        "grounded_evidence_bundle"
    )

    if not isinstance(
        bundle,
        dict,
    ):
        return []


    raw_items = bundle.get(
        "items"
    )

    if not isinstance(
        raw_items,
        list,
    ):
        return []


    items = []


    for index, raw in enumerate(
        raw_items
    ):

        if not isinstance(
            raw,
            dict,
        ):
            continue


        metadata = deepcopy(
            raw.get(
                "metadata"
            )
            if isinstance(
                raw.get(
                    "metadata"
                ),
                dict,
            )
            else {}
        )


        metadata[
            "retrieval_mode"
        ] = raw.get(
            "retrieval_mode"
        )

        metadata[
            "source_result_index"
        ] = raw.get(
            "source_result_index"
        )


        items.append(
            _make_item(
                evidence_id=
                    raw.get(
                        "evidence_id"
                    ),

                source_type=
                    "grounded_evidence_bundle",

                document_id=
                    raw.get(
                        "document_id"
                    ),

                source_filename=
                    raw.get(
                        "source_filename"
                    ),

                page_numbers=
                    raw.get(
                        "page_numbers"
                    ),

                content=
                    raw.get(
                        "content"
                    ),

                metadata=
                    metadata,

                id_parts=(
                    "grounded_evidence_bundle",
                    index,
                    raw.get(
                        "document_id"
                    ),
                    raw.get(
                        "page_numbers"
                    ),
                    raw.get(
                        "content"
                    ),
                ),
            )
        )


    return items


def _abb_items(
    source: dict[str, Any],
):

    records = source.get(
        "source_records"
    )

    if not isinstance(
        records,
        list,
    ):
        return []


    items = []


    for index, record in enumerate(
        records
    ):

        if not isinstance(
            record,
            dict,
        ):
            continue


        evidence = (
            record.get(
                "evidence"
            )
            if isinstance(
                record.get(
                    "evidence"
                ),
                dict,
            )
            else {}
        )


        metadata = {
            "record_id":
                record.get(
                    "record_id"
                ),

            "possible_cause":
                record.get(
                    "possible_cause"
                ),

            "context_ids":
                deepcopy(
                    record.get(
                        "context_ids"
                    )
                    if isinstance(
                        record.get(
                            "context_ids"
                        ),
                        list,
                    )
                    else []
                ),

            "mapping_limit":
                record.get(
                    "mapping_limit"
                ),

            "evidence_field":
                evidence.get(
                    "field"
                ),

            "evidence_start":
                evidence.get(
                    "start"
                ),

            "evidence_end":
                evidence.get(
                    "end"
                ),

            "source_cell":
                deepcopy(
                    evidence.get(
                        "source_cell"
                    )
                ),

            "source_scope":
                source.get(
                    "source_scope"
                ),

            "source_validation":
                source.get(
                    "source_validation"
                ),
        }


        items.append(
            _make_item(
                evidence_id=
                    evidence.get(
                        "evidence_id"
                    ),

                source_type=
                    "abb_source_record",

                document_id=
                    "dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022",

                source_filename=
                    "dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022.pdf",

                page_numbers=
                    record.get(
                        "page_numbers"
                    ),

                content=
                    evidence.get(
                        "quote"
                    )
                    or record.get(
                        "possible_cause"
                    ),

                metadata=
                    metadata,

                id_parts=(
                    "abb_stall",
                    index,
                    record.get(
                        "record_id"
                    ),
                    evidence.get(
                        "quote"
                    ),
                    record.get(
                        "page_numbers"
                    ),
                ),
            )
        )


    return items


def _licensing_items(
    source: dict[str, Any],
):

    candidates = source.get(
        "candidates"
    )

    if not isinstance(
        candidates,
        list,
    ):
        return []


    items = []


    for index, candidate in enumerate(
        candidates
    ):

        if not isinstance(
            candidate,
            dict,
        ):
            continue


        evidence = (
            candidate.get(
                "evidence"
            )
            if isinstance(
                candidate.get(
                    "evidence"
                ),
                dict,
            )
            else {}
        )


        evaluation = (
            candidate.get(
                "evaluation"
            )
            if isinstance(
                candidate.get(
                    "evaluation"
                ),
                dict,
            )
            else {}
        )


        metadata = {
            "alarm_number":
                candidate.get(
                    "alarm_number"
                )
                or evidence.get(
                    "alarm_number"
                ),

            "parent_id":
                evidence.get(
                    "parent_id"
                ),

            "parent_text_sha256":
                evidence.get(
                    "parent_text_sha256"
                ),

            "page_scope":
                evidence.get(
                    "page_scope"
                ),

            "evidence_start":
                evidence.get(
                    "start"
                ),

            "evidence_end":
                evidence.get(
                    "end"
                ),

            "evaluation_status":
                evaluation.get(
                    "status"
                ),

            "prepared_filename":
                source.get(
                    "prepared_filename"
                ),

            "prepared_sha256":
                source.get(
                    "prepared_sha256"
                ),

            "source_validation":
                source.get(
                    "source_validation"
                ),
        }


        items.append(
            _make_item(
                evidence_id=
                    evidence.get(
                        "evidence_id"
                    ),

                source_type=
                    "siemens_licensing_candidate",

                document_id=
                    None,

                source_filename=
                    None,

                page_numbers=
                    evidence.get(
                        "page_numbers"
                    ),

                content=
                    evidence.get(
                        "quote"
                    ),

                metadata=
                    metadata,

                id_parts=(
                    "siemens_licensing",
                    index,
                    evidence.get(
                        "parent_id"
                    ),
                    candidate.get(
                        "alarm_number"
                    ),
                    evidence.get(
                        "page_numbers"
                    ),
                    evidence.get(
                        "quote"
                    ),
                    source.get(
                        "prepared_sha256"
                    ),
                ),
            )
        )


    return items


def _logfile_items(
    source: dict[str, Any],
):

    sections = source.get(
        "source_sections"
    )

    if not isinstance(
        sections,
        list,
    ):
        return []


    items = []


    for index, section in enumerate(
        sections
    ):

        if not isinstance(
            section,
            dict,
        ):
            continue


        evidence = (
            section.get(
                "answer_evidence"
            )
            if isinstance(
                section.get(
                    "answer_evidence"
                ),
                dict,
            )
            else {}
        )


        page_numbers = (
            evidence.get(
                "page_numbers"
            )
        )


        if not _pages(
            page_numbers
        ):

            page_numbers = (
                section.get(
                    "section_page_numbers"
                )
            )


        metadata = {
            "alarm_number":
                section.get(
                    "alarm_number"
                ),

            "parameter_name":
                section.get(
                    "parameter_name"
                ),

            "parent_id":
                section.get(
                    "parent_id"
                ),

            "parent_text_sha256":
                section.get(
                    "parent_text_sha256"
                ),

            "page_scope":
                evidence.get(
                    "page_scope"
                ),

            "section_page_numbers":
                deepcopy(
                    section.get(
                        "section_page_numbers"
                    )
                    if isinstance(
                        section.get(
                            "section_page_numbers"
                        ),
                        list,
                    )
                    else []
                ),

            "evidence_start":
                evidence.get(
                    "start"
                ),

            "evidence_end":
                evidence.get(
                    "end"
                ),

            "prepared_filename":
                source.get(
                    "prepared_filename"
                ),

            "prepared_sha256":
                source.get(
                    "prepared_sha256"
                ),

            "source_validation":
                source.get(
                    "source_validation"
                ),
        }


        items.append(
            _make_item(
                evidence_id=
                    evidence.get(
                        "evidence_id"
                    ),

                source_type=
                    "siemens_logfile_section",

                document_id=
                    source.get(
                        "document_id"
                    ),

                source_filename=
                    source.get(
                        "source_filename"
                    ),

                page_numbers=
                    page_numbers,

                content=
                    evidence.get(
                        "quote"
                    ),

                metadata=
                    metadata,

                id_parts=(
                    "siemens_logfile",
                    index,
                    source.get(
                        "document_id"
                    ),
                    section.get(
                        "parent_id"
                    ),
                    section.get(
                        "alarm_number"
                    ),
                    page_numbers,
                    evidence.get(
                        "quote"
                    ),
                ),
            )
        )


    return items


def build_evidence_contract(
    response: dict[str, Any],
) -> dict[str, Any]:

    if not isinstance(
        response,
        dict,
    ):
        raise TypeError(
            "response must be a dictionary."
        )


    if (
        response.get(
            "diagnosis_confirmed",
            False,
        )
        is not False
    ):
        raise ValueError(
            "Evidence contract cannot be built "
            "for a confirmed diagnosis."
        )


    if (
        response.get(
            "approved_for_automatic_execution",
            False,
        )
        is not False
    ):
        raise ValueError(
            "Evidence contract cannot be built "
            "for automatic execution approval."
        )


    mode = _text(
        response.get(
            "mode"
        )
    )

    source_status = _text(
        response.get(
            "status"
        )
    )


    source = (
        response.get(
            "source_result"
        )
        if isinstance(
            response.get(
                "source_result"
            ),
            dict,
        )
        else {}
    )


    source_validation = _text(
        source.get(
            "source_validation"
        )
    )


    # A grounded evidence bundle is already the strongest
    # normalized provenance structure in the project.
    items = _grounded_bundle_items(
        response
    )


    # Specialist adapters are used only when no grounded bundle
    # is already available, avoiding duplicate evidence.
    if not items:

        if mode == "abb_stall":

            items = _abb_items(
                source
            )


        elif mode == "siemens_licensing":

            items = _licensing_items(
                source
            )


        elif mode == "siemens_logfile":

            items = _logfile_items(
                source
            )


    contract = EvidenceContract(
        mode=
            mode,

        source_status=
            source_status,

        source_validation=
            source_validation,

        evidence_count=
            len(
                items
            ),

        items=
            items,
    )


    return contract.model_dump()
