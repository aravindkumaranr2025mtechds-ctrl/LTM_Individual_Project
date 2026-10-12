"""Bounded development example: a shared parameter answer across source sections."""
import hashlib
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from app.services.evidence_index import _decode, _input_path

DOC = '212022f0a2614a7b839cc827522c6651_MC_diagnostics_man_0724_en-US'
PREPARED = DOC + '_chunks_ready.json'
DIRECTORY = Path(__file__).resolve().parents[2] / 'data' / 'embedding_documents'
PARAMETER = '_PROTNAME[0]'
QUOTE = 'Check parameter _PROTNAME[0].'
SOURCE = {
    '61352': ('s01929', [610, 611],
              '9ac3ad6c096465de4e06ca38a28672369cfb3b2e276557d13000051200377a66', True),
    '61353': ('s01930', [611],
              'a6fb912cef7d5d549ef5287bb76903cd78bc77986cbc170361fce0ed944c56f6', True),
    '61358': ('s01935', [612],
              '34b918b71639fcf10ab04d78862298d5b7fb0b2c4c10abbb982905d8ca1a9e2d', False),
}
SCOPES = {
    '61352_or_61353': ('61352', '61353'),
    '61352': ('61352',),
    '61353': ('61353',),
    '61358': ('61358',),
    '61352_or_61353_or_61358': ('61352', '61353', '61358'),
}


class LogfileAnswerRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Required: this source scope must never be inferred from a vague description.
    alarm_scope: Literal[
        '61352_or_61353', '61352', '61353', '61358',
        '61352_or_61353_or_61358'
    ]
    requested_information: Literal['logfile_path_parameter'] = 'logfile_path_parameter'
    prepared_filename: str = Field(default=PREPARED, strict=True, min_length=6, max_length=255)


def load_sections(filename, alarms):
    path = _input_path(DIRECTORY, filename)
    raw = path.read_bytes()
    document = _decode(raw)
    if document.get('document_id') != DOC or document.get('source_filename') != DOC + '.pdf':
        raise ValueError('Expected the configured Siemens diagnostics source.')
    parents = document.get('parents')
    if not isinstance(parents, list):
        raise ValueError('Prepared source has no parent sections.')
    sections = []
    for alarm in alarms:
        suffix, pages, expected_hash, has_answer = SOURCE[alarm]
        matches = [p for p in parents if isinstance(p, dict) and p.get('alarm_number') == alarm]
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one source section for alarm {alarm}.')
        parent = matches[0]
        text = parent.get('text')
        if (not isinstance(text, str)
                or hashlib.sha256(text.encode('utf-8')).hexdigest() != expected_hash
                or parent.get('document_id') != DOC
                or parent.get('source_filename') != DOC + '.pdf'
                or parent.get('parent_id') != DOC + '_' + suffix
                or parent.get('page_numbers') != pages):
            raise ValueError(f'Section {alarm} differs from the inspected development source; review required.')
        evidence = None
        if has_answer:
            if text.count(QUOTE) != 1:
                raise ValueError(f'Parameter quote is missing or ambiguous in section {alarm}.')
            start = text.index(QUOTE)
            evidence = {
                'evidence_id': parent['parent_id'] + ':logfile_path_parameter',
                'quote': QUOTE, 'start': start, 'end': start + len(QUOTE),
                'page_numbers': list(pages), 'page_scope': 'parent_section',
            }
        elif PARAMETER in text:
            raise ValueError('The inspected negative example has changed; review required.')
        sections.append({
            'alarm_number': alarm, 'parent_id': parent['parent_id'],
            'parent_text_sha256': expected_hash, 'section_page_numbers': list(pages),
            'parameter_name': PARAMETER if has_answer else None,
            'answer_evidence': evidence,
        })
    if path.read_bytes() != raw:
        raise ValueError('Prepared source changed during validation.')
    return sections, hashlib.sha256(raw).hexdigest()


def answer_logfile_parameter(request):
    alarms = SCOPES[request.alarm_scope]
    sections, fingerprint = load_sections(request.prepared_filename, alarms)
    missing = [s['alarm_number'] for s in sections if s['answer_evidence'] is None]
    answers = {s['parameter_name'] for s in sections if s['answer_evidence'] is not None}
    supported = not missing and len(answers) == 1
    return {
        'mode': 'siemens_logfile_parameter_development',
        'status': 'answer_supported' if supported else 'insufficient_evidence',
        'requested_information': request.requested_information,
        'declared_alarm_scope': request.alarm_scope,
        'considered_alarm_numbers': list(alarms),
        'answer': next(iter(answers)) if supported else None,
        'answer_agreement': 'established' if supported else 'not_established',
        'sections_without_answer_evidence': missing,
        'source_sections': sections,
        'selected_alarm_number': None,
        'alarm_identification': 'not_performed',
        'question': None,
        'document_id': DOC, 'source_filename': DOC + '.pdf',
        'prepared_filename': request.prepared_filename, 'prepared_sha256': fingerprint,
        'source_validation': 'matched_inspected_parent_text_hashes',
        'annotation_status': 'development_not_independently_reviewed',
        'scope': 'Parameter name in the explicitly declared source sections only; machine applicability and completeness of that scope are not established.',
        'diagnosis_confirmed': False, 'approved_for_automatic_execution': False,
        'message': (
            'Every section in this scope explicitly names the same parameter. No alarm selection is needed for this source-information answer.'
            if supported else
            'Not every section in this scope supports the parameter answer. Missing evidence is not agreement; no answer or alternate alarm is inferred.'
        ),
    }


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post('/development/siemens/logfile/answer', tags=['Development'])
def logfile_answer(request: LogfileAnswerRequest):
    try:
        return answer_logfile_parameter(request)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail='Prepared Siemens source was not found.') from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception('Logfile parameter comparison failed.')
        raise HTTPException(status_code=500, detail='Source comparison failed; check the backend terminal.') from error
