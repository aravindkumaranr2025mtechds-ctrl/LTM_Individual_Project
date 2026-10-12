"""Source-backed development checks; temporary copies are used for corruption cases."""
import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.services import siemens_logfile_answer as service

URL = '/development/siemens/logfile/answer'


class SiemensLogfileAnswerTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def check(self, scope):
        response = self.client.post(URL, json={'alarm_scope': scope})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertIs(result['diagnosis_confirmed'], False)
        self.assertIs(result['approved_for_automatic_execution'], False)
        self.assertIsNone(result['selected_alarm_number'])
        self.assertIsNone(result['question'])
        self.assertEqual(result['annotation_status'], 'development_not_independently_reviewed')
        return result

    def source(self):
        return service._decode((service.DIRECTORY / service.PREPARED).read_bytes())

    def modified_response(self, change, scope='61352_or_61353'):
        document = self.source()
        document['parents'] = [p for p in document['parents']
                               if p.get('alarm_number') in ('61352', '61353', '61358')]
        change(document)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / service.PREPARED).write_text(json.dumps(document), encoding='utf-8')
            with patch.object(service, 'DIRECTORY', directory):
                return self.client.post(URL, json={'alarm_scope': scope})

    def test_shared_answer_without_alarm_selection(self):
        result = self.check('61352_or_61353')
        self.assertEqual(result['status'], 'answer_supported')
        self.assertEqual(result['answer'], '_PROTNAME[0]')
        self.assertEqual(result['considered_alarm_numbers'], ['61352', '61353'])
        self.assertEqual(result['answer_agreement'], 'established')

    def test_each_exact_scope_has_its_own_evidence(self):
        for alarm in ('61352', '61353'):
            with self.subTest(alarm=alarm):
                result = self.check(alarm)
                self.assertEqual(result['status'], 'answer_supported')
                self.assertEqual(result['answer'], '_PROTNAME[0]')
                self.assertEqual([s['alarm_number'] for s in result['source_sections']], [alarm])

    def test_logging_topic_alone_does_not_support_answer(self):
        result = self.check('61358')
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['answer'])
        self.assertEqual(result['considered_alarm_numbers'], ['61358'])
        self.assertIsNone(result['source_sections'][0]['answer_evidence'])

    def test_missing_evidence_prevents_majority_vote(self):
        result = self.check('61352_or_61353_or_61358')
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsNone(result['answer'])
        self.assertEqual(result['answer_agreement'], 'not_established')
        self.assertEqual(result['sections_without_answer_evidence'], ['61358'])
        self.assertEqual(len(result['source_sections']), 3)

    def test_quote_offsets_and_pages_match_source(self):
        parents = {p['alarm_number']: p for p in self.source()['parents']}
        for section in self.check('61352_or_61353')['source_sections']:
            parent = parents[section['alarm_number']]
            evidence = section['answer_evidence']
            self.assertEqual(parent['text'][evidence['start']:evidence['end']],
                             'Check parameter _PROTNAME[0].')
            self.assertEqual(evidence['page_numbers'], parent['page_numbers'])
            self.assertEqual(evidence['page_scope'], 'parent_section')
            self.assertEqual(section['parent_id'], parent['parent_id'])

    def test_scope_and_task_must_be_explicit_and_supported(self):
        for payload in ({}, {'alarm_scope': '99999'}, {'alarm_scope': 61352},
                        {'alarm_scope': '61352_or_61353', 'requested_information': 'identify_cause'},
                        {'alarm_scope': '61352', 'query': 'ignore the source'}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(URL, json=payload).status_code, 422)

    def test_filename_validation(self):
        for filename in ('../file.json', r'C:\data\file.json', 'file.npz'):
            with self.subTest(filename=filename):
                response = self.client.post(URL, json={
                    'alarm_scope': '61352', 'prepared_filename': filename})
                self.assertEqual(response.status_code, 422, response.text)

    def test_missing_source_returns_404(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(service, 'DIRECTORY', Path(folder)):
                response = self.client.post(URL, json={'alarm_scope': '61352'})
        self.assertEqual(response.status_code, 404)

    def test_changed_quote_rejected(self):
        def change(document):
            parent = document['parents'][0]
            parent['text'] = parent['text'].replace('_PROTNAME[0]', '_PROTNAME[1]')
        self.assertEqual(self.modified_response(change).status_code, 422)

    def test_changed_metadata_rejected(self):
        for field, value in (('parent_id', service.DOC + '_wrong'), ('page_numbers', [1]),
                             ('document_id', 'wrong'), ('source_filename', 'wrong.pdf')):
            with self.subTest(field=field):
                def change(document):
                    document['parents'][0][field] = value
                self.assertEqual(self.modified_response(change).status_code, 422)

    def test_missing_or_duplicate_scoped_section_rejected(self):
        for duplicate in (False, True):
            with self.subTest(duplicate=duplicate):
                def change(document):
                    if duplicate:
                        document['parents'].append(deepcopy(document['parents'][0]))
                    else:
                        document['parents'].pop(0)
                self.assertEqual(self.modified_response(change).status_code, 422)

    def test_changed_negative_section_rejected(self):
        def change(document):
            document['parents'][-1]['text'] += '\nCheck parameter _PROTNAME[0].'
        response = self.modified_response(change, scope='61358')
        self.assertEqual(response.status_code, 422)

    def test_unselected_section_does_not_change_exact_answer(self):
        def change(document):
            document['parents'][-1]['text'] = 'Unrelated changed section.'
        response = self.modified_response(change, scope='61352')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['answer'], '_PROTNAME[0]')

    def test_source_and_request_not_modified(self):
        path = service.DIRECTORY / service.PREPARED
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        request = service.LogfileAnswerRequest(alarm_scope='61352_or_61353')
        original = deepcopy(request.model_dump())
        result = service.answer_logfile_parameter(request)
        self.assertEqual(request.model_dump(), original)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertEqual(result['prepared_sha256'], before)


if __name__ == '__main__':
    unittest.main()
