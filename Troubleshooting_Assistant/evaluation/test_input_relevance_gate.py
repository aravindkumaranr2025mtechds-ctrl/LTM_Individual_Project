from __future__ import annotations

import unittest

from app.services.input_relevance_gate import (
    assess_input_relevance,
)


class InputRelevanceGateTests(
    unittest.TestCase
):

    def test_real_maintenance_query_is_accepted(
        self,
    ):

        result = assess_input_relevance(
            "ABB motor stalls while running"
        )

        self.assertEqual(
            result["status"],
            "accepted",
        )

        self.assertEqual(
            result["classification"],
            "candidate_query",
        )

        self.assertTrue(
            result["continue_to_retrieval"]
        )


    def test_real_it_query_is_accepted(
        self,
    ):

        result = assess_input_relevance(
            "Ethernet link is down on the workstation"
        )

        self.assertEqual(
            result["status"],
            "accepted",
        )

        self.assertTrue(
            result["continue_to_retrieval"]
        )


    def test_alarm_identifier_query_is_not_rejected(
        self,
    ):

        result = assess_input_relevance(
            "Siemens alarm 8080"
        )

        self.assertEqual(
            result["status"],
            "accepted",
        )


    def test_casual_input_is_rejected(
        self,
    ):

        result = assess_input_relevance(
            "Hi how are you"
        )

        self.assertEqual(
            result["classification"],
            "casual_or_irrelevant",
        )

        self.assertEqual(
            result["status"],
            "rejected",
        )

        self.assertFalse(
            result["continue_to_retrieval"]
        )


    def test_casual_input_with_punctuation_is_rejected(
        self,
    ):

        result = assess_input_relevance(
            "Hi, how are you?"
        )

        self.assertEqual(
            result["classification"],
            "casual_or_irrelevant",
        )

        self.assertFalse(
            result["continue_to_retrieval"]
        )


    def test_clearly_irrelevant_request_is_rejected(
        self,
    ):

        result = assess_input_relevance(
            "Tell me a joke about robots"
        )

        self.assertEqual(
            result["status"],
            "rejected",
        )

        self.assertEqual(
            result["reason_code"],
            "clearly_irrelevant_request",
        )


    def test_multiple_gibberish_tokens_are_rejected(
        self,
    ):

        result = assess_input_relevance(
            "asdfgh xxxxx"
        )

        self.assertEqual(
            result["status"],
            "rejected",
        )

        self.assertEqual(
            result["classification"],
            "invalid_or_gibberish",
        )

        self.assertFalse(
            result["continue_to_retrieval"]
        )


    def test_repeated_letter_gibberish_is_rejected(
        self,
    ):

        result = assess_input_relevance(
            "xxxxxxxx"
        )

        self.assertEqual(
            result["status"],
            "rejected",
        )

        self.assertEqual(
            result["reason_code"],
            "obvious_gibberish",
        )


    def test_generic_problem_requests_more_detail(
        self,
    ):

        result = assess_input_relevance(
            "motor issue"
        )

        self.assertEqual(
            result["status"],
            "needs_more_detail",
        )

        self.assertEqual(
            result["classification"],
            "needs_more_detail",
        )

        self.assertFalse(
            result["continue_to_retrieval"]
        )


    def test_unknown_industrial_word_is_not_called_gibberish(
        self,
    ):

        result = assess_input_relevance(
            "PROTNAME parameter unavailable"
        )

        self.assertEqual(
            result["status"],
            "accepted",
        )

        self.assertEqual(
            result["classification"],
            "candidate_query",
        )


    def test_gate_does_not_extract_machine_facts(
        self,
    ):

        result = assess_input_relevance(
            "ABB motor stalls and phase may be open"
        )

        self.assertEqual(
            set(result),
            {
                "status",
                "classification",
                "continue_to_retrieval",
                "reason_code",
                "message",
                "diagnosis_confirmed",
                "approved_for_automatic_execution",
            },
        )

        for forbidden in (
            "manufacturer",
            "equipment",
            "alarm_number",
            "observations",
            "known_facts",
            "diagnosis",
        ):

            self.assertNotIn(
                forbidden,
                result,
            )

        self.assertFalse(
            result["diagnosis_confirmed"]
        )

        self.assertFalse(
            result[
                "approved_for_automatic_execution"
            ]
        )


    def test_non_string_input_is_rejected_by_contract(
        self,
    ):

        with self.assertRaises(
            TypeError
        ):

            assess_input_relevance(
                8080
            )


if __name__ == "__main__":
    unittest.main()
