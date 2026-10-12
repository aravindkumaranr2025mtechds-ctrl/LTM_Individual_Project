"""Offline behavioral tests; no manual annotations or clinical/field claims."""
import itertools
import unittest
from copy import deepcopy

from app.services.condition_checker import evaluate_condition


def fact(name="a", expected=True):
    return {"fact": name, "expected": expected}


class ConditionCheckerTests(unittest.TestCase):
    def test_boolean_reports_and_atomic_negation(self):
        for expected, report in itertools.product((True, False), repeat=2):
            with self.subTest(expected=expected, report=report):
                result = evaluate_condition(fact(expected=expected), {"a": [report]})
                self.assertEqual(result["status"], "supported" if expected == report else "contradicted")

    def test_absence_is_unknown_even_for_negative_condition(self):
        for observations in ({}, {"a": []}, {"a": [None]}):
            for expected in (True, False):
                with self.subTest(observations=observations, expected=expected):
                    result = evaluate_condition(fact(expected=expected), observations)
                    self.assertEqual(result["status"], "unknown")
                    self.assertEqual(result["missing_fact_ids"], ["a"])

    def test_conflicts_do_not_use_report_order(self):
        for reports in ([True, False], [False, True], [None, True, True, False]):
            result = evaluate_condition(fact(), {"a": reports})
            self.assertEqual(result["status"], "unknown")
            self.assertEqual(result["conflicting_fact_ids"], ["a"])
            self.assertEqual(result["missing_fact_ids"], [])

    def test_unknown_report_does_not_erase_known_report(self):
        self.assertEqual(evaluate_condition(fact(), {"a": [None, True, True]})["status"], "supported")

    def test_all_truth_table(self):
        expected = ["supported", "contradicted", "unknown",
                    "contradicted", "contradicted", "contradicted",
                    "unknown", "contradicted", "unknown"]
        for (a, b), outcome in zip(itertools.product((True, False, None), repeat=2), expected):
            with self.subTest(a=a, b=b):
                self.assertEqual(evaluate_condition({"all": [fact(), fact("b")]}, {"a": [a], "b": [b]})["status"], outcome)

    def test_any_truth_table(self):
        expected = ["supported", "supported", "supported",
                    "supported", "contradicted", "unknown",
                    "supported", "unknown", "unknown"]
        for (a, b), outcome in zip(itertools.product((True, False, None), repeat=2), expected):
            with self.subTest(a=a, b=b):
                self.assertEqual(evaluate_condition({"any": [fact(), fact("b")]}, {"a": [a], "b": [b]})["status"], outcome)

    def test_nested_condition_preserves_trace_and_unresolved_facts(self):
        condition = {"all": [fact(), {"any": [fact("b", False), fact("c")]}]}
        result = evaluate_condition(condition, {"a": [True], "b": [False]})
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["missing_fact_ids"], ["c"])
        self.assertEqual(result["trace"]["children"][1]["children"][1]["status"], "unknown")

    def test_resolved_group_still_reports_conflicting_child(self):
        result = evaluate_condition({"any": [fact(), fact("b")]}, {"a": [True], "b": [False, True]})
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["conflicting_fact_ids"], ["b"])

    def test_no_input_mutation_or_action_approval(self):
        condition, observations = fact(), {"a": [True], "unrelated": [False]}
        before = deepcopy((condition, observations))
        result = evaluate_condition(condition, observations)
        self.assertEqual((condition, observations), before)
        self.assertEqual(result["used_fact_ids"], ["a"])
        self.assertIs(result["diagnosis_confirmed"], False)
        self.assertIs(result["approved_for_automatic_execution"], False)

    def test_invalid_reports_rejected_without_coercion(self):
        for reports in ([1], [0], ["false"], [0.0], [{}], True, None):
            with self.subTest(reports=reports), self.assertRaises(ValueError):
                evaluate_condition(fact(), {"a": reports})

    def test_invalid_observation_container_and_identifiers(self):
        for observations in ([], None, {"bad id": [True]}, {1: [True]}):
            with self.subTest(observations=observations), self.assertRaises(ValueError):
                evaluate_condition(fact(), observations)

    def test_invalid_conditions(self):
        invalid = [{}, [], {"all": []}, {"any": []}, {"not": fact()},
                   {"fact": "a"}, fact(expected=1), fact("bad id"),
                   {"fact": "a", "expected": True, "remedy": "do this"},
                   {"all": [fact()], "any": [fact()]}, {"all": fact()}]
        for condition in invalid:
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                evaluate_condition(condition, {})

    def test_invalid_branch_is_not_hidden_by_decisive_branch(self):
        for op, report in (("any", True), ("all", False)):
            with self.subTest(op=op), self.assertRaises(ValueError):
                evaluate_condition({op: [fact(), {"unsupported": True}]}, {"a": [report]})

    def test_complexity_limits(self):
        condition = fact()
        for _ in range(17):
            condition = {"all": [condition]}
        for oversized in (condition, {"any": [fact()] * 256}):
            with self.assertRaises(ValueError):
                evaluate_condition(oversized, {})


if __name__ == "__main__":
    unittest.main()
