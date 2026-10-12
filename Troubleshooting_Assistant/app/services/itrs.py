"""Deterministic development reliability checks for guided responses."""
from copy import deepcopy
from typing import Any


VERSION = "itrs_development_v1"
VALID_SOURCE_CHECKS = {
    "matched_current_prepared_json",
    "matched_inspected_parent_text_hashes",
}
POSITIVE_STATUSES = {
    "source_information",
    "reports_complete",
    "description_supported",
    "answer_supported",
}
LIMIT_STATUSES = {
    "insufficient_information",
    "insufficient_evidence",
    "conflicting_input",
}
ABB_REPORT_FIELDS = (
    "open_phase_reported",
    "wrong_application_reported",
    "overload_reported",
    "low_voltage_reported",
    "open_circuit_reported",
)
LICENSING_REPORT_FIELDS = (
    "options_activated",
    "license_key_set",
    "entered_key_covers_activated_options",
)


def _evidence_items(mode: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    if mode == "abb_stall":
        return source.get("source_records") or []
    if mode == "siemens_licensing":
        return source.get("candidates") or []
    return source.get("source_sections") or []


def _has_provenance(mode: str, item: dict[str, Any]) -> bool:
    if mode == "abb_stall":
        evidence = item.get("evidence") or {}
        return bool(
            item.get("record_id")
            and evidence.get("evidence_id")
            and evidence.get("quote")
            and item.get("page_numbers")
        )
    if mode == "siemens_licensing":
        evidence = item.get("evidence") or {}
        return bool(
            item.get("alarm_number")
            and evidence.get("parent_id")
            and evidence.get("parent_text_sha256")
            and evidence.get("quote")
            and evidence.get("page_numbers")
        )
    return bool(
        item.get("alarm_number")
        and item.get("parent_id")
        and item.get("parent_text_sha256")
        and item.get("section_page_numbers")
    )


def _source_integrity(mode: str, source: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    if not source:
        return 0, {
            "source_validation_matched": False,
            "source_identity_present": False,
            "provenance_items": 0,
            "total_source_items": 0,
        }
    validation = source.get("source_validation") in VALID_SOURCE_CHECKS
    if mode == "abb_stall":
        identity = bool(source.get("symptom_id") and source.get("source_scope"))
    else:
        digest = source.get("prepared_sha256")
        identity = bool(source.get("prepared_filename") and isinstance(digest, str) and len(digest) == 64)
    items = _evidence_items(mode, source)
    linked = sum(_has_provenance(mode, item) for item in items)
    coverage = linked / len(items) if items else 0.0
    score = (10 if validation else 0) + (5 if identity else 0) + round(10 * coverage)
    return score, {
        "source_validation_matched": validation,
        "source_identity_present": identity,
        "provenance_items": linked,
        "total_source_items": len(items),
    }


def _input_quality(mode: str, source: dict[str, Any] | None, answers: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if mode == "abb_stall":
        request_type = answers.get("requested_information")
        relevant = () if request_type == "list_possible_causes" else ABB_REPORT_FIELDS
    elif mode == "siemens_licensing":
        relevant = LICENSING_REPORT_FIELDS
        if (source or {}).get("status") == "description_supported":
            selected = (source or {}).get("selected_description_alarm")
            selected_rows = [item for item in (source or {}).get("candidates", [])
                             if item.get("alarm_number") == selected]
            used = ((selected_rows[0].get("evaluation") or {}).get("used_fact_ids")
                    if len(selected_rows) == 1 else None)
            if used:
                relevant = tuple(used)
    else:
        relevant = ("alarm_scope",)
    known = sum(type(answers.get(key)) is bool for key in relevant)
    if mode == "siemens_logfile":
        known = int(isinstance(answers.get("alarm_scope"), str))
    conflicts = list((source or {}).get("conflicting_fact_ids") or [])
    if (source or {}).get("inconsistent_key_coverage_report"):
        conflicts.append("entered_key_covers_activated_options")
    if (source or {}).get("status") == "conflicting_input" and not conflicts:
        conflicts.append("reported_alarm_or_input_conflict")
    score = 20 if not relevant else round(20 * known / len(relevant))
    if conflicts:
        score = 0
    deferred = set(answers.get("deferred_fact_ids") or [])
    return score, {
        "known_relevant_fields": known,
        "total_relevant_fields": len(relevant),
        "deferred_relevant_fields": len(deferred.intersection(relevant)),
        "conflicting_fact_ids": sorted(set(conflicts)),
    }


def _policy_compliance(response: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    status = response.get("status")
    question = response.get("next_question")
    actions = (response.get("trace") or {}).get("actions") or []
    final_action = actions[-1] if actions else None
    if status in {"needs_clarification", "needs_user_input"}:
        expected = "ask_clarification"
        aligned = bool(question and question.get("fact_id") and question.get("choices"))
    elif status in POSITIVE_STATUSES:
        expected = "return_information"
        aligned = question is None
    elif status in LIMIT_STATUSES:
        expected = "abstain"
        aligned = question is None
    else:
        expected = None
        aligned = False
    aligned = bool(aligned and final_action == expected)
    source = response.get("source_result")
    tool_boundary = ((source is None and (response.get("trace") or {}).get("tool_calls") == 0)
                     or (source is not None and (response.get("trace") or {}).get("tool_calls", 0) >= 1))
    score = (20 if aligned else 0) + (5 if tool_boundary else 0)
    return score, {
        "expected_final_action": expected,
        "observed_final_action": final_action,
        "status_action_aligned": aligned,
        "tool_boundary_aligned": tool_boundary,
    }


def _answer_support(mode: str, response: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    status = response.get("status")
    source = response.get("source_result") or {}
    supported = False
    reason = "unrecognized_response_state"
    if status in {"needs_clarification", "needs_user_input"}:
        supported = bool(response.get("next_question"))
        reason = "clarification_returned_without_a_substantive_answer"
    elif status in LIMIT_STATUSES:
        selected = source.get("answer") or source.get("selected_description_alarm")
        supported = selected is None and response.get("diagnosis_confirmed") is False
        reason = "unsupported_answer_withheld"
    elif mode == "abb_stall" and status == "source_information":
        records = source.get("source_records") or []
        supported = bool(records) and all(_has_provenance(mode, item) for item in records)
        reason = "listed_causes_are_source_linked"
    elif mode == "abb_stall" and status == "reports_complete":
        rows = source.get("report_assessment") or []
        supported = bool(rows) and all(row.get("status") in {"supported", "contradicted"} and _has_provenance(mode, row) for row in rows)
        reason = "report_assessments_are_complete_and_source_linked"
    elif mode == "siemens_licensing" and status == "description_supported":
        selected = source.get("selected_description_alarm")
        rows = source.get("candidates") or []
        supported = sum(
            item.get("alarm_number") == selected
            and (item.get("evaluation") or {}).get("status") == "supported"
            and _has_provenance(mode, item)
            for item in rows
        ) == 1
        reason = "one_selected_description_has_support_and_source_evidence"
    elif mode == "siemens_logfile" and status == "answer_supported":
        answer = source.get("answer")
        rows = source.get("source_sections") or []
        supported = bool(answer and rows and source.get("answer_agreement") == "established"
                         and not source.get("sections_without_answer_evidence")
                         and all(item.get("parameter_name") == answer
                                 and (item.get("answer_evidence") or {}).get("quote")
                                 for item in rows))
        reason = "all_declared_sections_support_the_same_parameter"
    return (20 if supported else 0), {"support_rule_passed": supported, "reason": reason}


def _safety(response: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    source = response.get("source_result")
    top = response.get("diagnosis_confirmed") is False and response.get("approved_for_automatic_execution") is False
    nested = source is None or (source.get("diagnosis_confirmed") is False
                                and source.get("approved_for_automatic_execution") is False)
    return (5 if top else 0) + (5 if nested else 0), {
        "response_boundaries_preserved": top,
        "source_boundaries_preserved": nested,
    }


def calculate_itrs(response: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    """Return a non-calibrated behavior score without mutating either input."""
    snapshot = deepcopy(response)
    mode = snapshot.get("mode")
    source = snapshot.get("source_result")
    parts = {}
    for name, maximum, result in (
        ("source_integrity", 25, _source_integrity(mode, source)),
        ("input_quality", 20, _input_quality(mode, source, deepcopy(answers))),
        ("policy_compliance", 25, _policy_compliance(snapshot)),
        ("answer_support", 20, _answer_support(mode, snapshot)),
        ("safety_boundaries", 10, _safety(snapshot)),
    ):
        value, checks = result
        parts[name] = {"score": value, "maximum": maximum, "checks": checks}
    score = sum(part["score"] for part in parts.values())
    caps = []
    if parts["safety_boundaries"]["score"] < 10:
        score = min(score, 49)
        caps.append("safety_boundary_failure")
    if snapshot.get("status") in POSITIVE_STATUSES and parts["answer_support"]["score"] == 0:
        score = min(score, 69)
        caps.append("positive_answer_without_verified_support")
    if parts["policy_compliance"]["score"] < 25:
        score = min(score, 79)
        caps.append("policy_mismatch")
    status = snapshot.get("status")
    if source is None:
        label = "awaiting_source_scope"
    elif status in {"needs_clarification", "needs_user_input"}:
        label = "clarification_required"
    elif status in LIMIT_STATUSES:
        label = "safe_limit_reached"
    elif score >= 90:
        label = "source_supported_behavior"
    else:
        label = "review_required"
    return {
        "version": VERSION,
        "score": score,
        "maximum": 100,
        "label": label,
        "components": parts,
        "applied_caps": caps,
        "calibration_status": "not_calibrated",
        "interpretation": (
            "Development checks satisfied for this response. This score is not a probability, "
            "diagnostic confidence, machine-health assessment, or repair approval."
        ),
    }
