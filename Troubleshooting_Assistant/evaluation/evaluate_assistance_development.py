"""Fixed development scenarios across three policies; not a held-out benchmark."""
import hashlib
import json
import platform
import sys
from copy import deepcopy
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
ABB = 'dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022'
SIEMENS = '212022f0a2614a7b839cc827522c6651_MC_diagnostics_man_0724_en-US'
INDEX = ABB + '_structured_v1_ready_evidence_v1.json'

FACTS = [
    'open_phase_reported',
    'wrong_application_reported',
    'overload_reported',
    'low_voltage_reported',
    'open_circuit_reported',
]

CAUSES = [
    'One phase may be open',
    'Wrong application',
    'Overload',
    'Low voltage',
    'Open circuit',
]

P, W, O, L, C = FACTS

KEY = 'license_key_set'
COVER = 'entered_key_covers_activated_options'

STATES = {
    'S': 'supported',
    'C': 'contradicted',
    'U': 'unknown',
}

URLS = {
    'abb': '/development/abb/stall/assist',
    'licensing': '/development/siemens/licensing/compare',
    'logfile': '/development/siemens/logfile/answer',
}

SOURCE_FILES = {
    'abb': 'data/embedding_documents/' + ABB + '_structured_v1_ready.json',
    'index': 'data/condition_evidence/' + INDEX,
    'siemens': 'data/embedding_documents/' + SIEMENS + '_chunks_ready.json',
}


def abb_case(
    name,
    task,
    reports,
    status,
    question=None,
    states='UUUUU',
    deferred=(),
):
    review = task == 'review_reports'

    return {
        'id': name,
        'policy': 'abb',
        'input': {
            'index_filename': INDEX,
            'requested_information': task,
            'observations': reports,
            'deferred_fact_ids': list(deferred),
        },
        'expected': {
            'status': status,
            'question_fact': question,
            'source_causes': CAUSES,
            'states': (
                dict(zip(FACTS, map(STATES.__getitem__, states)))
                if review
                else None
            ),
            'deferred': list(deferred) if review else None,
        },
    }


def license_case(
    name,
    reports,
    status,
    selected=None,
    question=None,
    states='UU',
    used=0,
    deferred=(),
    reported=None,
):
    return {
        'id': name,
        'policy': 'licensing',
        'input': {
            'observations': reports,
            'reported_alarm_number': reported,
            'clarifications_used': used,
            'deferred_fact_ids': list(deferred),
        },
        'expected': {
            'status': status,
            'selected': selected,
            'question_fact': question,
            'states': dict(
                zip(
                    ('8080', '8081'),
                    map(STATES.__getitem__, states),
                )
            ),
            'clarifications_used': used,
            'deferred': list(deferred),
            'reported_alarm': reported,
        },
    }


def logfile_case(name, scope, status, answer, missing=()):
    return {
        'id': name,
        'policy': 'logfile',
        'input': {
            'alarm_scope': scope,
        },
        'expected': {
            'status': status,
            'answer': answer,
            'question_fact': None,
            'selected': None,
            'alarms': scope.split('_or_'),
            'missing': list(missing),
        },
    }


# These explicit expectations were authored for development,
# alongside the policies.
STATIC = [
    abb_case(
        'A01_list',
        'list_possible_causes',
        {},
        'source_information',
    ),
    abb_case(
        'A02_list_denied',
        'list_possible_causes',
        {f: [False] for f in FACTS},
        'source_information',
    ),
    abb_case(
        'A03_review_missing',
        'review_reports',
        {},
        'needs_clarification',
        P,
    ),
    abb_case(
        'A04_review_conflict',
        'review_reports',
        {L: [True, False]},
        'needs_clarification',
        L,
    ),
    abb_case(
        'A05_review_denied',
        'review_reports',
        {f: [False] for f in FACTS},
        'reports_complete',
        states='CCCCC',
    ),
    abb_case(
        'A06_review_deferred',
        'review_reports',
        {},
        'insufficient_information',
        deferred=FACTS,
    ),
    abb_case(
        'A07_identify_cause',
        'identify_cause',
        {f: [True] for f in FACTS},
        'insufficient_evidence',
    ),

    license_case(
        'S01_absent_key',
        {
            'options_activated': [True],
            KEY: [False],
        },
        'description_supported',
        '8080',
        states='SC',
    ),
    license_case(
        'S02_uncovered',
        {
            'options_activated': [True],
            KEY: [True],
            COVER: [False],
        },
        'description_supported',
        '8081',
        states='CS',
    ),
    license_case(
        'S03_missing_key',
        {
            'options_activated': [True],
        },
        'needs_clarification',
        question=KEY,
    ),
    license_case(
        'S04_missing_coverage',
        {
            'options_activated': [True],
            KEY: [True],
        },
        'needs_clarification',
        question=COVER,
        states='CU',
    ),
    license_case(
        'S05_code_conflict',
        {
            'options_activated': [True],
            KEY: [False],
        },
        'conflicting_input',
        states='SC',
        reported='8081',
    ),
    license_case(
        'S06_report_conflict',
        {
            'options_activated': [True],
            KEY: [True, False],
        },
        'conflicting_input',
    ),
    license_case(
        'S07_budget_used',
        {
            'options_activated': [True],
        },
        'insufficient_evidence',
        used=2,
    ),
    license_case(
        'S08_licensed',
        {
            'options_activated': [True],
            KEY: [True],
            COVER: [True],
        },
        'insufficient_evidence',
        states='CC',
    ),

    logfile_case(
        'L01_shared',
        '61352_or_61353',
        'answer_supported',
        '_PROTNAME[0]',
    ),
    logfile_case(
        'L02_exact_61352',
        '61352',
        'answer_supported',
        '_PROTNAME[0]',
    ),
    logfile_case(
        'L03_exact_61353',
        '61353',
        'answer_supported',
        '_PROTNAME[0]',
    ),
    logfile_case(
        'L04_missing_evidence',
        '61358',
        'insufficient_evidence',
        None,
        ['61358'],
    ),
    logfile_case(
        'L05_incomplete_scope',
        '61352_or_61353_or_61358',
        'insufficient_evidence',
        None,
        ['61358'],
    ),
]


# Full caller-carried state on every turn;
# the server is stateless.
DIALOGUES = {
    'ABB_report_review': [
        abb_case(
            'B1',
            'review_reports',
            {},
            'needs_clarification',
            P,
        ),
        abb_case(
            'B2',
            'review_reports',
            {},
            'needs_clarification',
            W,
            deferred=[P],
        ),
        abb_case(
            'B3',
            'review_reports',
            {
                W: [False],
            },
            'needs_clarification',
            O,
            'UCUUU',
            [P],
        ),
        abb_case(
            'B4',
            'review_reports',
            {
                W: [False],
                O: [True],
            },
            'needs_clarification',
            L,
            'UCSUU',
            [P],
        ),
        abb_case(
            'B5',
            'review_reports',
            {
                W: [False],
                O: [True],
                L: [True],
            },
            'needs_clarification',
            C,
            'UCSSU',
            [P],
        ),
        abb_case(
            'B6',
            'review_reports',
            {
                W: [False],
                O: [True],
                L: [True],
            },
            'insufficient_information',
            states='UCSSU',
            deferred=[P, C],
        ),
    ],

    'Siemens_reports_supplied': [
        license_case(
            'T1',
            {
                'options_activated': [True],
            },
            'needs_clarification',
            question=KEY,
        ),
        license_case(
            'T2',
            {
                'options_activated': [True],
                KEY: [True],
            },
            'needs_clarification',
            question=COVER,
            states='CU',
            used=1,
        ),
        license_case(
            'T3',
            {
                'options_activated': [True],
                KEY: [True],
                COVER: [False],
            },
            'description_supported',
            '8081',
            states='CS',
            used=2,
        ),
    ],

    'Siemens_reports_unknown': [
        license_case(
            'U1',
            {
                'options_activated': [True],
            },
            'needs_clarification',
            question=KEY,
        ),
        license_case(
            'U2',
            {
                'options_activated': [True],
            },
            'needs_clarification',
            question=COVER,
            used=1,
            deferred=[KEY],
        ),
        license_case(
            'U3',
            {
                'options_activated': [True],
            },
            'insufficient_evidence',
            used=2,
            deferred=[KEY, COVER],
        ),
    ],
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(paths):
    result = {}

    for relative in paths:
        try:
            raw = (ROOT / relative).read_bytes()
            result[relative] = {
                'sha256': digest(raw),
                'bytes': len(raw),
            }
        except OSError as error:
            result[relative] = {
                'error': str(error),
            }

    return result


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_span(parent, evidence):
    start = evidence['start']
    end = evidence['end']

    require(
        type(start) is int
        and type(end) is int
        and 0 <= start < end <= len(parent['text']),
        'Invalid evidence offsets',
    )

    require(
        parent['text'][start:end] == evidence['quote'],
        'Quote differs from source span',
    )


def inspect_response(case, body, sources):
    """Missing fields and malformed evidence fail the case instead of being ignored."""
    view = None
    errors = []

    try:
        require(
            body['diagnosis_confirmed'] is False,
            'Diagnosis flag must be false',
        )

        require(
            body['approved_for_automatic_execution'] is False,
            'Execution flag must be false',
        )

        policy = case['policy']

        if policy == 'abb':
            require(
                body['mapping_status'] == 'development_not_reviewed',
                'Mapping status changed',
            )

            rows = body['source_records']

            require(
                body['source_record_count'] == len(rows) == 5,
                'Expected five source records',
            )

            parents = {
                p['parent_id']: p
                for p in sources['abb']['parents']
            }

            entries = {
                e['record_id']: e
                for e in sources['index']['entries']
            }

            for number, (row, cause) in enumerate(
                zip(rows, CAUSES),
                10,
            ):
                record = ABB + f'_r{number:03d}'

                require(
                    row['record_id'] == record
                    and row['possible_cause'] == cause,
                    'Wrong ABB record',
                )

                span = next(
                    s
                    for s in entries[record]['spans']
                    if s['field'] == 'possible_cause'
                )

                require(
                    row['evidence'] == span,
                    'Evidence differs from ABB index',
                )

                check_span(
                    parents[record],
                    row['evidence'],
                )

                require(
                    row['page_numbers']
                    == parents[record]['page_numbers'],
                    'Wrong ABB pages',
                )

                require(
                    row['context_ids']
                    == parents[record]['context_ids'],
                    'Wrong ABB context links',
                )

            clarification = body['clarification']

            question = (
                clarification['question']
                if clarification is not None
                else None
            )

            assessment = body['report_assessment']

            if assessment is not None:
                require(
                    len(assessment) == 5,
                    'Expected five report assessments',
                )

            if question is not None:
                fact = question['fact_id']

                record = (
                    ABB
                    + f'_r{10 + FACTS.index(fact):03d}'
                )

                require(
                    question['evidence_id']
                    == record + ':possible_cause',
                    'Wrong question evidence',
                )

                require(
                    question['page_numbers'] == [25],
                    'Wrong question pages',
                )

            view = {
                'status': body['status'],
                'question_fact': (
                    question['fact_id']
                    if question
                    else None
                ),
                'source_causes': [
                    r['possible_cause']
                    for r in rows
                ],
                'states': (
                    {
                        r['fact_id']: r['status']
                        for r in assessment
                    }
                    if assessment is not None
                    else None
                ),
                'deferred': (
                    clarification['deferred_fact_ids']
                    if clarification is not None
                    else None
                ),
            }

        else:
            require(
                body['annotation_status']
                == 'development_not_independently_reviewed',
                'Annotation status changed',
            )

            parents = {
                p['parent_id']: p
                for p in sources['siemens']['parents']
            }

            require(
                body['prepared_sha256']
                == sources['siemens_sha256'],
                'Wrong Siemens source fingerprint',
            )

            if policy == 'licensing':
                rows = body['candidates']

                require(
                    [
                        r['alarm_number']
                        for r in rows
                    ] == ['8080', '8081'],
                    'Wrong licensing candidates',
                )

                for row in rows:
                    evidence = row['evidence']
                    parent = parents[evidence['parent_id']]

                    require(
                        parent['alarm_number']
                        == row['alarm_number'],
                        'Wrong licensing source',
                    )

                    require(
                        evidence['page_numbers']
                        == parent['page_numbers'],
                        'Wrong licensing pages',
                    )

                    require(
                        evidence['page_scope']
                        == 'parent_section',
                        'Wrong page-reference scope',
                    )

                    check_span(
                        parent,
                        evidence,
                    )

                question = body['question']

                if question is not None:
                    require(
                        question['next_clarifications_used']
                        == case['input']['clarifications_used'] + 1,
                        'Incorrect next clarification count',
                    )

                    require(
                        question['next_clarifications_used'] <= 2,
                        'Question budget exceeded',
                    )

                view = {
                    'status': body['status'],
                    'selected': body[
                        'selected_description_alarm'
                    ],
                    'question_fact': (
                        question['fact_id']
                        if question
                        else None
                    ),
                    'states': {
                        r['alarm_number']:
                        r['evaluation']['status']
                        for r in rows
                    },
                    'clarifications_used':
                        body['clarifications_used'],
                    'deferred':
                        body['deferred_fact_ids'],
                    'reported_alarm':
                        body['reported_alarm_number'],
                }

            else:
                rows = body['source_sections']

                for row in rows:
                    parent = parents[row['parent_id']]

                    require(
                        parent['alarm_number']
                        == row['alarm_number'],
                        'Wrong logfile source',
                    )

                    require(
                        row['section_page_numbers']
                        == parent['page_numbers'],
                        'Wrong logfile pages',
                    )

                    evidence = row['answer_evidence']

                    if evidence is not None:
                        check_span(
                            parent,
                            evidence,
                        )

                        require(
                            evidence['quote']
                            == 'Check parameter _PROTNAME[0].',
                            'Wrong parameter quote',
                        )

                        require(
                            evidence['page_numbers']
                            == parent['page_numbers'],
                            'Wrong evidence pages',
                        )

                        require(
                            evidence['page_scope']
                            == 'parent_section',
                            'Wrong page-reference scope',
                        )

                    else:
                        require(
                            '_PROTNAME[0]'
                            not in parent['text'],
                            'Parameter evidence was omitted',
                        )

                require(
                    body['question'] is None,
                    'Unexpected logfile clarification',
                )

                view = {
                    'status': body['status'],
                    'answer': body['answer'],
                    'question_fact': None,
                    'selected':
                        body['selected_alarm_number'],
                    'alarms': [
                        r['alarm_number']
                        for r in rows
                    ],
                    'missing':
                        body[
                            'sections_without_answer_evidence'
                        ],
                }

        for key, expected in case['expected'].items():
            if view[key] != expected:
                errors.append(
                    f'{key}: expected {expected!r}; '
                    f'received {view[key]!r}'
                )

    except Exception as error:
        errors.append(
            f'{type(error).__name__}: {error}'
        )

    return view, errors


def run_case(
    client,
    case,
    sources,
    dialogue=None,
    turn=None,
):
    body = None
    view = None
    http = None

    started = perf_counter()
    errors = []

    try:
        response = client.post(
            URLS[case['policy']],
            json=deepcopy(case['input']),
        )

        http = response.status_code

        elapsed = round(
            (perf_counter() - started) * 1000,
            3,
        )

        body = response.json()

        if http != 200:
            errors.append(
                f'Expected HTTP 200; received {http}'
            )

        else:
            view, errors = inspect_response(
                case,
                body,
                sources,
            )

    except Exception as error:
        elapsed = round(
            (perf_counter() - started) * 1000,
            3,
        )

        errors.append(
            f'{type(error).__name__}: {error}'
        )

    return {
        **deepcopy(case),
        'dialogue': dialogue,
        'turn': turn,
        'http_status': http,
        'actual': view,
        'response': body,
        'request_elapsed_ms': elapsed,
        'passed': not errors,
        'errors': errors,
    }


def verifier_checks(records, sources):
    """Inject six defects to check that the evaluator can reject incorrect output."""
    by_id = {
        r['id']: r
        for r in records
    }

    specs = [
        (
            'wrong_answer',
            'L01_shared',
            lambda b: b.update(
                answer='_PROTNAME[1]'
            ),
        ),
        (
            'wrong_question',
            'S03_missing_key',
            lambda b: b['question'].update(
                fact_id='options_activated'
            ),
        ),
        (
            'missing_citation',
            'L01_shared',
            lambda b:
                b['source_sections'][0].pop(
                    'answer_evidence'
                ),
        ),
        (
            'missing_diagnosis_flag',
            'A01_list',
            lambda b:
                b.pop('diagnosis_confirmed'),
        ),
        (
            'execution_approved',
            'A01_list',
            lambda b:
                b.update(
                    approved_for_automatic_execution=True
                ),
        ),
        (
            'empty_response',
            'A01_list',
            lambda b: b.clear(),
        ),
    ]

    checks = []

    for name, case_id, mutate in specs:
        record = by_id[case_id]
        passed = False

        if record['passed']:
            changed = deepcopy(
                record['response']
            )

            mutate(changed)

            _, errors = inspect_response(
                record,
                changed,
                sources,
            )

            passed = bool(errors)

        checks.append({
            'defect': name,
            'rejected': passed,
        })

    return checks


def main():
    paths = list(
        SOURCE_FILES.values()
    ) + [
        'app/main.py'
    ]

    paths += [
        str(
            p.relative_to(ROOT)
        ).replace('\\', '/')
        for p in sorted(
            (ROOT / 'app/services').glob('*.py')
        )
    ]

    paths.append(
        str(
            Path(__file__)
            .resolve()
            .relative_to(ROOT)
        ).replace('\\', '/')
    )

    before = fingerprint(paths)

    sources = {}
    setup_errors = []

    for name, relative in SOURCE_FILES.items():
        try:
            raw = (
                ROOT / relative
            ).read_bytes()

            sources[name] = json.loads(
                raw.decode('utf-8-sig')
            )

            if name == 'siemens':
                sources['siemens_sha256'] = digest(
                    raw
                )

        except Exception as error:
            setup_errors.append(
                f'{relative}: '
                f'{type(error).__name__}: '
                f'{error}'
            )

    with TestClient(
        app,
        raise_server_exceptions=False,
    ) as client:

        records = [
            run_case(
                client,
                case,
                sources,
            )
            for case in STATIC
        ]

        for name, turns in DIALOGUES.items():
            records += [
                run_case(
                    client,
                    case,
                    sources,
                    name,
                    n,
                )
                for n, case in enumerate(
                    turns,
                    1,
                )
            ]

    for record in records:
        print(
            (
                'PASS '
                if record['passed']
                else 'FAIL '
            )
            + record['id']
        )

        if record['errors']:
            print(
                '  '
                + '; '.join(
                    record['errors']
                )
            )

    checks = verifier_checks(
        records,
        sources,
    )

    after = fingerprint(paths)

    unchanged = (
        before == after
        and all(
            'sha256' in value
            for value in before.values()
        )
    )

    static_results = [
        r
        for r in records
        if r['dialogue'] is None
    ]

    summaries = {}

    for name in DIALOGUES:
        turns = [
            r
            for r in records
            if r['dialogue'] == name
        ]

        summaries[name] = {
            'passed': all(
                r['passed']
                for r in turns
            ),
            'turns_passed': sum(
                r['passed']
                for r in turns
            ),
            'turns_total': len(turns),
            'questions_returned': sum(
                r['actual'] is not None
                and r['actual']['question_fact']
                is not None
                for r in turns
            ),
        }

    groups = {
        name: {
            'passed': sum(
                r['passed']
                for r in static_results
                if r['policy'] == name
            ),
            'total': sum(
                r['policy'] == name
                for r in static_results
            ),
        }
        for name in URLS
    }

    passed = (
        not setup_errors
        and unchanged
        and all(
            r['passed']
            for r in records
        )
        and all(
            c['rejected']
            for c in checks
        )
    )

    report = {
        'evaluation_version':
            'assistance_development_v1',

        'overall_passed':
            passed,

        'created_at_utc':
            datetime.now(
                timezone.utc
            ).isoformat(),

        'environment': {
            'python':
                platform.python_version(),

            'platform':
                platform.system(),

            'packages': {
                name: version(name)
                for name in (
                    'fastapi',
                    'starlette',
                    'pydantic',
                    'httpx',
                )
            },
        },

        'case_manifest_sha256':
            digest(
                json.dumps(
                    {
                        'static': STATIC,
                        'dialogues': DIALOGUES,
                    },
                    sort_keys=True,
                ).encode()
            ),

        'interpretation':
            'Agreement with authored development expectations; not diagnostic accuracy.',

        'limitations': [
            'Constructed structured-input cases authored alongside these policies; not held-out incidents.',
            'Dialogue turns are related; count three dialogues separately from twenty static scenarios.',
            'Mappings remain unreviewed; no comparison with competing methods or optimality claim.',
            'No semantic retrieval, free-text parsing, LLM generation, or machine diagnosis evaluated.',
            'Single-pass timings include in-process API calls and source validation; not deployment benchmarks.',
        ],

        'static_groups':
            groups,

        'dialogues':
            summaries,

        'verifier_rejection_checks':
            checks,

        'input_and_code_files_unchanged':
            unchanged,

        'files_before':
            before,

        'files_after':
            after,

        'setup_errors':
            setup_errors,

        'records':
            records,
    }

    directory = (
        ROOT / 'evaluation/reports'
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now(
        timezone.utc
    ).strftime(
        '%Y%m%dT%H%M%S_%fZ'
    )

    destination = (
        directory
        / (
            f'assistance_development_'
            f'{stamp}_'
            f'{uuid4().hex[:8]}.json'
        )
    )

    with destination.open(
        'x',
        encoding='utf-8',
    ) as handle:
        json.dump(
            report,
            handle,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )

    print(
        f'\nStatic scenarios: '
        f'{sum(r["passed"] for r in static_results)}'
        f'/{len(STATIC)} passed.'
    )

    print(
        f'Scripted dialogues: '
        f'{sum(d["passed"] for d in summaries.values())}'
        f'/{len(DIALOGUES)} passed.'
    )

    print(
        f'Dialogue turns: '
        f'{sum(d["turns_passed"] for d in summaries.values())}'
        f'/'
        f'{sum(d["turns_total"] for d in summaries.values())}'
        f' passed.'
    )

    print(
        f'Verifier rejection checks: '
        f'{sum(c["rejected"] for c in checks)}'
        f'/{len(checks)} passed.'
    )

    print(
        'Input and code files unchanged:',
        unchanged,
    )

    print(
        'Report saved:',
        destination,
    )

    print(
        'Overall:',
        'PASS' if passed else 'FAIL',
    )

    print(
        'Development behaviour only; '
        'no diagnostic accuracy claim.'
    )

    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
