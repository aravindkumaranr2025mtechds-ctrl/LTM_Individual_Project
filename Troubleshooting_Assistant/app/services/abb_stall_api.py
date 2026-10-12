"""Development-only HTTP route for five independent Motor stalls checks."""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.services.abb_stall_conditions import check_abb_stall_conditions

router = APIRouter()
logger = logging.getLogger(__name__)


class StallObservations(BaseModel):
    model_config = ConfigDict(extra='forbid')
    open_phase_reported: list[StrictBool | None] = Field(default_factory=list, max_length=32)
    wrong_application_reported: list[StrictBool | None] = Field(default_factory=list, max_length=32)
    overload_reported: list[StrictBool | None] = Field(default_factory=list, max_length=32)
    low_voltage_reported: list[StrictBool | None] = Field(default_factory=list, max_length=32)
    open_circuit_reported: list[StrictBool | None] = Field(default_factory=list, max_length=32)


class StallConditionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    index_filename: str = Field(
        min_length=6, max_length=255, strict=True,
        pattern=r'^[^/\\:\x00-\x1f]+\.[jJ][sS][oO][nN]$',
    )
    observations: StallObservations

    @model_validator(mode='after')
    def validate_filename(self):
        if self.index_filename != self.index_filename.strip():
            raise ValueError('Do not include surrounding whitespace in the filename.')
        return self


@router.post(
    '/development/abb/conditions/stall',
    tags=['Development'],
    summary='Check five unreviewed Motor stalls conditions',
    description=(
        'Independent checks against explicit reports for the same machine and interval. '
        'Missing or conflicting reports remain unknown. Multiple conditions may be '
        'supported. No diagnosis, measurement interpretation, ranking, or remedies.'
    ),
)
def check_stall_conditions(request: StallConditionRequest):
    try:
        return check_abb_stall_conditions(
            index_filename=request.index_filename,
            observations=request.observations.model_dump(),
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404, detail='Evidence index or prepared source was not found.'
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception('ABB stall condition check failed.')
        raise HTTPException(
            status_code=500,
            detail='Condition check failed. Check the backend terminal for details.'
        ) from error
