"""Answer-scoped development policy for the five ABB Motor stalls records.

The audit covers indexed rows r010-r014 and their existing context links.
It establishes no reviewed measurement discriminator or unique-cause rule.
Existing report labels remain separate from diagnosis and source retrieval.
"""
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from app.services.abb_stall_clarification_api import StallClarificationRequest
from app.services.abb_stall_conditions import check_abb_stall_conditions
from app.services.abb_stall_clarification import clarify_abb_stall_conditions

router = APIRouter()
logger = logging.getLogger(__name__)

# Draft limitations of the indexed rows, not claims about all ABB documents.
GAPS = {
    'open_phase_reported': 'The row names a check; it gives no unique-cause decision rule.',
    'wrong_application_reported': 'The row refers to type/size and supplier consultation; no sizing rule is encoded.',
    'overload_reported': 'The row gives load-reduction guidance; no numeric overload criterion is encoded.',
    'low_voltage_reported': 'The row refers to rating-plate voltage; no scoped measurement classifier is encoded.',
    'open_circuit_reported': 'The row lists components to check; it gives no exclusive discriminator among these causes.',
}


class StallAssistanceRequest(StallClarificationRequest):
    requested_information: Literal[
        'list_possible_causes', 'review_reports', 'identify_cause'
    ]


def assist_abb_stall(index_filename, observations, requested_information, deferred_fact_ids=None):
    """Select output by task without promoting report support into diagnosis."""
    # Reuse strict API validation for direct Python callers too.
    request = StallAssistanceRequest(
        index_filename=index_filename, observations=observations,
        requested_information=requested_information,
        deferred_fact_ids=[] if deferred_fact_ids is None else deferred_fact_ids,
    )
    reports = request.observations.model_dump()
    deferred = request.deferred_fact_ids
    if len(deferred) != len(set(deferred)) or any(f not in GAPS for f in deferred):
        raise ValueError('Deferred IDs must be unique supported fact IDs.')

    if requested_information == 'review_reports':
        result = clarify_abb_stall_conditions(index_filename, reports, deferred)
        clarification = result['clarification']
        status = clarification['status']
        report_assessment = result['results']
        message = 'Review of explicit reports only; a complete report is not a diagnosis.'
    else:
        result = check_abb_stall_conditions(index_filename, reports)
        clarification = None
        report_assessment = None
        if requested_information == 'list_possible_causes':
            status = 'source_information'
            message = 'These are the five possible causes listed for Motor stalls in the indexed ABB table.'
        else:
            status = 'insufficient_evidence'
            message = (
                'The indexed source and unreviewed report mappings do not establish '
                'a unique cause. No diagnosis or distinguishing measurement is inferred.'
            )

    source_records = [{
        'record_id': item['record_id'], 'possible_cause': item['possible_cause'],
        'evidence': item['evidence'], 'page_numbers': item['page_numbers'],
        'context_ids': item['context_ids'],
        'mapping_limit': GAPS[item['fact_id']],
    } for item in result['results']]
    return {
        'mode': 'abb_stall_answer_scoped_development',
        'requested_information': requested_information, 'status': status,
        'symptom': 'Motor stalls', 'symptom_id': result['symptom_id'],
        'source_validation': result['source_validation'],
        'source_scope': 'Indexed ABB Motor stalls rows r010-r014 and linked context passages.',
        'mapping_status': 'development_not_reviewed',
        'discriminator_status': 'not_established_for_unique_cause_selection',
        'source_records': source_records, 'source_record_count': len(source_records),
        'report_assessment': report_assessment, 'clarification': clarification,
        'observations_used_for_report_assessment': requested_information == 'review_reports',
        'diagnosis_confirmed': False, 'approved_for_automatic_execution': False,
        'message': message,
    }


@router.post(
    '/development/abb/stall/assist', tags=['Development'],
    summary='Answer an ABB Motor stalls request according to its information scope',
    description='Source listing, report review, or an explicit insufficient-evidence result for diagnosis. Development only.',
)
def assist_stall(request: StallAssistanceRequest):
    try:
        return assist_abb_stall(
            index_filename=request.index_filename,
            observations=request.observations.model_dump(),
            requested_information=request.requested_information,
            deferred_fact_ids=request.deferred_fact_ids,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail='Evidence index or prepared source was not found.') from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception('ABB scoped assistance failed.')
        raise HTTPException(status_code=500, detail='Assistance failed. Check the backend terminal for details.') from error
