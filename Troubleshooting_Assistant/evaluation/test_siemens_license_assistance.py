"""Read-only development tests for the bounded 8080/8081 source comparison."""
import unittest
from fastapi.testclient import TestClient
from app.main import app

URL = '/development/siemens/licensing/compare'


class SiemensLicenseTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def check(self, observations, **extra):
        response = self.client.post(URL, json={'observations': observations, **extra})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertIs(result['diagnosis_confirmed'], False)
        self.assertIs(result['approved_for_automatic_execution'], False)
        self.assertEqual(result['annotation_status'], 'development_not_independently_reviewed')
        for candidate in result['candidates']:
            self.assertEqual(candidate['evidence']['page_numbers'], [114])
            self.assertEqual(candidate['evidence']['end'] - candidate['evidence']['start'],
                             len(candidate['evidence']['quote']))
        return result

    def test_absent_key_supports_8080_description(self):
        result = self.check({'options_activated': [True], 'license_key_set': [False]})
        self.assertEqual(result['status'], 'description_supported')
        self.assertEqual(result['selected_description_alarm'], '8080')

    def test_uncovered_options_support_8081_description(self):
        result = self.check({'options_activated': [True], 'license_key_set': [True],
                             'entered_key_covers_activated_options': [False]})
        self.assertEqual(result['status'], 'description_supported')
        self.assertEqual(result['selected_description_alarm'], '8081')

    def test_missing_key_fact_asks_discriminator(self):
        result = self.check({'options_activated': [True]})
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertEqual(result['question']['fact_id'], 'license_key_set')
        self.assertIsNone(result['selected_description_alarm'])

    def test_key_present_alone_does_not_confirm_8081(self):
        result = self.check({'options_activated': [True], 'license_key_set': [True]})
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertEqual(result['question']['fact_id'], 'entered_key_covers_activated_options')

    def test_licensed_options_support_neither(self):
        result = self.check({'options_activated': [True], 'license_key_set': [True],
                             'entered_key_covers_activated_options': [True]})
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['selected_description_alarm'])

    def test_no_activated_options_support_neither(self):
        self.assertEqual(self.check({'options_activated': [False]})['status'], 'insufficient_evidence')

    def test_explicit_alarm_conflict_never_switches_alarm(self):
        result = self.check({'options_activated': [True], 'license_key_set': [False]},
                             reported_alarm_number='8081')
        self.assertEqual(result['status'], 'conflicting_input')
        self.assertIsNone(result['selected_description_alarm'])
        self.assertEqual(result['reported_alarm_number'], '8081')

    def test_opposing_reports_are_conflicting(self):
        result = self.check({'license_key_set': [True, False]})
        self.assertEqual(result['status'], 'conflicting_input')
        self.assertEqual(result['conflicting_fact_ids'], ['license_key_set'])

    def test_absent_key_and_coverage_assertion_conflict(self):
        result = self.check({'license_key_set': [False], 'entered_key_covers_activated_options': [True]})
        self.assertEqual(result['status'], 'conflicting_input')
        self.assertIs(result['inconsistent_key_coverage_report'], True)

    def test_turn_budget_stops_questions(self):
        result = self.check({'options_activated': [True]}, clarifications_used=2)
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['question'])

    def test_deferred_fact_is_not_repeated(self):
        result = self.check({'options_activated': [True], 'license_key_set': [False, True]},
                             deferred_fact_ids=['license_key_set'])
        self.assertEqual(result['status'], 'conflicting_input')
        result = self.check({}, deferred_fact_ids=[
            'options_activated', 'license_key_set', 'entered_key_covers_activated_options'])
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['question'])

    def test_invalid_inputs_rejected(self):
        for payload in (
            {'observations': {'license_key_set': [1]}},
            {'reported_alarm_number': '99999999'},
            {'clarifications_used': 3},
            {'observations': {'unknown': [True]}},
            {'prepared_filename': '../file.json'},
            {'deferred_fact_ids': ['license_key_set', 'license_key_set']},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(URL, json=payload)
                self.assertEqual(response.status_code, 422, response.text)


if __name__ == '__main__':
    unittest.main()
