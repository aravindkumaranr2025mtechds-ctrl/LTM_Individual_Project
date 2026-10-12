"""Stateless development clarification endpoint for ABB Motor stalls."""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import Field, StrictStr

from app.services.abb_stall_api import StallConditionRequest
from app.services.abb_stall_clarification import clarify_abb_stall_conditions

router = APIRouter()
logger = logging.getLogger(__name__)


class StallClarificationRequest(StallConditionRequest):
    deferred_fact_ids: list[StrictStr] = Field(default_factory=list, max_length=5)


@router.post(
    '/development/abb/conditions/stall/clarify',
    tags=['Development'],
    summary='Ask one source-linked Motor stalls clarification question',
    description=(
        'Fixed-order development baseline: conflicts first, then missing reports. '
        'Send the current observations and deferred fact IDs on every request. '
        'Deferral leaves a condition unknown. No stored conversation, diagnosis, '
        'measurement interpretation, or repair approval.'
    ),
)
def clarify_stall_conditions(request: StallClarificationRequest):
    try:
        return clarify_abb_stall_conditions(
            index_filename=request.index_filename,
            observations=request.observations.model_dump(),
            deferred_fact_ids=request.deferred_fact_ids,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404, detail='Evidence index or prepared source was not found.'
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception('ABB stall clarification failed.')
        raise HTTPException(
            status_code=500,
            detail='Clarification failed. Check the backend terminal for details.'
        ) from error
