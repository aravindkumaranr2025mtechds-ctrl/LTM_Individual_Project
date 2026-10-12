import unittest
from copy import deepcopy

from app.services.troubleshooting_input_guidance import (
    SUPPORTED_MODES,
    get_troubleshooting_input_guidance,
)


class TroubleshootingInputGuidanceTests(
    unittest.TestCase
):
    def test_all_supported_modes_returned(self):
        result = get_troubleshooting_input_guidance()

        self.assertEqual(
            result["supported_modes"],
            [
                "abb_stall",
                "siemens_licensing",
                "siemens_logfile",
            ],
        )

        self.assertEqual(
            set(result["modes"]),
            set(SUPPORTED_MODES),
        )

        self.assertFalse(
            result["diagnosis_confirmed"]
        )

        self.assertFalse(
            result[
                "approved_for_automatic_execution"
            ]
        )

    def test_abb_guidance_lists_all_observations(self):
        result = get_troubleshooting_input_guidance(
            "abb_stall"
        )

        self.assertEqual(
            result["guidance"]["observation_fields"],
            [
                "open_phase_reported",
                "wrong_application_reported",
                "overload_reported",
                "low_voltage_reported",
                "open_circuit_reported",
            ],
        )

    def test_siemens_licensing_guidance(self):
        result = get_troubleshooting_input_guidance(
            "siemens_licensing"
        )

        self.assertEqual(
            result["guidance"][
                "reported_alarm_number_values"
            ],
            ["8080", "8081"],
        )

        self.assertEqual(
            result["guidance"][
                "clarification_budget"
            ],
            2,
        )

    def test_siemens_logfile_scope_is_explicit(self):
        result = get_troubleshooting_input_guidance(
            "siemens_logfile"
        )

        self.assertEqual(
            result["guidance"]["alarm_scope_values"],
            [
                "61352_or_61353",
                "61352",
                "61353",
                "61358",
                "61352_or_61353_or_61358",
            ],
        )

        limitations = " ".join(
            result["guidance"]["limitations"]
        ).lower()

        self.assertIn(
            "never inferred",
            limitations,
        )

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            get_troubleshooting_input_guidance(
                "guessed_policy"
            )

    def test_returned_guidance_does_not_alias_definition(self):
        before = deepcopy(
            SUPPORTED_MODES
        )

        result = get_troubleshooting_input_guidance()

        result["modes"]["abb_stall"]["title"] = (
            "CHANGED"
        )

        self.assertEqual(
            before,
            SUPPORTED_MODES,
        )


if __name__ == "__main__":
    unittest.main()
