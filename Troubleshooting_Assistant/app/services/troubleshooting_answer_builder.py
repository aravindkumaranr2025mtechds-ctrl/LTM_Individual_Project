"""Convert explicit client answers into validated troubleshooting payloads.

This module performs deterministic field conversion only.
It does not infer missing facts, manufacturer, alarm scope, or diagnosis.
"""

from copy import deepcopy

from app.services.troubleshooting_input_guidance import (
    SUPPORTED_MODES,
)


ABB_INDEX = (
    "dde3696f00424107b1253d4dfd44a05b_"
    "ABB_LV_Motors_RevH_2022_"
    "structured_v1_ready_evidence_v1.json"
)


TRI_STATE_FIELDS = {
    "abb_stall": {
        "open_phase_reported",
        "wrong_application_reported",
        "overload_reported",
        "low_voltage_reported",
        "open_circuit_reported",
    },

    "siemens_licensing": {
        "options_activated",
        "license_key_set",
        "entered_key_covers_activated_options",
    },
}


def _tri_state(value):
    """Accept only explicit boolean/null-like form answers."""

    if value is True:
        return True

    if value is False:
        return False

    if value is None:
        return None

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "yes",
            "true",
        }:
            return True

        if normalized in {
            "no",
            "false",
        }:
            return False

        if normalized in {
            "unknown",
            "not known",
            "unsure",
        }:
            return None

    raise ValueError(
        "Tri-state answers must be yes, no, unknown, "
        "true, false, or null."
    )


def _observation_lists(mode, answers):
    fields = TRI_STATE_FIELDS[mode]

    observations = {}

    for field in fields:
        if field not in answers:
            continue

        value = _tri_state(
            answers[field]
        )

        if value is None:
            observations[field] = [
                None
            ]
        else:
            observations[field] = [
                value
            ]

    return observations


def build_structured_assistance(
    mode,
    answers,
):
    """Build one explicit structured_assistance payload."""

    if mode not in SUPPORTED_MODES:
        raise ValueError(
            "Unsupported troubleshooting mode."
        )

    if not isinstance(
        answers,
        dict,
    ):
        raise ValueError(
            "Answers must be an object."
        )

    answers = deepcopy(
        answers
    )

    if mode == "abb_stall":
        requested = answers.get(
            "requested_information"
        )

        allowed = {
            "list_possible_causes",
            "review_reports",
            "identify_cause",
        }

        if requested not in allowed:
            raise ValueError(
                "ABB requested_information must be explicitly selected."
            )

        observations = _observation_lists(
            mode,
            answers,
        )

        deferred = answers.get(
            "deferred_fact_ids",
            [],
        )

        if not isinstance(
            deferred,
            list,
        ):
            raise ValueError(
                "deferred_fact_ids must be a list."
            )

        return {
            "mode": "abb_stall",
            "payload": {
                "index_filename":
                    ABB_INDEX,
                "observations":
                    observations,
                "requested_information":
                    requested,
                "deferred_fact_ids":
                    deepcopy(deferred),
            },
        }

    if mode == "siemens_licensing":
        observations = _observation_lists(
            mode,
            answers,
        )

        alarm = answers.get(
            "reported_alarm_number"
        )

        if alarm not in {
            None,
            "8080",
            "8081",
        }:
            raise ValueError(
                "reported_alarm_number must be 8080, 8081, or null."
            )

        clarifications_used = answers.get(
            "clarifications_used",
            0,
        )

        if (
            type(clarifications_used) is not int
            or not 0 <= clarifications_used <= 2
        ):
            raise ValueError(
                "clarifications_used must be an integer from 0 to 2."
            )

        deferred = answers.get(
            "deferred_fact_ids",
            [],
        )

        if not isinstance(
            deferred,
            list,
        ):
            raise ValueError(
                "deferred_fact_ids must be a list."
            )

        return {
            "mode": "siemens_licensing",
            "payload": {
                "observations":
                    observations,
                "reported_alarm_number":
                    alarm,
                "clarifications_used":
                    clarifications_used,
                "deferred_fact_ids":
                    deepcopy(deferred),
            },
        }

    scope = answers.get(
        "alarm_scope"
    )

    allowed_scopes = {
        "61352_or_61353",
        "61352",
        "61353",
        "61358",
        "61352_or_61353_or_61358",
    }

    if scope not in allowed_scopes:
        raise ValueError(
            "Siemens logfile alarm_scope must be explicitly selected."
        )

    return {
        "mode": "siemens_logfile",
        "payload": {
            "alarm_scope":
                scope,
            "requested_information":
                "logfile_path_parameter",
        },
    }


from typing import Literal

from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


router = APIRouter()


class AnswerBuildRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    mode: Literal[
        "abb_stall",
        "siemens_licensing",
        "siemens_logfile",
    ]

    answers: dict = Field(
        default_factory=dict
    )


@router.post(
    "/development/troubleshoot/build",
    tags=["Development"],
    summary="Convert explicit form answers into a structured assistance payload",
    description=(
        "Performs deterministic answer conversion only. "
        "Missing facts, alarm scope, and diagnosis are not inferred."
    ),
)
def build_troubleshooting_payload(
    request: AnswerBuildRequest,
):
    try:
        structured = (
            build_structured_assistance(
                request.mode,
                request.answers,
            )
        )

        return {
            "status":
                "structured_payload_built",
            "structured_assistance":
                structured,
            "diagnosis_confirmed":
                False,
            "approved_for_automatic_execution":
                False,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
