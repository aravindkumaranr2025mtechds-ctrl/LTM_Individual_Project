"""HTTP contract tests; run from the project root with unittest discovery."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.services.abb_condition_service import PILOT_RECORD_ID

URL = '/development/abb/conditions/check'

class ABBConditionAPITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        patcher = patch('app.main.check_abb_pilot_condition')
        self.service = patcher.start()
        self.addCleanup(patcher.stop)
        self.body = {'index_filename': 'example.json', 'record_id': PILOT_RECORD_ID,
                     'observations': {'low_voltage_reported': [True]}}

    def post(self):
        return self.client.post(URL, json=self.body)

    def test_status_and_reports_forwarded(self):
        for reports, status in (([True], 'supported'), ([False], 'contradicted'),
                                ([], 'unknown'), ([True, False], 'unknown')):
            with self.subTest(reports=reports):
                self.body['observations']['low_voltage_reported'] = reports
                self.service.return_value = {'status': status, 'mapping_status': 'development_not_reviewed',
                                             'diagnosis_confirmed': False, 'approved_for_automatic_execution': False}
                response = self.post()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), self.service.return_value)
                self.service.assert_called_with(index_filename='example.json', record_id=PILOT_RECORD_ID,
                                                observations={'low_voltage_reported': reports})

    def test_empty_observations_default_to_empty_reports(self):
        self.body['observations'] = {}
        self.service.return_value = {'status': 'unknown'}
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.service.call_args.kwargs['observations'], {'low_voltage_reported': []})

    def test_null_report_accepted(self):
        self.body['observations'] = {'low_voltage_reported': [None]}
        self.service.return_value = {'status': 'unknown'}
        self.assertEqual(self.post().status_code, 200)

    def test_numeric_and_string_reports_rejected(self):
        for reports in ([1], [0], ['true'], ['false'], [0.0]):
            with self.subTest(reports=reports):
                self.body['observations']['low_voltage_reported'] = reports
                self.assertEqual(self.post().status_code, 422)
        self.service.assert_not_called()

    def test_report_limit(self):
        self.body['observations']['low_voltage_reported'] = [True] * 33
        self.assertEqual(self.post().status_code, 422)
        self.service.assert_not_called()

    def test_unknown_record_rejected(self):
        self.body['record_id'] = 'unknown'
        self.assertEqual(self.post().status_code, 422)
        self.service.assert_not_called()

    def test_extra_fields_rejected(self):
        self.body['unexpected'] = True
        self.assertEqual(self.post().status_code, 422)
        del self.body['unexpected']
        self.body['observations']['voltage'] = [200]
        self.assertEqual(self.post().status_code, 422)
        self.service.assert_not_called()

    def test_invalid_filenames_rejected(self):
        for filename in ('../a.json', 'C:\\a.json', 'a.npz', ' a.json', 'a.json\n'):
            with self.subTest(filename=filename):
                self.body['index_filename'] = filename
                self.assertEqual(self.post().status_code, 422)
        self.service.assert_not_called()

    def test_missing_required_fields_rejected(self):
        for name in ('index_filename', 'record_id', 'observations'):
            with self.subTest(name=name):
                response = self.client.post(URL, json={k:v for k,v in self.body.items() if k != name})
                self.assertEqual(response.status_code, 422)
        self.service.assert_not_called()

    def test_missing_source_404_without_path_disclosure(self):
        self.service.side_effect = FileNotFoundError('/private/location')
        response = self.post()
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('/private/location', response.text)

    def test_source_validation_failure_422(self):
        self.service.side_effect = ValueError('Source differs from pilot mapping')
        self.assertEqual(self.post().status_code, 422)

    def test_unexpected_failure_500(self):
        self.service.side_effect = RuntimeError('internal-secret')
        with self.assertLogs('app.main', level='ERROR'):
            response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('internal-secret', response.text)

    def test_existing_routes_still_registered(self):
        registered = {(method, route.path) for route in app.routes for method in getattr(route, 'methods', [])}
        required = {('GET','/'), ('GET','/health'), ('POST','/troubleshoot'),
                    ('POST','/documents/upload'), ('POST','/documents/process'), ('POST','/documents/chunk'),
                    ('POST','/documents/search'), ('POST','/documents/search/abb'),
                    ('POST','/documents/search/abb/confirm')}
        self.assertTrue(required <= registered)
        self.assertEqual(self.client.get('/health').status_code, 200)

    def test_swagger_schema_exposes_development_route(self):
        schema = self.client.get('/openapi.json').json()
        self.assertIn(URL, schema['paths'])
        self.assertEqual(schema['paths'][URL]['post']['tags'], ['Development'])

if __name__ == '__main__':
    unittest.main()
