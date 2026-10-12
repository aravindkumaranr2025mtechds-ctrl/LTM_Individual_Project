"""Three-valued logic over explicit, caller-supplied observations.

This is a logic primitive, not an ABB annotation loader or fault diagnosis.
It does not parse free text, establish evidence reliability, infer conditions
from remedies, or approve actions. A separate reviewed mapping must define
each fact and bind its condition to the relevant manual span before API use.

Condition grammar:
  {"fact": "phase_open", "expected": True}
  {"all": [condition, ...]}  or  {"any": [condition, ...]}
Negation of an atomic fact uses expected=False. Lists must be non-empty.

Observations map fact IDs to lists of reports: True, False, or None.
Missing facts, empty reports and only-None reports are unknown. Opposing
boolean reports are conflicting and remain unknown, never last-write-wins.
Reports must concern the same machine and observation interval; the caller
owns that scope. None means no information and does not negate a report.
"""

MAX_DEPTH = 16
MAX_NODES = 256


def _identifier(value):
    return (
        isinstance(value, str) and bool(value)
        and value == value.strip()
        and len(value) <= 128
        and all(c.isascii() and (c.isalnum() or c == "_") for c in value)
    )


def evaluate_condition(condition, observations):
    """Return support relative to supplied reports, not a confirmed cause.

    Invalid schemas raise ValueError. All branches are validated, including
    branches that would not affect the result. Inputs are never modified.
    No models, files, network calls, or external dependencies are used.
    """
    if not isinstance(observations, dict):
        raise ValueError("Observations must map fact IDs to lists of reports.")
    for fact, reports in observations.items():
        if not _identifier(fact) or not isinstance(reports, list):
            raise ValueError("Each fact requires a valid ID and a report list.")
        if any(value is not None and type(value) is not bool for value in reports):
            raise ValueError("Reports must be True, False or None; no coercion.")

    used, missing, conflicting = set(), set(), set()
    node_count = 0

    def visit(node, depth):
        nonlocal node_count
        node_count += 1
        if depth > MAX_DEPTH or node_count > MAX_NODES:
            raise ValueError("Condition exceeds the supported complexity limit.")
        if not isinstance(node, dict):
            raise ValueError("Each condition must be an object.")
        if set(node) == {"fact", "expected"}:
            fact, expected = node["fact"], node["expected"]
            if not _identifier(fact) or type(expected) is not bool:
                raise ValueError("A fact needs a valid ID and boolean expected value.")
            used.add(fact)
            values = {v for v in observations.get(fact, []) if v is not None}
            if not values:
                missing.add(fact)
                status = "unknown"
            elif len(values) > 1:
                conflicting.add(fact)
                status = "unknown"
            else:
                status = "supported" if expected in values else "contradicted"
            return {"fact": fact, "expected": expected, "status": status}
        if set(node) not in ({"all"}, {"any"}):
            raise ValueError("Use a fact/expected pair, all, or any; no extra keys.")
        operator = next(iter(node))
        children = node[operator]
        if not isinstance(children, list) or not children:
            raise ValueError("all and any require a non-empty condition list.")
        evaluated = [visit(child, depth + 1) for child in children]
        statuses = [child["status"] for child in evaluated]
        if operator == "all":
            status = (
                "contradicted" if "contradicted" in statuses else
                "supported" if all(s == "supported" for s in statuses) else
                "unknown"
            )
        else:
            status = (
                "supported" if "supported" in statuses else
                "contradicted" if all(s == "contradicted" for s in statuses) else
                "unknown"
            )
        return {"operator": operator, "status": status, "children": evaluated}

    trace = visit(condition, 1)
    return {
        "status": trace["status"],
        "scope": "logical_support_relative_to_supplied_observations",
        "used_fact_ids": sorted(used),
        "missing_fact_ids": sorted(missing),
        "conflicting_fact_ids": sorted(conflicting),
        "trace": trace,
        "diagnosis_confirmed": False,
        "approved_for_automatic_execution": False,
    }
