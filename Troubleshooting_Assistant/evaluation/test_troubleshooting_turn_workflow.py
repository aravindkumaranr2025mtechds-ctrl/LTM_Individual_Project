import unittest

from pydantic import ValidationError

from app.services.troubleshooting_turn_workflow import (
    TroubleshootingTurnRequest,
    run_troubleshooting_turn,
)


class TroubleshootingTurnWorkflowTests(
    unittest.TestCase
):
    def request(
        self,
        mode,
        answers,
        symptom="Example symptom",
    ):
        return TroubleshootingTurnRequest(
            machine_name="Example machine",
            symptom=symptom,
            mode=mode,
            answers=answers,
        )

    def test_abb_missing_reports_returns_question(self):
        result = run_troubleshooting_turn(
            self.request(
                "abb_stall",
                {
                    "requested_information":
                        "review_reports",
                },
                "Motor stalls",
            )
        )

        self.assertEqual(
            result["status"],
            "needs_clarification",
        )

        self.assertEqual(
            result["next_question"][
                "fact_id"
            ],
            "open_phase_reported",
        )

        self.assertFalse(
            result["server_session_created"]
        )

    def test_abb_answer_moves_to_next_question(self):
        result = run_troubleshooting_turn(
            self.request(
                "abb_stall",
                {
                    "requested_information":
                        "review_reports",
                    "open_phase_reported":
                        "no",
                },
                "Motor stalls",
            )
        )

        self.assertEqual(
            result["status"],
            "needs_clarification",
        )

        self.assertEqual(
            result["next_question"][
                "fact_id"
            ],
            "wrong_application_reported",
        )

    def test_licensing_missing_key_returns_question(self):
        result = run_troubleshooting_turn(
            self.request(
                "siemens_licensing",
                {
                    "options_activated":
                        "yes",
                },
                "Licensing issue",
            )
        )

        self.assertEqual(
            result["status"],
            "needs_clarification",
        )

        self.assertEqual(
            result["next_question"][
                "fact_id"
            ],
            "license_key_set",
        )

    def test_licensing_supported_result_finishes_turn(self):
        result = run_troubleshooting_turn(
            self.request(
                "siemens_licensing",
                {
                    "options_activated":
                        "yes",
                    "license_key_set":
                        "no",
                },
                "Licensing issue",
            )
        )

        self.assertEqual(
            result["status"],
            "turn_complete",
        )

        self.assertIsNone(
            result["next_question"]
        )

        self.assertEqual(
            result["assistance"][
                "result"
            ][
                "selected_description_alarm"
            ],
            "8080",
        )

    def test_logfile_has_no_clarification_turn(self):
        result = run_troubleshooting_turn(
            self.request(
                "siemens_logfile",
                {
                    "alarm_scope":
                        "61352_or_61353",
                },
                "Need logfile path",
            )
        )

        self.assertEqual(
            result["status"],
            "turn_complete",
        )

        self.assertIsNone(
            result["next_question"]
        )

        self.assertEqual(
            result["assistance"][
                "result"
            ][
                "answer"
            ],
            "_PROTNAME[0]",
        )

    def test_missing_logfile_scope_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            run_troubleshooting_turn(
                self.request(
                    "siemens_logfile",
                    {},
                )
            )

    def test_invalid_mode_rejected_by_request_model(self):
        with self.assertRaises(
            ValidationError
        ):
            TroubleshootingTurnRequest(
                machine_name="Example",
                symptom="Example",
                mode="guessed_policy",
                answers={},
            )

    def test_safety_flags_false(self):
        result = run_troubleshooting_turn(
            self.request(
                "siemens_logfile",
                {
                    "alarm_scope":
                        "61352",
                },
            )
        )

        self.assertFalse(
            result["diagnosis_confirmed"]
        )

        self.assertFalse(
            result[
                "approved_for_automatic_execution"
            ]
        )


if __name__ == "__main__":
    unittest.main()
