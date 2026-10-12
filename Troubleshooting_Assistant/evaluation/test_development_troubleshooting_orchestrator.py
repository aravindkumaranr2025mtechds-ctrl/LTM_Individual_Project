import unittest

from pydantic import TypeAdapter, ValidationError

from app.services.development_troubleshooting_orchestrator import (
    DevelopmentTroubleshootingRequest,
    orchestrate_development_troubleshooting,
)


ABB = (
    'dde3696f00424107b1253d4dfd44a05b_'
    'ABB_LV_Motors_RevH_2022'
)

INDEX = (
    ABB
    + '_structured_v1_ready_evidence_v1.json'
)


class DevelopmentTroubleshootingOrchestratorTests(
    unittest.TestCase
):
    def setUp(self):
        self.adapter = TypeAdapter(
            DevelopmentTroubleshootingRequest
        )

    def test_abb_source_listing_routes_explicitly(self):
        request = self.adapter.validate_python({
            'mode': 'abb_stall',
            'payload': {
                'index_filename': INDEX,
                'observations': {},
                'requested_information':
                    'list_possible_causes',
                'deferred_fact_ids': [],
            },
        })

        result = (
            orchestrate_development_troubleshooting(
                request
            )
        )

        self.assertEqual(
            result['selected_policy'],
            'abb_stall',
        )

        self.assertEqual(
            result['result']['status'],
            'source_information',
        )

        self.assertFalse(
            result['diagnosis_confirmed']
        )

        self.assertFalse(
            result[
                'approved_for_automatic_execution'
            ]
        )

    def test_siemens_licensing_routes_explicitly(self):
        request = self.adapter.validate_python({
            'mode': 'siemens_licensing',
            'payload': {
                'observations': {
                    'options_activated': [True],
                    'license_key_set': [False],
                },
                'clarifications_used': 0,
                'deferred_fact_ids': [],
            },
        })

        result = (
            orchestrate_development_troubleshooting(
                request
            )
        )

        self.assertEqual(
            result['selected_policy'],
            'siemens_licensing',
        )

        self.assertEqual(
            result['result']['status'],
            'description_supported',
        )

        self.assertEqual(
            result['result'][
                'selected_description_alarm'
            ],
            '8080',
        )

        self.assertFalse(
            result['diagnosis_confirmed']
        )

    def test_siemens_logfile_routes_explicitly(self):
        request = self.adapter.validate_python({
            'mode': 'siemens_logfile',
            'payload': {
                'alarm_scope':
                    '61352_or_61353',
            },
        })

        result = (
            orchestrate_development_troubleshooting(
                request
            )
        )

        self.assertEqual(
            result['selected_policy'],
            'siemens_logfile',
        )

        self.assertEqual(
            result['result']['status'],
            'answer_supported',
        )

        self.assertEqual(
            result['result']['answer'],
            '_PROTNAME[0]',
        )

        self.assertFalse(
            result['diagnosis_confirmed']
        )

    def test_mode_is_required(self):
        with self.assertRaises(
            ValidationError
        ):
            self.adapter.validate_python({
                'payload': {},
            })

    def test_payload_must_match_declared_mode(self):
        with self.assertRaises(
            ValidationError
        ):
            self.adapter.validate_python({
                'mode': 'siemens_logfile',
                'payload': {
                    'index_filename': INDEX,
                    'observations': {},
                    'requested_information':
                        'list_possible_causes',
                },
            })


if __name__ == '__main__':
    unittest.main()
