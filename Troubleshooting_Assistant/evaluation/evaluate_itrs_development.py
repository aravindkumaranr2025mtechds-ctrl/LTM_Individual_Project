"""Run repeatable ITRS development scenarios and save a JSON report."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from app.services.assistant_workflow import ConversationRequest, run_conversation
from app.services.itrs import calculate_itrs


ABB_FIELDS = (
    "open_phase_reported", "wrong_application_reported", "overload_reported",
    "low_voltage_reported", "open_circuit_reported",
)


def run(mode, answers):
    return run_conversation(ConversationRequest(mode=mode, answers=answers))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    scenarios = [
        ("A01_source_list", "abb_stall", {"requested_information": "list_possible_causes"}, "source_information", 100),
        ("A02_missing_reports", "abb_stall", {"requested_information": "review_reports"}, "needs_clarification", 80),
        ("A03_complete_denials", "abb_stall", {"requested_information": "review_reports", **{key: False for key in ABB_FIELDS}}, "reports_complete", 100),
        ("A04_all_deferred", "abb_stall", {"requested_information": "review_reports", **{key: None for key in ABB_FIELDS}}, "insufficient_information", 80),
        ("A05_cause_with_partial_reports", "abb_stall", {"requested_information": "identify_cause", "overload_reported": True}, "insufficient_evidence", 84),
        ("S01_description_8080", "siemens_licensing", {"options_activated": True, "license_key_set": False}, "description_supported", 100),
        ("S02_description_8081", "siemens_licensing", {"options_activated": True, "license_key_set": True, "entered_key_covers_activated_options": False}, "description_supported", 100),
        ("S03_missing_key", "siemens_licensing", {"options_activated": True}, "needs_clarification", 87),
        ("S04_conflicting_alarm", "siemens_licensing", {"options_activated": True, "license_key_set": False, "reported_alarm_number": "8081"}, "conflicting_input", 80),
        ("L01_shared_parameter", "siemens_logfile", {"alarm_scope": "61352_or_61353"}, "answer_supported", 100),
        ("L02_missing_section_evidence", "siemens_logfile", {"alarm_scope": "61358"}, "insufficient_evidence", 100),
    ]
    results = []
    for case_id, mode, answers, expected_status, expected_score in scenarios:
        response = run(mode, answers)
        metric = response["itrs"]
        require(response["status"] == expected_status, f"{case_id}: status")
        require(metric["score"] == expected_score, f"{case_id}: expected {expected_score}, got {metric['score']}")
        require(metric["calibration_status"] == "not_calibrated", f"{case_id}: calibration label")
        require(response["diagnosis_confirmed"] is False, f"{case_id}: diagnosis boundary")
        require(response["approved_for_automatic_execution"] is False, f"{case_id}: execution boundary")
        results.append({
            "case_id": case_id, "mode": mode, "status": response["status"],
            "score": metric["score"], "label": metric["label"],
            "component_scores": {name: part["score"] for name, part in metric["components"].items()},
            "passed": True,
        })
        print(f"PASS {case_id}: status={response['status']}; ITRS={metric['score']}/100; {metric['label']}")

    base = run("abb_stall", {"requested_information": "list_possible_causes"})
    base.pop("itrs")
    tamper_cases = []
    altered = deepcopy(base)
    altered["source_result"]["source_records"][0]["evidence"] = {}
    tamper_cases.append(("T01_missing_evidence", calculate_itrs(altered, {"requested_information": "list_possible_causes"}), 69, "positive_answer_without_verified_support"))
    altered = deepcopy(base)
    altered["trace"]["actions"][-1] = "ask_clarification"
    tamper_cases.append(("T02_policy_mismatch", calculate_itrs(altered, {"requested_information": "list_possible_causes"}), 79, "policy_mismatch"))
    altered = deepcopy(base)
    altered["approved_for_automatic_execution"] = True
    tamper_cases.append(("T03_safety_violation", calculate_itrs(altered, {"requested_information": "list_possible_causes"}), 49, "safety_boundary_failure"))
    for case_id, metric, maximum_score, cap in tamper_cases:
        require(metric["score"] <= maximum_score, f"{case_id}: cap")
        require(cap in metric["applied_caps"], f"{case_id}: missing cap")
        results.append({"case_id": case_id, "score": metric["score"], "applied_caps": metric["applied_caps"], "passed": True})
        print(f"PASS {case_id}: capped at {metric['score']}/100")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    report_dir = Path(__file__).resolve().parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"itrs_development_{stamp}.json"
    report = {
        "metric": "Industrial Troubleshooting Reliability Score",
        "version": "itrs_development_v1",
        "overall": "PASS",
        "static_scenarios": len(scenarios),
        "tamper_checks": len(tamper_cases),
        "results": results,
        "interpretation": "Development behavior checks only; not diagnostic confidence or repair approval.",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nStatic response scenarios: {len(scenarios)}/{len(scenarios)} passed.")
    print(f"Tamper and cap checks: {len(tamper_cases)}/{len(tamper_cases)} passed.")
    print("Report saved:", report_path)
    print("Overall: PASS")
    print("ITRS remains non-calibrated and does not measure diagnostic accuracy.")


if __name__ == "__main__":
    main()
