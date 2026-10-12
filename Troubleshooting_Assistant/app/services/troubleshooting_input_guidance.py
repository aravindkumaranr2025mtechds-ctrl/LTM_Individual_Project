"""Machine-readable guidance for explicit troubleshooting inputs.

This module describes what a caller must supply before one of the
development-validated assistance policies can run.

It does not infer manufacturer, condition facts, alarm scope,
or diagnosis from free text.
"""

from copy import deepcopy
from typing import Literal

from fastapi import APIRouter


router = APIRouter()


GuidanceMode = Literal[
    "abb_stall",
    "siemens_licensing",
    "siemens_logfile",
]


SUPPORTED_MODES = {
    "abb_stall": {
        "title": "ABB Motor stalls assistance",
        "description": (
            "Use only when the caller explicitly selects the ABB Motor stalls "
            "policy and supplies structured reports."
        ),
        "required_payload_fields": [
            "index_filename",
            "observations",
            "requested_information",
        ],
        "optional_payload_fields": [
            "deferred_fact_ids",
        ],
        "requested_information_values": [
            "list_possible_causes",
            "review_reports",
            "identify_cause",
        ],
        "observation_fields": [
            "open_phase_reported",
            "wrong_application_reported",
            "overload_reported",
            "low_voltage_reported",
            "open_circuit_reported",
        ],
        "observation_value_format": (
            "Each observation field is a list containing explicit "
            "true, false, or null reports."
        ),
        "limitations": [
            "Free-text symptom wording is not converted into observation facts.",
            "Supported reports do not establish a unique diagnosis.",
            "Automatic execution is never approved.",
        ],
    },

    "siemens_licensing": {
        "title": "Siemens 8080 / 8081 licensing comparison",
        "description": (
            "Use only for the bounded Siemens licensing comparison policy."
        ),
        "required_payload_fields": [
            "observations",
        ],
        "optional_payload_fields": [
            "prepared_filename",
            "reported_alarm_number",
            "clarifications_used",
            "deferred_fact_ids",
        ],
        "reported_alarm_number_values": [
            "8080",
            "8081",
        ],
        "observation_fields": [
            "options_activated",
            "license_key_set",
            "entered_key_covers_activated_options",
        ],
        "observation_value_format": (
            "Each observation field is a list containing explicit "
            "true, false, or null reports."
        ),
        "clarification_budget": 2,
        "limitations": [
            "The policy compares only Siemens alarm descriptions 8080 and 8081.",
            "An alarm number is not inferred from symptom text.",
            "Description support is not a confirmed machine diagnosis.",
            "Automatic execution is never approved.",
        ],
    },

    "siemens_logfile": {
        "title": "Siemens logfile path parameter answer",
        "description": (
            "Use only when the caller explicitly declares one supported "
            "alarm source scope."
        ),
        "required_payload_fields": [
            "alarm_scope",
        ],
        "optional_payload_fields": [
            "requested_information",
            "prepared_filename",
        ],
        "alarm_scope_values": [
            "61352_or_61353",
            "61352",
            "61353",
            "61358",
            "61352_or_61353_or_61358",
        ],
        "requested_information_values": [
            "logfile_path_parameter",
        ],
        "limitations": [
            "Alarm scope must be explicitly declared.",
            "Alarm scope is never inferred from error_code or symptom text.",
            "An answer is returned only when every section in the declared scope supports it.",
            "Automatic execution is never approved.",
        ],
    },
}


def get_troubleshooting_input_guidance(mode=None):
    """Return deterministic guidance without modifying shared definitions."""

    if mode is None:
        return {
            "status": "structured_input_guidance",
            "supported_modes": list(SUPPORTED_MODES),
            "modes": deepcopy(SUPPORTED_MODES),
            "diagnosis_confirmed": False,
            "approved_for_automatic_execution": False,
        }

    if mode not in SUPPORTED_MODES:
        raise ValueError(
            "Unsupported guidance mode."
        )

    return {
        "status": "structured_input_guidance",
        "mode": mode,
        "guidance": deepcopy(
            SUPPORTED_MODES[mode]
        ),
        "diagnosis_confirmed": False,
        "approved_for_automatic_execution": False,
    }


@router.get(
    "/development/troubleshoot/guidance",
    tags=["Development"],
    summary="Describe supported structured troubleshooting inputs",
    description=(
        "Returns machine-readable input requirements for the "
        "development troubleshooting policies. No diagnosis or "
        "free-text inference is performed."
    ),
)
def troubleshooting_input_guidance(
    mode: GuidanceMode | None = None,
):
    return get_troubleshooting_input_guidance(
        mode
    )
