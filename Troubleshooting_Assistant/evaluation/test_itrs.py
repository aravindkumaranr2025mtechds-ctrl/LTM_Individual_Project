import unittest
from copy import deepcopy
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.agentic.contracts import AgentDecision
from app.services.assistant_workflow import ConversationRequest, router, run_conversation
from app.services.itrs import calculate_itrs


class ITRSDevelopmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def result(self, mode, answers):
        return run_conversation(ConversationRequest(mode=mode, answers=answers))

    def test_abb_source_list_has_full_behavior_score(self):
        result = self.result("abb_stall", {"requested_information": "list_possible_causes"})
        self.assertEqual(result["itrs"]["score"], 100)
        self.assertEqual(result["itrs"]["label"], "source_supported_behavior")
        self.assertEqual(result["itrs"]["components"]["source_integrity"]["checks"]["provenance_items"], 5)

    def test_missing_reports_reduce_input_component_only(self):
        result = self.result("abb_stall", {"requested_information": "review_reports"})
        score = result["itrs"]
        self.assertEqual(score["score"], 80)
        self.assertEqual(score["label"], "clarification_required")
        self.assertEqual(score["components"]["input_quality"]["score"], 0)
        self.assertEqual(score["components"]["policy_compliance"]["score"], 25)

    def test_complete_reports_receive_full_behavior_score_without_diagnosis(self):
        answers = {"requested_information": "review_reports", **{key: False for key in (
            "open_phase_reported", "wrong_application_reported", "overload_reported",
            "low_voltage_reported", "open_circuit_reported",
        )}}
        result = self.result("abb_stall", answers)
        self.assertEqual(result["status"], "reports_complete")
        self.assertEqual(result["itrs"]["score"], 100)
        self.assertIs(result["diagnosis_confirmed"], False)

    def test_safe_abstention_can_pass_behavior_checks(self):
        result = self.result("siemens_logfile", {"alarm_scope": "61358"})
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["itrs"]["score"], 100)
        self.assertEqual(result["itrs"]["label"], "safe_limit_reached")
        self.assertIsNone(result["source_result"]["answer"])

    def test_supported_siemens_answers_have_source_evidence(self):
        licensing = self.result("siemens_licensing", {
            "options_activated": True, "license_key_set": False,
            "entered_key_covers_activated_options": None,
        })
        logfile = self.result("siemens_logfile", {"alarm_scope": "61352_or_61353"})
        self.assertEqual(licensing["itrs"]["components"]["answer_support"]["score"], 20)
        self.assertEqual(licensing["itrs"]["score"], 100)
        self.assertEqual(logfile["itrs"]["components"]["answer_support"]["score"], 20)
        self.assertEqual(logfile["source_result"]["answer"], "_PROTNAME[0]")

    def test_planner_question_before_source_is_explicitly_labelled(self):
        decision = AgentDecision(
            action="ask_clarification", reason="Scope missing",
            requested_fact="alarm_scope", question="Untrusted wording",
        )
        with patch("app.services.assistant_workflow.OllamaAgentModelAdapter.decide", return_value=decision):
            result = self.result("siemens_logfile", {})
        self.assertEqual(result["itrs"]["label"], "awaiting_source_scope")
        self.assertEqual(result["itrs"]["components"]["source_integrity"]["score"], 0)
        self.assertEqual(result["itrs"]["components"]["policy_compliance"]["score"], 25)

    def test_removed_provenance_lowers_score(self):
        result = self.result("abb_stall", {"requested_information": "list_possible_causes"})
        altered = deepcopy(result)
        altered.pop("itrs")
        altered["source_result"]["source_records"][0]["evidence"] = {}
        score = calculate_itrs(altered, {"requested_information": "list_possible_causes"})
        self.assertLess(score["score"], 100)
        self.assertEqual(score["components"]["answer_support"]["score"], 0)
        self.assertIn("positive_answer_without_verified_support", score["applied_caps"])

    def test_policy_mismatch_is_capped(self):
        result = self.result("siemens_logfile", {"alarm_scope": "61352_or_61353"})
        altered = deepcopy(result)
        altered.pop("itrs")
        altered["trace"]["actions"][-1] = "ask_clarification"
        score = calculate_itrs(altered, {"alarm_scope": "61352_or_61353"})
        self.assertLessEqual(score["score"], 79)
        self.assertIn("policy_mismatch", score["applied_caps"])

    def test_safety_violation_is_capped_below_half(self):
        result = self.result("siemens_logfile", {"alarm_scope": "61352_or_61353"})
        altered = deepcopy(result)
        altered.pop("itrs")
        altered["approved_for_automatic_execution"] = True
        score = calculate_itrs(altered, {"alarm_scope": "61352_or_61353"})
        self.assertLessEqual(score["score"], 49)
        self.assertIn("safety_boundary_failure", score["applied_caps"])

    def test_metric_does_not_mutate_inputs(self):
        result = self.result("abb_stall", {"requested_information": "list_possible_causes"})
        result.pop("itrs")
        answers = {"requested_information": "list_possible_causes"}
        expected_result, expected_answers = deepcopy(result), deepcopy(answers)
        first = calculate_itrs(result, answers)
        second = calculate_itrs(result, answers)
        self.assertEqual(first, second)
        self.assertEqual(result, expected_result)
        self.assertEqual(answers, expected_answers)

    def test_http_response_exposes_components_and_warning(self):
        response = self.client.post("/assistant/turn", json={
            "mode": "siemens_logfile", "answers": {"alarm_scope": "61352_or_61353"},
        })
        self.assertEqual(response.status_code, 200, response.text)
        score = response.json()["itrs"]
        self.assertEqual(set(score["components"]), {
            "source_integrity", "input_quality", "policy_compliance",
            "answer_support", "safety_boundaries",
        })
        self.assertEqual(score["calibration_status"], "not_calibrated")
        self.assertIn("not a probability", score["interpretation"])


if __name__ == "__main__":
    unittest.main()
