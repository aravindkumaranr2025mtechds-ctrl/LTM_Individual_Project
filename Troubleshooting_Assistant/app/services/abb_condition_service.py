"""One source-bound development mapping; not a reviewed diagnosis policy.

Only ABB record r013 (Motor stalls / Low voltage) is mapped in this pilot.
Reports must describe the same machine and observation interval. True/False
means low voltage explicitly reported/denied; None means no information.
No voltage threshold or measurement interpretation is implemented here.
All other records are unsupported, not contradicted. No remedies are returned.
"""
from app.services.condition_checker import evaluate_condition
from app.services.evidence_index import load_abb_evidence_index


DOCUMENT_ID = "dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022"
PILOT_RECORD_ID = DOCUMENT_ID + "_r013"
PILOT_FACT_ID = "low_voltage_reported"
PREPARED_SHA256 = "f1e9ec709763a1ca70716b83bfcb89acf515b6c10777106e40e06a5bbf8a94d5"


def check_abb_pilot_condition(index_filename, record_id, observations):
    """Check the pilot condition against explicit structured reports.

    ValueError: unsupported record/fact, invalid reports, stale source/mapping.
    FileNotFoundError: index or prepared source missing.
    The original index validator runs on every call. This function neither
    changes its annotations nor upgrades their review status.
    """
    if record_id != PILOT_RECORD_ID:
        raise ValueError("Unsupported pilot record; only ABB r013 is mapped. No fallback.")
    if not isinstance(observations, dict) or any(
        key != PILOT_FACT_ID for key in observations
    ):
        raise ValueError("Only the low_voltage_reported observation is supported.")
    condition = {"fact": PILOT_FACT_ID, "expected": True}
    evaluation = evaluate_condition(condition, observations)
    index = load_abb_evidence_index(index_filename)
    source = index["source"]
    if (
        source["document_id"] != DOCUMENT_ID
        or source["prepared_sha256"] != PREPARED_SHA256
    ):
        raise ValueError("Source differs from the pilot mapping; review is required.")
    entries = [e for e in index["entries"] if e["record_id"] == record_id]
    if len(entries) != 1:
        raise ValueError("Pilot evidence record is missing or duplicated.")
    entry = entries[0]
    spans = {span["field"]: span for span in entry["spans"]}
    if (
        entry["symptom_id"] != DOCUMENT_ID + "_s002"
        or spans["symptom"]["quote"] != "Motor stalls"
        or spans["possible_cause"]["quote"] != "Low voltage"
        or spans["possible_cause"]["evidence_id"] != record_id + ":possible_cause"
    ):
        raise ValueError("Pilot mapping no longer matches its source evidence.")
    return {
        "mode": "abb_pilot_condition_check",
        "status": evaluation["status"],
        "mapping_status": "development_not_reviewed",
        "source_validation": "matched_current_prepared_json",
        "document_id": DOCUMENT_ID,
        "record_id": record_id,
        "symptom_id": entry["symptom_id"],
        "symptom": spans["symptom"]["quote"],
        "possible_cause": spans["possible_cause"]["quote"],
        "evidence": {
            "evidence_id": spans["possible_cause"]["evidence_id"],
            "quote": spans["possible_cause"]["quote"],
            "start": spans["possible_cause"]["start"],
            "end": spans["possible_cause"]["end"],
            "page_numbers": list(entry["page_numbers"]),
            "context_ids": list(entry["context_ids"]),
        },
        "condition": condition,
        "evaluation": evaluation,
        "diagnosis_confirmed": False,
        "approved_for_automatic_execution": False,
        "message": (
            "Logical support relative to supplied reports only. "
            "The mapping is a development example, not a reviewed condition "
            "annotation, measurement assessment, or confirmed cause."
        ),
    }
