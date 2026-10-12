"""Stateless multi-turn troubleshooting workflow.

Each request carries the complete explicit state needed for that turn.
No server-side session, free-text fact inference, diagnosis, or automatic
execution is introduced here.
"""

from copy import deepcopy
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.services.development_troubleshooting_orchestrator import (
    DevelopmentTroubleshootingRequest,
    orchestrate_development_troubleshooting,
)
from app.services.troubleshooting_answer_builder import (
    build_structured_assistance,
)


router = APIRouter()


class TroubleshootingTurnRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    machine_name: str
    error_code: str | None = None
    symptom: str
    operating_condition: str | None = None
    previous_attempts: str | None = None

    mode: Literal[
        "abb_stall",
        "siemens_licensing",
        "siemens_logfile",
    ]

    answers: dict = Field(
        default_factory=dict
    )


def _context(request):
    return {
        "machine_name":
            request.machine_name,
        "error_code":
            request.error_code,
        "symptom":
            request.symptom,
        "operating_condition":
            request.operating_condition,
        "previous_attempts":
            request.previous_attempts,
    }


def _continuation(mode, answers, result):
    """Return explicit caller-carried state for the next turn."""

    state = deepcopy(
        answers
    )

    if mode == "abb_stall":
        clarification = result.get(
            "clarification"
        )

        if clarification is not None:
            state[
                "deferred_fact_ids"
            ] = deepcopy(
                clarification.get(
                    "deferred_fact_ids",
                    state.get(
                        "deferred_fact_ids",
                        [],
                    ),
                )
            )

    elif mode == "siemens_licensing":
        state[
            "clarifications_used"
        ] = result.get(
            "clarifications_used",
            state.get(
                "clarifications_used",
                0,
            ),
        )

        state[
            "deferred_fact_ids"
        ] = deepcopy(
            result.get(
                "deferred_fact_ids",
                state.get(
                    "deferred_fact_ids",
                    [],
                ),
            )
        )

        if (
            result.get(
                "reported_alarm_number"
            )
            is not None
        ):
            state[
                "reported_alarm_number"
            ] = result[
                "reported_alarm_number"
            ]

    return state


def _next_question(mode, result):
    if mode == "abb_stall":
        clarification = result.get(
            "clarification"
        )

        if clarification is None:
            return None

        return clarification.get(
            "question"
        )

    if mode == "siemens_licensing":
        return result.get(
            "question"
        )

    return None


def run_troubleshooting_turn(request):
    """Run one explicit turn through existing validated assistance code."""

    structured = build_structured_assistance(
        request.mode,
        request.answers,
    )

    validated = TypeAdapter(
        DevelopmentTroubleshootingRequest
    ).validate_python(
        structured
    )

    assistance = (
        orchestrate_development_troubleshooting(
            validated
        )
    )

    result = assistance[
        "result"
    ]

    question = _next_question(
        request.mode,
        result,
    )

    if question is not None:
        workflow_status = (
            "needs_clarification"
        )
    else:
        workflow_status = (
            "turn_complete"
        )

    continuation = _continuation(
        request.mode,
        request.answers,
        result,
    )

    return {
        "status":
            workflow_status,
        "mode":
            request.mode,
        "context":
            _context(request),
        "next_question":
            question,
        "continuation_answers":
            continuation,
        "assistance":
            assistance,
        "diagnosis_confirmed":
            False,
        "approved_for_automatic_execution":
            False,
        "server_session_created":
            False,
        "message": (
            "Carry continuation_answers into the next request and add "
            "the user's explicit answer to next_question."
            if question is not None
            else
            "This turn produced no further clarification question."
        ),
    }


@router.post(
    "/development/troubleshoot/turn",
    tags=["Development"],
    summary="Run one stateless troubleshooting clarification turn",
    description=(
        "Builds and executes one explicit structured turn. "
        "Any next-question state is returned to the caller; "
        "the server does not create a troubleshooting session."
    ),
)
def troubleshooting_turn(
    request: TroubleshootingTurnRequest,
):
    try:
        return run_troubleshooting_turn(
            request
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=(
                "Required prepared evidence source was not found."
            ),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Troubleshooting turn failed. "
                "Check the backend terminal for details."
            ),
        ) from error
