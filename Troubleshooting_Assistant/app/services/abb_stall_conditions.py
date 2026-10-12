"""Development report mappings for five ABB Motor stalls records.

Reports concern the same machine and interval. This module does not parse
measurements, establish causes, rank repairs, or return manufacturer guidance.
"""
from copy import deepcopy

from app.services.abb_condition_service import DOCUMENT_ID, PREPARED_SHA256
from app.services.condition_checker import evaluate_condition
from app.services.evidence_index import load_abb_evidence_index

MAPPINGS = (
    ('r010', 'One phase may be open', 'open_phase_reported'),
    ('r011', 'Wrong application', 'wrong_application_reported'),
    ('r012', 'Overload', 'overload_reported'),
    ('r013', 'Low voltage', 'low_voltage_reported'),
    ('r014', 'Open circuit', 'open_circuit_reported'),
)


def check_abb_stall_conditions(index_filename, observations):
    """Return five separate report-support results; never one diagnosis.

    Unknown fact IDs and invalid report types raise ValueError. Missing facts
    remain unknown. Opposing reports remain conflicting; no last-write-wins.
    The source is revalidated on every call. Existing JSON is not modified.
    """
    allowed = {item[2] for item in MAPPINGS}
    if not isinstance(observations, dict) or any(k not in allowed for k in observations):
        raise ValueError('Provide only the five supported Motor stalls fact IDs.')
    for reports in observations.values():
        if not isinstance(reports, list) or len(reports) > 32:
            raise ValueError('Each fact needs a list containing at most 32 reports.')

    checks = [
        evaluate_condition({'fact': fact, 'expected': True}, observations)
        for _, _, fact in MAPPINGS
    ]
    index = load_abb_evidence_index(index_filename)
    source = index['source']
    if (source['document_id'] != DOCUMENT_ID
            or source['prepared_sha256'] != PREPARED_SHA256):
        raise ValueError('Source differs from development mappings; review required.')

    symptom_id = DOCUMENT_ID + '_s002'
    entries = [e for e in index['entries'] if e['symptom_id'] == symptom_id]
    expected_ids = {DOCUMENT_ID + '_' + item[0] for item in MAPPINGS}
    if len(entries) != 5 or {e['record_id'] for e in entries} != expected_ids:
        raise ValueError('Motor stalls source record group differs from mappings.')
    by_id = {e['record_id']: e for e in entries}
    results = []
    for (suffix, cause, fact), evaluation in zip(MAPPINGS, checks):
        record_id = DOCUMENT_ID + '_' + suffix
        entry = by_id[record_id]
        spans = {s['field']: s for s in entry['spans']}
        evidence = spans['possible_cause']
        if (spans['symptom']['quote'] != 'Motor stalls'
                or evidence['quote'] != cause
                or evidence['evidence_id'] != record_id + ':possible_cause'):
            raise ValueError('Development mapping differs from source evidence.')
        results.append({
            'record_id': record_id, 'possible_cause': cause,
            'fact_id': fact, 'status': evaluation['status'],
            'evidence': deepcopy(evidence),
            'page_numbers': list(entry['page_numbers']),
            'context_ids': list(entry['context_ids']),
            'evaluation': evaluation,
        })
    return {
        'mode': 'abb_stall_development_conditions',
        'mapping_status': 'development_not_reviewed',
        'source_validation': 'matched_current_prepared_json',
        'symptom_id': symptom_id, 'symptom': 'Motor stalls',
        'results_count': len(results), 'results': results,
        'diagnosis_confirmed': False,
        'approved_for_automatic_execution': False,
        'message': 'Independent report-support checks; no cause selected or remedy approved.',
    }
