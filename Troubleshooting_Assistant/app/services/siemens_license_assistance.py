"""Source-bound development comparison of Siemens 8080 and 8081 only.

No diagnosis, repair execution, semantic fallback, or exhaustive licensing scope.
Question budget is caller-carried; no server-side conversation state is stored.
"""
import hashlib
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.services.condition_checker import evaluate_condition
from app.services.evidence_index import _decode, _input_path

DOC = '212022f0a2614a7b839cc827522c6651_MC_diagnostics_man_0724_en-US'
PREPARED = DOC + '_chunks_ready.json'
DIRECTORY = Path(__file__).resolve().parents[2] / 'data' / 'embedding_documents'
SOURCE = {
    '8080': (
        '0fb5886f44915435ec86ca344abefdb538e1dd3821e147547ae007c9134350ae',
        'One or more options were activated but no license key was set to prove the purchase of the option(s).',
    ),
    '8081': (
        'a538abe532071c0ef4cb20dff5e76937eb1970e143edea020296802c9dac4704',
        'One ore more options were activated, that are not licensed by the license key entered.',
    ),
}
QUESTIONS = {
    'options_activated': 'Were one or more options activated?',
    'license_key_set': 'Has a license key been set or entered?',
    'entered_key_covers_activated_options': 'Does the entered key license all activated options?',
}


def fact(name, expected=True):
    return {'fact': name, 'expected': expected}


CONDITIONS = {
    '8080': {'all': [fact('options_activated'), fact('license_key_set', False)]},
    '8081': {'all': [fact('options_activated'), fact('license_key_set'),
                     fact('entered_key_covers_activated_options', False)]},
}


class LicenseReports(BaseModel):
    model_config = ConfigDict(extra='forbid')
    options_activated: list[StrictBool | None] = Field(default_factory=list, max_length=32)
    license_key_set: list[StrictBool | None] = Field(default_factory=list, max_length=32)
    entered_key_covers_activated_options: list[StrictBool | None] = Field(default_factory=list, max_length=32)


class LicenseRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prepared_filename: str = Field(default=PREPARED, strict=True, min_length=6, max_length=255)
    observations: LicenseReports = Field(default_factory=LicenseReports)
    reported_alarm_number: Literal['8080', '8081'] | None = None
    clarifications_used: int = Field(default=0, strict=True, ge=0, le=2)
    deferred_fact_ids: list[Literal[
        'options_activated', 'license_key_set', 'entered_key_covers_activated_options'
    ]] = Field(default_factory=list, max_length=3)


def load_evidence(filename):
    path = _input_path(DIRECTORY, filename)
    raw = path.read_bytes()
    document = _decode(raw)
    if document.get('document_id') != DOC or document.get('source_filename') != DOC + '.pdf':
        raise ValueError('Expected the configured Siemens diagnostics source.')
    parents = document.get('parents')
    if not isinstance(parents, list):
        raise ValueError('Prepared source has no parent sections.')
    evidence = {}
    for alarm, (expected_hash, quote) in SOURCE.items():
        matches = [p for p in parents if isinstance(p, dict) and p.get('alarm_number') == alarm]
        if len(matches) != 1:
            raise ValueError('Expected one source section for each of 8080 and 8081.')
        parent = matches[0]
        text = parent.get('text')
        if (not isinstance(text, str)
                or hashlib.sha256(text.encode('utf-8')).hexdigest() != expected_hash
                or parent.get('document_id') != DOC
                or parent.get('source_filename') != DOC + '.pdf'
                or parent.get('page_numbers') != [114]
                or not isinstance(parent.get('parent_id'), str)
                or not parent['parent_id'].startswith(DOC + '_')):
            raise ValueError('Licensing section differs from the inspected development source; review required.')
        if text.count(quote) != 1:
            raise ValueError('Explanation quote is missing or ambiguous.')
        start = text.index(quote)
        evidence[alarm] = {
            'parent_id': parent['parent_id'], 'alarm_number': alarm,
            'quote': quote, 'start': start, 'end': start + len(quote),
            'page_numbers': [114], 'page_scope': 'parent_section',
            'parent_text_sha256': expected_hash,
        }
    if path.read_bytes() != raw:
        raise ValueError('Prepared source changed during validation.')
    return evidence, hashlib.sha256(raw).hexdigest()


def compare_license_conditions(request):
    if len(request.deferred_fact_ids) != len(set(request.deferred_fact_ids)):
        raise ValueError('Deferred fact IDs must be unique.')
    observations = request.observations.model_dump()
    evidence, fingerprint = load_evidence(request.prepared_filename)
    evaluations = {alarm: evaluate_condition(condition, observations)
                   for alarm, condition in CONDITIONS.items()}
    states = {name: evaluate_condition(fact(name), observations) for name in QUESTIONS}
    conflicts = [name for name, result in states.items() if result['conflicting_fact_ids']]
    inconsistent_coverage = (
        states['license_key_set']['status'] == 'contradicted'
        and states['entered_key_covers_activated_options']['status'] != 'unknown'
    )
    selected, question = None, None
    considered = [request.reported_alarm_number] if request.reported_alarm_number else list(SOURCE)
    supported = [a for a in considered if evaluations[a]['status'] == 'supported']
    unknown = [a for a in considered if evaluations[a]['status'] == 'unknown']
    if conflicts or inconsistent_coverage:
        status = 'conflicting_input'
    elif request.reported_alarm_number and evaluations[request.reported_alarm_number]['status'] == 'contradicted':
        status = 'conflicting_input'
    elif len(supported) == 1:
        status, selected = 'description_supported', supported[0]
    else:
        status = 'insufficient_evidence'
        missing = {f for a in unknown for f in evaluations[a]['missing_fact_ids']}
        next_fact = next((f for f in QUESTIONS if f in missing and f not in request.deferred_fact_ids), None)
        if next_fact and request.clarifications_used < 2:
            status = 'needs_clarification'
            question = {
                'fact_id': next_fact, 'text': QUESTIONS[next_fact],
                'source_alarms': unknown,
                'next_clarifications_used': request.clarifications_used + 1,
                'options': ['reported_true', 'reported_false', 'unknown'],
            }
    return {
        'mode': 'siemens_8080_8081_development_comparison',
        'status': status, 'reported_alarm_number': request.reported_alarm_number,
        'selected_description_alarm': selected,
        'candidates': [{'alarm_number': a, 'evaluation': evaluations[a], 'evidence': evidence[a]}
                       for a in SOURCE],
        'question': question, 'conflicting_fact_ids': conflicts,
        'inconsistent_key_coverage_report': inconsistent_coverage,
        'clarifications_used': request.clarifications_used, 'clarification_budget': 2,
        'deferred_fact_ids': list(request.deferred_fact_ids),
        'prepared_filename': request.prepared_filename, 'prepared_sha256': fingerprint,
        'source_validation': 'matched_inspected_parent_text_hashes',
        'annotation_status': 'development_not_independently_reviewed',
        'scope': 'Comparison of 8080 and 8081 descriptions only; other licensing alarms are outside this policy.',
        'diagnosis_confirmed': False, 'approved_for_automatic_execution': False,
        'message': 'Description support is relative to supplied reports and this bounded development mapping.',
    }


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/development/siemens/licensing/compare', tags=['Development'])
def compare_licensing(request: LicenseRequest):
    try:
        return compare_license_conditions(request)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail='Prepared Siemens source was not found.') from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception('Licensing comparison failed.')
        raise HTTPException(status_code=500, detail='Comparison failed; check the backend terminal.') from error
