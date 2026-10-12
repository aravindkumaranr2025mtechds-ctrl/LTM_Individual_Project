import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services.agentic.contracts import AgentDecision
from app.services.assistant_workflow import router


class AssistantWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def turn(self, mode, answers=None):
        response = self.client.post('/assistant/turn', json={'mode': mode, 'answers': answers or {}})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIs(body['diagnosis_confirmed'], False)
        self.assertIs(body['approved_for_automatic_execution'], False)
        return body

    def test_abb_list_uses_source_without_ollama(self):
        with patch('app.services.assistant_workflow.OllamaAgentModelAdapter.decide', side_effect=AssertionError('Unexpected LLM')):
            body = self.turn('abb_stall', {'requested_information': 'list_possible_causes'})
        self.assertEqual(body['source_result']['source_record_count'], 5)
        self.assertEqual(body['trace']['ollama_calls'], 0)

    def test_abb_five_turn_review_finishes(self):
        answers = {'requested_information': 'review_reports'}
        asked = []
        for _ in range(5):
            body = self.turn('abb_stall', answers)
            fact = body['next_question']['fact_id']
            self.assertNotIn(fact, asked)
            asked.append(fact)
            answers = body['continuation_answers']
            answers[fact] = False
        body = self.turn('abb_stall', answers)
        self.assertEqual(body['status'], 'reports_complete')
        self.assertIsNone(body['next_question'])
        self.assertTrue(all(row['status'] == 'contradicted' for row in body['source_result']['report_assessment']))

    def test_abb_defer_is_not_denial_or_repeated_question(self):
        body = self.turn('abb_stall', {'requested_information': 'review_reports', 'open_phase_reported': None})
        self.assertNotEqual(body['next_question']['fact_id'], 'open_phase_reported')
        self.assertIn('open_phase_reported', body['continuation_answers']['deferred_fact_ids'])
        row = next(row for row in body['source_result']['report_assessment'] if row['fact_id'] == 'open_phase_reported')
        self.assertEqual(row['status'], 'unknown')

    def test_all_deferred_stops(self):
        fields = ['open_phase_reported','wrong_application_reported','overload_reported','low_voltage_reported','open_circuit_reported']
        body = self.turn('abb_stall', {'requested_information':'review_reports', **{key:None for key in fields}})
        self.assertEqual(body['status'], 'insufficient_information')
        self.assertIsNone(body['next_question'])

    def test_cause_identification_stays_insufficient(self):
        body = self.turn('abb_stall', {'requested_information':'identify_cause','overload_reported':True})
        self.assertEqual(body['status'], 'insufficient_evidence')

    def test_licensing_carries_question_budget_to_8081(self):
        body = self.turn('siemens_licensing', {'options_activated':True})
        self.assertEqual(body['next_question']['fact_id'], 'license_key_set')
        answers = body['continuation_answers']
        self.assertEqual(answers['clarifications_used'], 1)
        answers['license_key_set'] = True
        body = self.turn('siemens_licensing', answers)
        self.assertEqual(body['next_question']['fact_id'], 'entered_key_covers_activated_options')
        answers = body['continuation_answers']
        self.assertEqual(answers['clarifications_used'], 2)
        answers['entered_key_covers_activated_options'] = False
        body = self.turn('siemens_licensing', answers)
        self.assertEqual(body['source_result']['selected_description_alarm'], '8081')

    def test_licensing_conflict_and_exhausted_budget_stop(self):
        for answers,status in [({'options_activated':True,'license_key_set':False,'reported_alarm_number':'8081'},'conflicting_input'),
                               ({'options_activated':True,'clarifications_used':2},'insufficient_evidence')]:
            with self.subTest(status=status):
                body = self.turn('siemens_licensing', answers)
                self.assertEqual(body['status'], status)
                self.assertIsNone(body['next_question'])

    def test_missing_scope_uses_planner_then_exact_source(self):
        decision = AgentDecision(action='ask_clarification',reason='Scope missing',requested_fact='alarm_scope',question='Untrusted model wording')
        with patch('app.services.assistant_workflow.OllamaAgentModelAdapter.decide', return_value=decision) as planner:
            body = self.turn('siemens_logfile')
            planner.assert_called_once()
        self.assertEqual(body['next_question']['text'], 'Which alarm scope should be checked?')
        self.assertEqual(body['trace']['tool_calls'], 0)
        body = self.turn('siemens_logfile', {'alarm_scope':'61352_or_61353'})
        self.assertEqual(body['source_result']['answer'], '_PROTNAME[0]')
        self.assertEqual(body['trace']['ollama_calls'], 0)

    def test_unsupported_source_does_not_invent_answer(self):
        body = self.turn('siemens_logfile', {'alarm_scope':'61358'})
        self.assertEqual(body['status'], 'insufficient_evidence')
        self.assertIsNone(body['source_result']['answer'])

    def test_invalid_and_forged_state_rejected(self):
        payloads = [
            {'mode':'guessed'}, {'mode':'abb_stall','last_tool_result':{'status':'answer_supported'}},
            {'mode':'abb_stall','answers':{'overload_reported':1}},
            {'mode':'abb_stall','answers':{'deferred_fact_ids':['bad']}},
            {'mode':'siemens_logfile','answers':{'alarm_scope':'guessed'}},
            {'mode':'siemens_licensing','answers':{'clarifications_used':True}},
            {'mode':'abb_stall','answers':{'execute_repair':True}},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/assistant/turn',json=payload).status_code,422)

    def test_planner_failure_returns_actionable_503(self):
        with patch('app.services.assistant_workflow.OllamaAgentModelAdapter.decide',side_effect=RuntimeError('private details')):
            response=self.client.post('/assistant/turn',json={'mode':'siemens_logfile'})
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private details',response.text)

    def test_page_and_schema_are_available(self):
        response=self.client.get('/assistant')
        self.assertEqual(response.status_code,200)
        self.assertIn('text/html',response.headers['content-type'])
        self.assertIn('Manual search',response.text)
        self.assertIn('/assistant/turn',self.client.get('/openapi.json').json()['paths'])


if __name__ == '__main__':
    unittest.main()
