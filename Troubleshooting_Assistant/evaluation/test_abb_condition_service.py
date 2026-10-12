"""Pilot service contract tests; source validation has its own test suite."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from app.services.abb_condition_service import (
    DOCUMENT_ID, PILOT_RECORD_ID, PREPARED_SHA256, check_abb_pilot_condition,
)


class ABBConditionServiceTests(unittest.TestCase):
    def setUp(self):
        self.index = {
            "source": {"document_id": DOCUMENT_ID, "prepared_sha256": PREPARED_SHA256},
            "entries": [{
                "record_id": PILOT_RECORD_ID,
                "symptom_id": DOCUMENT_ID + "_s002",
                "page_numbers": [25], "context_ids": ["context_example"],
                "spans": [
                    {"field": "symptom", "quote": "Motor stalls"},
                    {"field": "possible_cause", "quote": "Low voltage",
                     "evidence_id": PILOT_RECORD_ID + ":possible_cause",
                     "start": 0, "end": 11},
                ],
            }],
        }
        patcher = patch("app.services.abb_condition_service.load_abb_evidence_index", return_value=self.index)
        self.loader = patcher.start()
        self.addCleanup(patcher.stop)

    def check(self, observations, record_id=PILOT_RECORD_ID):
        return check_abb_pilot_condition("example.json", record_id, observations)

    def test_four_report_cases(self):
        for reports, expected in (([True], "supported"), ([False], "contradicted"),
                                  ([None], "unknown"), ([True, False], "unknown")):
            with self.subTest(reports=reports):
                result = self.check({"low_voltage_reported": reports})
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["mapping_status"], "development_not_reviewed")
                self.assertIs(result["diagnosis_confirmed"], False)
                self.assertIs(result["approved_for_automatic_execution"], False)
                self.assertNotIn("manufacturer_guidance", result)
        self.assertEqual(self.loader.call_count, 4)

    def test_missing_report_is_unknown(self):
        self.assertEqual(self.check({})["status"], "unknown")

    def test_source_link_is_preserved(self):
        result = self.check({})
        self.assertEqual(result["evidence"]["evidence_id"], PILOT_RECORD_ID + ":possible_cause")
        self.assertEqual(result["evidence"]["page_numbers"], [25])
        self.loader.assert_called_once_with("example.json")

    def test_unsupported_record_never_falls_back(self):
        with self.assertRaisesRegex(ValueError, "Unsupported pilot record"):
            self.check({}, DOCUMENT_ID + "_r012")
        self.loader.assert_not_called()

    def test_unsupported_fact_and_numeric_reports_rejected(self):
        for observations in ({"voltage": [200]}, {"low_voltage_reported": [1]},
                             {"low_voltage_reported": ["false"]}, []):
            with self.subTest(observations=observations), self.assertRaises(ValueError):
                self.check(observations)
        self.loader.assert_not_called()

    def test_changed_source_fingerprint_rejected(self):
        self.index["source"]["prepared_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Source differs"):
            self.check({})

    def test_changed_mapping_quote_rejected(self):
        self.index["entries"][0]["spans"][1]["quote"] = "Overload"
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            self.check({})

    def test_missing_record_rejected(self):
        self.index["entries"] = []
        with self.assertRaisesRegex(ValueError, "missing or duplicated"):
            self.check({})

    def test_source_validation_errors_propagate(self):
        for error in (ValueError("Changed source"), FileNotFoundError("Missing source")):
            self.loader.side_effect = error
            with self.assertRaises(type(error)):
                self.check({})

    def test_inputs_and_source_not_modified(self):
        before = deepcopy(self.index)
        observations = {"low_voltage_reported": [True]}
        result = self.check(observations)
        result["evidence"]["context_ids"].append("extra")
        self.assertEqual(self.index, before)
        self.assertEqual(observations, {"low_voltage_reported": [True]})


if __name__ == "__main__":
    unittest.main()
