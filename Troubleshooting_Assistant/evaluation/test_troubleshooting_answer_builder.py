import unittest
from copy import deepcopy

from app.services.troubleshooting_answer_builder import (
    build_structured_assistance,
)


class TroubleshootingAnswerBuilderTests(
    unittest.TestCase
):
    def test_abb_yes_no_unknown_conversion(self):
        result = build_structured_assistance(
            "abb_stall",
            {
                "requested_information":
                    "review_reports",
                "low_voltage_reported":
                    "yes",
                "open_circuit_reported":
                    "unknown",
                "overload_reported":
                    "no",
            },
        )

        observations = result[
            "payload"
        ]["observations"]

        self.assertEqual(
            observations[
                "low_voltage_reported"
            ],
            [True],
        )

        self.assertEqual(
            observations[
                "open_circuit_reported"
            ],
            [None],
        )

        self.assertEqual(
            observations[
                "overload_reported"
            ],
            [False],
        )

    def test_abb_requires_task(self):
        with self.assertRaises(
            ValueError
        ):
            build_structured_assistance(
                "abb_stall",
                {},
            )

    def test_licensing_conversion(self):
        result = build_structured_assistance(
            "siemens_licensing",
            {
                "options_activated":
                    "yes",
                "license_key_set":
                    "no",
                "reported_alarm_number":
                    "8080",
            },
        )

        payload = result[
            "payload"
        ]

        self.assertEqual(
            payload[
                "observations"
            ][
                "options_activated"
            ],
            [True],
        )

        self.assertEqual(
            payload[
                "observations"
            ][
                "license_key_set"
            ],
            [False],
        )

        self.assertEqual(
            payload[
                "reported_alarm_number"
            ],
            "8080",
        )

    def test_logfile_requires_explicit_scope(self):
        with self.assertRaises(
            ValueError
        ):
            build_structured_assistance(
                "siemens_logfile",
                {},
            )

    def test_logfile_builds_exact_scope(self):
        result = build_structured_assistance(
            "siemens_logfile",
            {
                "alarm_scope":
                    "61352_or_61353",
            },
        )

        self.assertEqual(
            result,
            {
                "mode":
                    "siemens_logfile",
                "payload": {
                    "alarm_scope":
                        "61352_or_61353",
                    "requested_information":
                        "logfile_path_parameter",
                },
            },
        )

    def test_invalid_tri_state_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            build_structured_assistance(
                "siemens_licensing",
                {
                    "options_activated":
                        "probably",
                },
            )

    def test_invalid_mode_rejected(self):
        with self.assertRaises(
            ValueError
        ):
            build_structured_assistance(
                "guessed_policy",
                {},
            )

    def test_input_not_modified(self):
        answers = {
            "alarm_scope":
                "61352",
        }

        before = deepcopy(
            answers
        )

        build_structured_assistance(
            "siemens_logfile",
            answers,
        )

        self.assertEqual(
            before,
            answers,
        )


if __name__ == "__main__":
    unittest.main()
