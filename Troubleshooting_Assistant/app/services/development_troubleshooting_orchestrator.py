"""Explicit structured development orchestrator.

This module routes only caller-declared structured assistance requests.
It does not infer manufacturer, alarm scope, observations, or diagnosis
from vague free text.
"""

import logging
from typing import Annotated, Literal, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.abb_stall_assistance import (
    StallAssistanceRequest,
    assist_abb_stall,
)
from app.services.siemens_license_assistance import (
    LicenseRequest,
    compare_license_conditions,
)
from app.services.siemens_logfile_answer import (
    LogfileAnswerRequest,
    answer_logfile_parameter,
)


router = APIRouter()
logger = logging.getLogger(__name__)


class AbbStallOrchestratorRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    mode: Literal['abb_stall']
    payload: StallAssistanceRequest


class SiemensLicensingOrchestratorRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    mode: Literal['siemens_licensing']
    payload: LicenseRequest


class SiemensLogfileOrchestratorRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    mode: Literal['siemens_logfile']
    payload: LogfileAnswerRequest


DevelopmentTroubleshootingRequest = Annotated[
    Union[
        AbbStallOrchestratorRequest,
        SiemensLicensingOrchestratorRequest,
        SiemensLogfileOrchestratorRequest,
    ],
    Field(discriminator='mode'),
]


def orchestrate_development_troubleshooting(request):
    """Route an explicit structured request to one validated policy."""

    if request.mode == 'abb_stall':
        payload = request.payload

        result = assist_abb_stall(
            index_filename=payload.index_filename,
            observations=payload.observations.model_dump(),
            requested_information=payload.requested_information,
            deferred_fact_ids=payload.deferred_fact_ids,
        )

    elif request.mode == 'siemens_licensing':
        result = compare_license_conditions(
            request.payload
        )

    elif request.mode == 'siemens_logfile':
        result = answer_logfile_parameter(
            request.payload
        )

    else:
        raise ValueError(
            'Unsupported explicit assistance mode.'
        )

    if result.get('diagnosis_confirmed') is not False:
        raise ValueError(
            'Selected policy did not preserve the diagnosis safeguard.'
        )

    if result.get('approved_for_automatic_execution') is not False:
        raise ValueError(
            'Selected policy did not preserve the execution safeguard.'
        )

    return {
        'mode': 'explicit_structured_development_orchestrator',
        'selected_policy': request.mode,
        'diagnosis_confirmed': False,
        'approved_for_automatic_execution': False,
        'result': result,
    }


@router.post(
    '/development/troubleshoot',
    tags=['Development'],
    summary='Route an explicit structured troubleshooting assistance request',
    description=(
        'Development-only orchestrator for the validated ABB stall, '
        'Siemens licensing, and Siemens logfile policies. '
        'The mode and structured evidence scope must be supplied explicitly.'
    ),
)
def development_troubleshoot(
    request: DevelopmentTroubleshootingRequest,
):
    try:
        return orchestrate_development_troubleshooting(
            request
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail='Required prepared evidence source was not found.',
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception(
            'Development troubleshooting orchestration failed.'
        )

        raise HTTPException(
            status_code=500,
            detail=(
                'Development troubleshooting orchestration failed. '
                'Check the backend terminal for details.'
            ),
        ) from error
