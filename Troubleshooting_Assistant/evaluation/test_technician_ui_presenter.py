import unittest

from app.services.technician_ui_presenter import (
    build_technician_view,
    choices_for_fact,
    humanize_field,
)


class TechnicianUIPresenterTests(
    unittest.TestCase
):

    def test_internal_field_is_humanized(self):

        self.assertEqual(
            humanize_field(
                "low_voltage_reported"
            ),
            "Supply voltage condition",
        )

    def test_alarm_scope_choices_are_human_readable(self):

        choices = choices_for_fact(
            "alarm_scope"
        )

        self.assertGreaterEqual(
            len(choices),
            5,
        )

        self.assertEqual(
            choices[0]["label"],
            "Alarm 61352",
        )

    def test_clarification_view_is_simple(self):

        result = (
            build_technician_view(
                {
                    "status":
                        "needs_user_input",

                    "state": {
                        "known_facts": {
                            "manufacturer":
                                "Siemens"
                        },

                        "unknown_facts": [
                            "alarm_scope"
                        ],
                    },

                    "final_decision": {
                        "action":
                            "ask_clarification",

                        "requested_fact":
                            "alarm_scope",

                        "question":
                            "Which alarm scope should be checked?",

                        "tool_name":
                            None,
                    },
                }
            )
        )

        self.assertEqual(
            result["headline"],
            "A little more information is needed",
        )

        self.assertEqual(
            result[
                "requested_fact"
            ][
                "label"
            ],
            "Alarm source",
        )

        self.assertFalse(
            result[
                "safety"
            ][
                "diagnosis"
            ][
                "confirmed"
            ]
        )

    def test_completed_evidence_view(self):

        result = (
            build_technician_view(
                {
                    "status":
                        "completed",

                    "state": {
                        "known_facts": {
                            "alarm_scope":
                                "61352"
                        },

                        "unknown_facts":
                            [],

                        "last_tool_result": {
                            "tool_name":
                                "siemens_logfile",

                            "result": {
                                "result": {
                                    "status":
                                        "answer_supported",

                                    "answer":
                                        "_PROTNAME[0]",
                                }
                            },
                        },
                    },

                    "final_decision": {
                        "action":
                            "return_information",

                        "tool_name":
                            None,
                    },
                }
            )
        )

        self.assertEqual(
            result["headline"],
            "Verified guidance is available",
        )

        self.assertEqual(
            result[
                "evidence"
            ][
                "answer"
            ],
            "_PROTNAME[0]",
        )

    def test_safety_language_is_operator_friendly(self):

        result = (
            build_technician_view(
                {
                    "status":
                        "abstained",

                    "state": {},
                }
            )
        )

        self.assertEqual(
            result[
                "safety"
            ][
                "diagnosis"
            ][
                "label"
            ],
            "Cause not yet confirmed",
        )

        self.assertEqual(
            result[
                "safety"
            ][
                "automatic_execution"
            ][
                "label"
            ],
            "No automatic machine action will be performed",
        )


if __name__ == "__main__":
    unittest.main()
