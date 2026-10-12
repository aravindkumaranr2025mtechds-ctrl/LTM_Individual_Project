import unittest
from copy import deepcopy

from app.services.troubleshooting_question_builder import (
    QUESTION_FORMS,
    get_all_question_forms,
    get_question_form,
)


class TroubleshootingQuestionBuilderTests(
    unittest.TestCase
):
    def test_all_modes_have_forms(self):
        result = get_all_question_forms()

        self.assertEqual(
            result["supported_modes"],
            [
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            ],
        )

        self.assertEqual(
            set(result["forms"]),
            {
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            },
        )

    def test_logfile_requires_explicit_scope(self):
        result = get_question_form(
            "siemens_logfile"
        )

        field = result["form"]["fields"][0]

        self.assertEqual(
            field["field_id"],
            "alarm_scope",
        )

        self.assertTrue(
            field["required"]
        )

        self.assertEqual(
            field["input_type"],
            "single_choice",
        )

    def test_abb_contains_five_report_questions(self):
        result = get_question_form(
            "abb_stall"
        )

        ids = [
            field["field_id"]
            for field in result["form"]["fields"]
        ]

        for required in (
            "open_phase_reported",
            "wrong_application_reported",
            "overload_reported",
            "low_voltage_reported",
            "open_circuit_reported",
        ):
            self.assertIn(
                required,
                ids,
            )

    def test_licensing_contains_three_report_questions(self):
        result = get_question_form(
            "siemens_licensing"
        )

        ids = {
            field["field_id"]
            for field in result["form"]["fields"]
        }

        self.assertTrue(
            {
                "options_activated",
                "license_key_set",
                "entered_key_covers_activated_options",
            }
            <= ids
        )

    def test_invalid_mode_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            get_question_form(
                "guessed_policy"
            )

    def test_forms_do_not_alias_definition(self):
        before = deepcopy(
            QUESTION_FORMS
        )

        result = get_all_question_forms()

        result["forms"][
            "siemens_logfile"
        ]["title"] = "CHANGED"

        self.assertEqual(
            before,
            QUESTION_FORMS,
        )

    def test_safety_flags_false(self):
        result = get_question_form(
            "abb_stall"
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
