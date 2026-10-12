"""Fixed-order development clarification baseline; not an optimized policy."""
from app.services.abb_stall_conditions import MAPPINGS, check_abb_stall_conditions


def clarify_abb_stall_conditions(index_filename, observations, deferred_fact_ids=None):
    """Return one question, prioritizing conflicts over missing reports.

    The caller carries deferred IDs across turns for the same machine/interval.
    Deferral means the user cannot clarify now, not that the condition is false.
    This function is stateless. It neither stores replies nor diagnoses faults.
    """
    deferred = [] if deferred_fact_ids is None else deferred_fact_ids
    allowed = {item[2] for item in MAPPINGS}
    if (not isinstance(deferred, list)
            or any(not isinstance(f, str) or f not in allowed for f in deferred)
            or len(deferred) != len(set(deferred))):
        raise ValueError('Deferred IDs must be a unique list of supported fact IDs.')

    result = check_abb_stall_conditions(index_filename, observations)
    unresolved = [r for r in result['results'] if r['status'] == 'unknown']
    available = [r for r in unresolved if r['fact_id'] not in deferred]
    conflicts = [r for r in available if r['evaluation']['conflicting_fact_ids']]
    pending = conflicts + [r for r in available if not r['evaluation']['conflicting_fact_ids']]

    question = None
    if pending:
        item = pending[0]
        conflict = bool(item['evaluation']['conflicting_fact_ids'])
        prompt = (
            'Reports disagree about this condition. For the same machine and '
            'observation interval, can you resolve the report: '
            if conflict else
            'For the same machine and observation interval, what is already '
            'known about this condition: '
        )
        question = {
            'fact_id': item['fact_id'],
            'record_id': item['record_id'],
            'evidence_id': item['evidence']['evidence_id'],
            'page_numbers': list(item['page_numbers']),
            'reason': 'conflicting_reports' if conflict else 'missing_report',
            'text': prompt + item['possible_cause'] + '?',
            'options': ['reported_present', 'reported_absent', 'cannot_clarify_now'],
        }
        status = 'needs_clarification'
    elif unresolved:
        status = 'insufficient_information'
    else:
        status = 'reports_complete'

    result['clarification'] = {
        'policy': 'fixed_order_conflicts_first_development_v1',
        'status': status,
        'question': question,
        'unresolved_fact_ids': [r['fact_id'] for r in unresolved],
        'deferred_fact_ids': list(deferred),
        'note': 'Use existing reports only. Report completeness is not a confirmed diagnosis.',
    }
    return result
