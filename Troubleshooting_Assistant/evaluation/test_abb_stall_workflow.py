"""Read-only integration regressions requiring the project's real ABB files."""
import unittest

from fastapi.testclient import TestClient
from app.main import app

PREFIX = 'dde3696f00424107b1253d4dfd44a05b_ABB_LV_Motors_RevH_2022'
INDEX = PREFIX + '_structured_v1_ready_evidence_v1.json'
FACTS = [
    'open_phase_reported', 'wrong_application_reported', 'overload_reported',
    'low_voltage_reported', 'open_circuit_reported',
]
STALL = '/development/abb/conditions/stall'
CLARIFY = STALL + '/clarify'


class ABBStallWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def clarify(self, observations, deferred=None):
        response = self.client.post(CLARIFY, json={
            'index_filename': INDEX, 'observations': observations,
            'deferred_fact_ids': [] if deferred is None else deferred,
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['results_count'], 5)
        self.assertEqual(result['mapping_status'], 'development_not_reviewed')
        self.assertIs(result['diagnosis_confirmed'], False)
        self.assertIs(result['approved_for_automatic_execution'], False)
        return result

    def test_source_links_and_multiple_supported_conditions(self):
        response = self.client.post(STALL, json={
            'index_filename': INDEX,
            'observations': {'overload_reported': [True], 'low_voltage_reported': [True]},
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(result['results']), 5)
        for item in result['results']:
            expected = 'supported' if item['fact_id'] in FACTS[2:4] else 'unknown'
            self.assertEqual(item['status'], expected)
            self.assertEqual(item['evidence']['evidence_id'], item['record_id'] + ':possible_cause')
            self.assertEqual(item['page_numbers'], [25])
            self.assertEqual(len(item['context_ids']), 4)
        self.assertIs(result['diagnosis_confirmed'], False)

    def test_missing_reports_ask_first_source_linked_question(self):
        result = self.clarify({})
        question = result['clarification']['question']
        self.assertEqual(question['fact_id'], FACTS[0])
        self.assertEqual(question['reason'], 'missing_report')
        self.assertEqual(question['evidence_id'], PREFIX + '_r010:possible_cause')

    def test_conflict_takes_priority(self):
        result = self.clarify({'low_voltage_reported': [True, False]})
        question = result['clarification']['question']
        self.assertEqual(question['fact_id'], 'low_voltage_reported')
        self.assertEqual(question['reason'], 'conflicting_reports')

    def test_deferral_moves_question_without_resolving_fact(self):
        result = self.clarify({}, [FACTS[0]])
        self.assertEqual(result['clarification']['question']['fact_id'], FACTS[1])
        self.assertTrue(all(r['status'] == 'unknown' for r in result['results']))

    def test_all_deferred_stops_questions(self):
        result = self.clarify({}, FACTS)
        self.assertEqual(result['clarification']['status'], 'insufficient_information')
        self.assertIsNone(result['clarification']['question'])
        self.assertTrue(all(r['status'] == 'unknown' for r in result['results']))

    def test_complete_reports_do_not_confirm_diagnosis(self):
        for report in (True, False):
            with self.subTest(report=report):
                result = self.clarify({f: [report] for f in FACTS})
                self.assertEqual(result['clarification']['status'], 'reports_complete')
                self.assertIsNone(result['clarification']['question'])

    def test_requests_do_not_share_session_state(self):
        self.clarify({}, [FACTS[0]])
        result = self.clarify({})
        self.assertEqual(result['clarification']['question']['fact_id'], FACTS[0])
        self.assertEqual(result['clarification']['deferred_fact_ids'], [])

    def test_invalid_deferral_inputs_rejected(self):
        for deferred in (['unknown'], [FACTS[0], FACTS[0]], [1], None):
            with self.subTest(deferred=deferred):
                response = self.client.post(CLARIFY, json={
                    'index_filename': INDEX, 'observations': {},
                    'deferred_fact_ids': deferred,
                })
                self.assertEqual(response.status_code, 422, response.text)

    def test_invalid_reports_rejected_on_both_routes(self):
        for route in (STALL, CLARIFY):
            for observations in ({'low_voltage_reported': [1]},
                                 {'low_voltage_reported': ['false']}, {'unknown': []}):
                with self.subTest(route=route, observations=observations):
                    response = self.client.post(route, json={
                        'index_filename': INDEX, 'observations': observations,
                    })
                    self.assertEqual(response.status_code, 422, response.text)

    def test_original_pilot_route_still_works(self):
        response = self.client.post('/development/abb/conditions/check', json={
            'index_filename': INDEX, 'record_id': PREFIX + '_r013',
            'observations': {'low_voltage_reported': [False]},
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'contradicted')
        self.assertIs(response.json()['diagnosis_confirmed'], False)


if __name__ == '__main__':
    unittest.main()
