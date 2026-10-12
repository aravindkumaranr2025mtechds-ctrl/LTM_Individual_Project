"""Development task-scope integration checks against the real ABB source."""
import unittest
from fastapi.testclient import TestClient
from app.main import app

PREFIX = 'dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022'
INDEX = PREFIX + '_structured_v1_ready_evidence_v1.json'
URL = '/development/abb/stall/assist'
FACTS = ['open_phase_reported', 'wrong_application_reported', 'overload_reported',
         'low_voltage_reported', 'open_circuit_reported']


class ABBStallAssistanceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def call(self, task, observations=None, deferred=None):
        response = self.client.post(URL, json={
            'index_filename': INDEX, 'requested_information': task,
            'observations': {} if observations is None else observations,
            'deferred_fact_ids': [] if deferred is None else deferred,
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['source_record_count'], 5)
        self.assertEqual(result['mapping_status'], 'development_not_reviewed')
        self.assertIs(result['diagnosis_confirmed'], False)
        self.assertIs(result['approved_for_automatic_execution'], False)
        return result

    def test_source_listing_answers_without_questions(self):
        result = self.call('list_possible_causes')
        self.assertEqual(result['status'], 'source_information')
        self.assertIsNone(result['clarification'])
        self.assertIsNone(result['report_assessment'])
        self.assertIs(result['observations_used_for_report_assessment'], False)
        self.assertEqual({r['record_id'] for r in result['source_records']},
                         {PREFIX + f'_r{n:03d}' for n in range(10, 15)})
        for item in result['source_records']:
            self.assertEqual(item['evidence']['quote'], item['possible_cause'])
            self.assertEqual(item['page_numbers'], [25])
            self.assertEqual(len(item['context_ids']), 4)

    def test_source_listing_does_not_hide_denied_causes(self):
        result = self.call('list_possible_causes', {f: [False] for f in FACTS})
        self.assertEqual(len(result['source_records']), 5)
        self.assertEqual(result['status'], 'source_information')
        self.assertIsNone(result['clarification'])

    def test_review_missing_reports_asks_question(self):
        result = self.call('review_reports')
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertEqual(result['clarification']['question']['fact_id'], FACTS[0])

    def test_review_conflict_takes_priority(self):
        result = self.call('review_reports', {'low_voltage_reported': [True, False]})
        self.assertEqual(result['clarification']['question']['fact_id'], 'low_voltage_reported')
        self.assertEqual(result['clarification']['question']['reason'], 'conflicting_reports')

    def test_review_deferral_preserves_unknowns(self):
        result = self.call('review_reports', {}, FACTS)
        self.assertEqual(result['status'], 'insufficient_information')
        self.assertIsNone(result['clarification']['question'])
        self.assertTrue(all(r['status'] == 'unknown' for r in result['report_assessment']))

    def test_complete_review_is_not_diagnosis(self):
        result = self.call('review_reports', {f: [True] for f in FACTS})
        self.assertEqual(result['status'], 'reports_complete')
        self.assertIs(result['diagnosis_confirmed'], False)

    def test_one_supported_report_does_not_prove_unique_cause(self):
        observations = {f: [False] for f in FACTS}
        observations['low_voltage_reported'] = [True]
        result = self.call('identify_cause', observations)
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['clarification'])
        self.assertIsNone(result['report_assessment'])

    def test_all_positive_reports_do_not_prove_cause(self):
        result = self.call('identify_cause', {f: [True] for f in FACTS})
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['clarification'])

    def test_invalid_requests_rejected(self):
        base = {'index_filename': INDEX, 'requested_information': 'review_reports', 'observations': {}}
        for changes in (
            {'requested_information': 'repair_motor'},
            {'unexpected': True},
            {'observations': {'low_voltage_reported': [1]}},
            {'deferred_fact_ids': [FACTS[0], FACTS[0]]},
            {'deferred_fact_ids': ['unknown']},
            {'index_filename': '../file.json'},
        ):
            with self.subTest(changes=changes):
                response = self.client.post(URL, json={**base, **changes})
                self.assertEqual(response.status_code, 422, response.text)

    def test_task_switch_does_not_share_state(self):
        self.call('review_reports', {}, FACTS)
        result = self.call('review_reports')
        self.assertEqual(result['clarification']['question']['fact_id'], FACTS[0])
        self.assertEqual(self.call('list_possible_causes')['status'], 'source_information')
        self.assertEqual(self.call('identify_cause')['status'], 'insufficient_evidence')


if __name__ == '__main__':
    unittest.main()
