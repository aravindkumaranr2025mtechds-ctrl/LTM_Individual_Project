"""Constructed development scenarios, not held-out or diagnostic evaluation.

Run from the project root: python -m evaluation.evaluate_abb_clarification
Uses the real local ABB files through FastAPI TestClient; no running server.
Expected outcomes are explicit test judgements for the fixed-order baseline.
"""
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient
from app.main import app

PREFIX = 'dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022'
INDEX = PREFIX + '_structured_v1_ready_evidence_v1.json'
URL = '/development/abb/conditions/stall/clarify'
FACTS = ['open_phase_reported', 'wrong_application_reported', 'overload_reported',
         'low_voltage_reported', 'open_circuit_reported']
CAUSES = ['One phase may be open', 'Wrong application', 'Overload', 'Low voltage', 'Open circuit']
P, W, O, L, C = FACTS

# name, input reports, deferred IDs, expected workflow status,
# expected question fact (None means no question), non-unknown expected states.
SCENARIOS = [
    ('D01_missing_all', {}, [], 'needs_clarification', P, {}),
    ('D02_voltage_present', {L: [True]}, [], 'needs_clarification', P, {L: 'supported'}),
    ('D03_overload_absent', {O: [False]}, [], 'needs_clarification', P, {O: 'contradicted'}),
    ('D04_two_present', {O: [True], L: [True]}, [], 'needs_clarification', P,
     {O: 'supported', L: 'supported'}),
    ('D05_voltage_conflict', {L: [True, False]}, [], 'needs_clarification', L, {}),
    ('D06_two_conflicts', {P: [True, False], L: [False, True]}, [], 'needs_clarification', P, {}),
    ('D07_defer_phase', {}, [P], 'needs_clarification', W, {}),
    ('D08_defer_conflict', {L: [True, False]}, [L], 'needs_clarification', P, {}),
    ('D09_defer_all', {}, FACTS, 'insufficient_information', None, {}),
    ('D10_all_present', {f: [True] for f in FACTS}, [], 'reports_complete', None,
     {f: 'supported' for f in FACTS}),
    ('D11_all_absent', {f: [False] for f in FACTS}, [], 'reports_complete', None,
     {f: 'contradicted' for f in FACTS}),
    ('D12_mixed_complete', {P: [False], W: [False], O: [True], L: [True], C: [False]}, [],
     'reports_complete', None,
     {P: 'contradicted', W: 'contradicted', O: 'supported', L: 'supported', C: 'contradicted'}),
]

# One scripted dialogue; each row carries the full current session state.
# The runner does not infer that the server remembers earlier requests.
DIALOGUE = [
    ('T01_start', {}, [], 'needs_clarification', P, {}),
    ('T02_phase_deferred', {}, [P], 'needs_clarification', W, {}),
    ('T03_application_absent', {W: [False]}, [P], 'needs_clarification', O, {W: 'contradicted'}),
    ('T04_overload_present', {W: [False], O: [True]}, [P], 'needs_clarification', L,
     {W: 'contradicted', O: 'supported'}),
    ('T05_voltage_present', {W: [False], O: [True], L: [True]}, [P], 'needs_clarification', C,
     {W: 'contradicted', O: 'supported', L: 'supported'}),
    ('T06_circuit_deferred', {W: [False], O: [True], L: [True]}, [P, C],
     'insufficient_information', None, {W: 'contradicted', O: 'supported', L: 'supported'}),
]


def run_case(client, case, group):
    name, observations, deferred, status, question_fact, known = case
    expected_states = {f: known.get(f, 'unknown') for f in FACTS}
    payload = {'index_filename': INDEX, 'observations': observations, 'deferred_fact_ids': deferred}
    expected = {'status': status, 'question_fact': question_fact, 'condition_states': expected_states}
    errors = []
    body, http_status = None, None
    started = perf_counter()
    try:
        response = client.post(URL, json=payload)
        http_status = response.status_code
        body = response.json()
        if http_status != 200:
            errors.append(f'Expected HTTP 200; got {http_status}')
        else:
            clarification = body['clarification']
            question = clarification['question']
            checks = {
                'workflow_status': clarification['status'] == status,
                'question_fact': (question['fact_id'] if question else None) == question_fact,
                'condition_states': {r['fact_id']: r['status'] for r in body['results']} == expected_states,
                'five_records': body['results_count'] == len(body['results']) == 5,
                'unreviewed': body['mapping_status'] == 'development_not_reviewed',
                'no_diagnosis': body['diagnosis_confirmed'] is False,
                'no_action_approval': body['approved_for_automatic_execution'] is False,
                'deferrals_preserved': clarification['deferred_fact_ids'] == deferred,
                'unresolved_preserved': clarification['unresolved_fact_ids'] ==
                    [f for f in FACTS if expected_states[f] == 'unknown'],
            }
            for number, (fact, cause) in enumerate(zip(FACTS, CAUSES), 10):
                rows = [r for r in body['results'] if r['fact_id'] == fact]
                record_id = PREFIX + f'_r{number:03d}'
                checks['source_' + fact] = len(rows) == 1 and (
                    rows[0]['record_id'] == record_id
                    and rows[0]['possible_cause'] == cause
                    and rows[0]['evidence']['quote'] == cause
                    and rows[0]['evidence']['evidence_id'] == record_id + ':possible_cause'
                    and rows[0]['page_numbers'] == [25]
                    and len(rows[0]['context_ids']) == 4
                )
            if question:
                record = PREFIX + f'_r{10 + FACTS.index(question_fact):03d}'
                checks['question_source'] = question['evidence_id'] == record + ':possible_cause'
                reports = observations.get(question_fact, [])
                reason = 'conflicting_reports' if True in reports and False in reports else 'missing_report'
                checks['question_reason'] = question['reason'] == reason
            errors.extend(name for name, passed in checks.items() if not passed)
    except Exception as error:
        errors.append(f'{type(error).__name__}: {error}')
    return {
        'scenario_id': name, 'group': group, 'input': payload, 'expected': expected,
        'http_status': http_status, 'passed': not errors, 'errors': errors,
        'elapsed_ms': round((perf_counter() - started) * 1000, 3), 'response': body,
    }


def main():
    with TestClient(app, raise_server_exceptions=False) as client:
        records = [run_case(client, case, 'static') for case in SCENARIOS]
        records += [run_case(client, case, 'scripted_dialogue') for case in DIALOGUE]
    for record in records:
        print(('PASS ' if record['passed'] else 'FAIL ') + record['scenario_id'])
        if record['errors']:
            print('  ' + '; '.join(record['errors']))
    static_passed = sum(r['passed'] for r in records if r['group'] == 'static')
    turns_passed = sum(r['passed'] for r in records if r['group'] == 'scripted_dialogue')
    report = {
        'evaluation_version': 'abb_fixed_order_development_v1',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'python_version': platform.python_version(),
        'scope': 'One symptom group; five unreviewed mappings; structured reports only.',
        'limitations': [
            'Constructed development cases, not held-out tests or field incidents.',
            'Expected outcomes were authored alongside the implementation.',
            'No diagnostic accuracy, superiority, or optimal question-count claim.',
            'Elapsed times include in-process API and source validation; not deployment benchmarks.',
            'The dialogue turns are related steps of one scenario, not independent cases.',
        ],
        'static_scenarios': {'passed': static_passed, 'total': len(SCENARIOS)},
        'scripted_dialogue': {'turns_passed': turns_passed, 'turns_total': len(DIALOGUE),
                             'passed': turns_passed == len(DIALOGUE)},
        'records': records,
    }
    directory = Path(__file__).resolve().parents[1] / 'evaluation' / 'reports'
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    destination = directory / f'abb_clarification_development_{stamp}.json'
    with destination.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
    print(f'\nStatic development scenarios: {static_passed}/{len(SCENARIOS)} passed.')
    print(f'Scripted dialogue: {turns_passed}/{len(DIALOGUE)} turns passed.')
    print('Report saved:', destination)
    print('These results measure development behaviour, not diagnostic accuracy.')
    return 0 if all(r['passed'] for r in records) else 1


if __name__ == '__main__':
    sys.exit(main())
