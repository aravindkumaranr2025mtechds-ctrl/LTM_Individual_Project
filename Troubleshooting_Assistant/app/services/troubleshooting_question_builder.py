"""Human-friendly question specifications for supported troubleshooting modes.

The questions are derived only from the explicit structured-input contract.
They do not infer answers from free text and do not confirm a diagnosis.
"""

from copy import deepcopy

from app.services.troubleshooting_input_guidance import (
    SUPPORTED_MODES,
)


QUESTION_FORMS = {
    "abb_stall": {
        "title": "ABB Motor stalls information",
        "intro": (
            "Choose what information you want and explicitly report "
            "the available observations."
        ),
        "fields": [
            {
                "field_id": "requested_information",
                "label": "What do you want the assistant to do?",
                "input_type": "single_choice",
                "required": True,
                "choices": [
                    {
                        "value": "list_possible_causes",
                        "label": "List possible causes from the indexed ABB source",
                    },
                    {
                        "value": "review_reports",
                        "label": "Review my explicit condition reports",
                    },
                    {
                        "value": "identify_cause",
                        "label": "Check whether the evidence identifies one cause",
                    },
                ],
            },
            {
                "field_id": "open_phase_reported",
                "label": "Has an open phase been explicitly reported?",
                "input_type": "tri_state",
                "required": False,
            },
            {
                "field_id": "wrong_application_reported",
                "label": "Has a wrong application or sizing issue been explicitly reported?",
                "input_type": "tri_state",
                "required": False,
            },
            {
                "field_id": "overload_reported",
                "label": "Has overload been explicitly reported?",
                "input_type": "tri_state",
                "required": False,
            },
            {
                "field_id": "low_voltage_reported",
                "label": "Has low voltage been explicitly reported?",
                "input_type": "tri_state",
                "required": False,
            },
            {
                "field_id": "open_circuit_reported",
                "label": "Has an open circuit been explicitly reported?",
                "input_type": "tri_state",
                "required": False,
            },
        ],
    },

    "siemens_licensing": {
        "title": "Siemens licensing information",
        "intro": (
            "Provide only facts that are explicitly known or reported."
        ),
        "fields": [
            {
                "field_id": "reported_alarm_number",
                "label": "Was alarm 8080 or 8081 explicitly reported?",
                "input_type": "single_choice",
                "required": False,
                "choices": [
                    {"value": "8080", "label": "8080"},
                    {"value": "8081", "label": "8081"},
                    {"value": None, "label": "Not explicitly known"},
                ],
            },
            {
                "field_id": "options_activated",
                "label": "Are one or more options activated?",
                "input_type": "tri_state",
                "required": False,
            },
            {
                "field_id": "license_key_set",
                "label": "Is a license key set?",
                "input_type": "tri_state",
                "required": False,
            },
            {
                "field_id": "entered_key_covers_activated_options",
                "label": "Does the entered key cover the activated options?",
                "input_type": "tri_state",
                "required": False,
            },
        ],
    },

    "siemens_logfile": {
        "title": "Siemens logfile source scope",
        "intro": (
            "Select the alarm scope explicitly. "
            "The scope is never inferred from free text."
        ),
        "fields": [
            {
                "field_id": "alarm_scope",
                "label": "Which alarm source scope should be checked?",
                "input_type": "single_choice",
                "required": True,
                "choices": [
                    {
                        "value": "61352_or_61353",
                        "label": "61352 or 61353",
                    },
                    {
                        "value": "61352",
                        "label": "61352 only",
                    },
                    {
                        "value": "61353",
                        "label": "61353 only",
                    },
                    {
                        "value": "61358",
                        "label": "61358 only",
                    },
                    {
                        "value": "61352_or_61353_or_61358",
                        "label": "61352, 61353, or 61358",
                    },
                ],
            }
        ],
    },
}


def get_question_form(mode):
    """Return a copy of the human-friendly form for one explicit mode."""

    if mode not in SUPPORTED_MODES:
        raise ValueError(
            "Unsupported troubleshooting question mode."
        )

    if mode not in QUESTION_FORMS:
        raise ValueError(
            "Question form is not defined for this supported mode."
        )

    return {
        "status": "question_form",
        "mode": mode,
        "form": deepcopy(
            QUESTION_FORMS[mode]
        ),
        "diagnosis_confirmed": False,
        "approved_for_automatic_execution": False,
    }


def get_all_question_forms():
    """Return all question forms without aliasing shared definitions."""

    return {
        "status": "question_forms",
        "supported_modes": list(
            SUPPORTED_MODES
        ),
        "forms": deepcopy(
            QUESTION_FORMS
        ),
        "diagnosis_confirmed": False,
        "approved_for_automatic_execution": False,
    }


from typing import Literal
from fastapi import APIRouter


router = APIRouter()


QuestionMode = Literal[
    "abb_stall",
    "siemens_licensing",
    "siemens_logfile",
]


@router.get(
    "/development/troubleshoot/questions",
    tags=["Development"],
    summary="Return human-friendly troubleshooting questions",
    description=(
        "Returns deterministic question specifications for one explicit "
        "supported troubleshooting mode. No free-text inference is performed."
    ),
)
def troubleshooting_questions(
    mode: QuestionMode,
):
    return get_question_form(
        mode
    )
