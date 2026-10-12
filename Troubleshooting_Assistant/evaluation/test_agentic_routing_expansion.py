import ast
from copy import deepcopy
from pathlib import Path
import unittest

from app.services.agentic.contracts import AgentState
from app.services.agentic.routing_policy import (
    _TOOL_ARGUMENT_FIELDS, choose_deterministic_ready_tool,
)
from app.services.agentic.tool_registry import build_default_tool_registry


class RoutingExpansionTests(unittest.TestCase):
    def setUp(self):
        self.tools = build_default_tool_registry().list_specs()

    def route(self, intent, facts=None, **kwargs):
        state = AgentState(
            user_message="Explicit development request",
            detected_intent=intent, known_facts=facts or {}, **kwargs,
        )
        return choose_deterministic_ready_tool(state, self.tools)

    def test_abb_preserves_reports_and_deferrals(self):
        facts = {
            "requested_information": "review_reports",
            "overload_reported": False, "low_voltage_reported": None,
            "open_circuit_reported": True,
            "deferred_fact_ids": ["open_phase_reported"],
        }
        decision = self.route("request_abb_stall_assistance", facts)
        self.assertEqual(decision.tool_name, "abb_stall")
        self.assertEqual(decision.tool_arguments, facts)
        self.assertIs(decision.tool_arguments["overload_reported"], False)

    def test_licensing_preserves_false_zero_and_alarm(self):
        facts = {
            "options_activated": True, "license_key_set": False,
            "reported_alarm_number": "8081", "clarifications_used": 0,
            "deferred_fact_ids": [],
        }
        decision = self.route("compare_siemens_licensing", facts)
        self.assertEqual(decision.tool_name, "siemens_licensing")
        self.assertEqual(decision.tool_arguments, facts)
        self.assertIs(decision.tool_arguments["license_key_set"], False)
        self.assertIs(type(decision.tool_arguments["clarifications_used"]), int)

    def test_all_abb_information_requests_are_preserved(self):
        for requested in ("list_possible_causes", "review_reports", "identify_cause"):
            with self.subTest(requested=requested):
                facts = {"requested_information": requested}
                decision = self.route("request_abb_stall_assistance", facts)
                self.assertEqual(decision.tool_arguments, facts)

    def test_missing_abb_selection_does_not_route(self):
        self.assertIsNone(self.route("request_abb_stall_assistance"))

    def test_missing_logfile_scope_does_not_route(self):
        self.assertIsNone(self.route("request_logfile_parameter"))

    def test_empty_licensing_request_invents_no_reports(self):
        decision = self.route("compare_siemens_licensing")
        self.assertEqual(decision.tool_arguments, {})

    def test_free_text_does_not_select_a_tool(self):
        state = AgentState(user_message="ABB Motor stalls; overload is present.")
        self.assertIsNone(choose_deterministic_ready_tool(state, self.tools))

    def test_unrelated_facts_are_not_tool_arguments(self):
        decision = self.route("request_abb_stall_assistance", {
            "requested_information": "list_possible_causes",
            "alarm_scope": "61352", "execute_repair": True,
        })
        self.assertEqual(decision.tool_arguments, {
            "requested_information": "list_possible_causes",
        })

    def test_decision_does_not_alias_or_mutate_state(self):
        state = AgentState(
            user_message="Review reports", detected_intent="request_abb_stall_assistance",
            known_facts={"requested_information": "review_reports",
                         "deferred_fact_ids": ["open_phase_reported"]},
        )
        before = deepcopy(state.model_dump())
        decision = choose_deterministic_ready_tool(state, self.tools)
        decision.tool_arguments["deferred_fact_ids"].append("low_voltage_reported")
        self.assertEqual(state.model_dump(), before)

    def test_unregistered_tool_is_not_selected(self):
        self.tools = [tool for tool in self.tools if tool.name != "abb_stall"]
        self.assertIsNone(self.route("request_abb_stall_assistance", {
            "requested_information": "list_possible_causes",
        }))

    def test_each_previous_tool_is_not_automatically_repeated(self):
        cases = [
            ("request_abb_stall_assistance", "abb_stall",
             {"requested_information": "review_reports"}),
            ("compare_siemens_licensing", "siemens_licensing", {}),
        ]
        for intent, tool, facts in cases:
            with self.subTest(tool=tool):
                self.assertIsNone(self.route(intent, facts, last_tool_result={"tool_name": tool}))

    def test_argument_fields_match_existing_dispatcher(self):
        path = Path(__file__).resolve().parents[1] / "app/services/agentic/dispatcher.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        node = next(node for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "_ALLOWED_ARGUMENTS"
                            for t in node.targets))
        dispatcher_fields = ast.literal_eval(node.value)
        for tool, fields in _TOOL_ARGUMENT_FIELDS.items():
            self.assertEqual(fields, dispatcher_fields[tool], tool)


class RoutingSourceIntegrationTests(unittest.TestCase):
    def test_complete_requests_finish_without_planner_calls(self):
        from app.services.agentic.dispatcher import ProtectedToolDispatcher
        from app.services.agentic.loop import run_agent_loop
        from app.services.agentic.model_adapter import AgentModelAdapter

        class NoPlanner(AgentModelAdapter):
            calls = 0

            @property
            def provider_name(self):
                return "test_no_planner"

            def decide(self, state, allowed_tools):
                self.calls += 1
                raise AssertionError("A complete test request unexpectedly called the planner.")

        cases = [
            ("ABB source list", "request_abb_stall_assistance", "abb_stall",
             {"requested_information": "list_possible_causes"},
             "source_information", "source_record_count", 5),
            ("Siemens 8080", "compare_siemens_licensing", "siemens_licensing",
             {"options_activated": True, "license_key_set": False},
             "description_supported", "selected_description_alarm", "8080"),
            ("Siemens 8081", "compare_siemens_licensing", "siemens_licensing",
             {"options_activated": True, "license_key_set": True,
              "entered_key_covers_activated_options": False},
             "description_supported", "selected_description_alarm", "8081"),
            ("Siemens logfile", "request_logfile_parameter", "siemens_logfile",
             {"alarm_scope": "61352_or_61353"},
             "answer_supported", "answer", "_PROTNAME[0]"),
        ]
        registry = build_default_tool_registry()
        dispatcher = ProtectedToolDispatcher(registry)
        for label, intent, tool, facts, status, field, value in cases:
            with self.subTest(case=label):
                model = NoPlanner()
                state = AgentState(user_message=label, detected_intent=intent, known_facts=facts)
                result = run_agent_loop(state, model, registry, dispatcher, max_steps=3)
                self.assertEqual(model.calls, 0)
                self.assertEqual(result.status, "completed")
                self.assertEqual(result.final_decision.action, "return_information")
                self.assertEqual(len(result.observations), 1)
                self.assertEqual(result.observations[0].tool_name, tool)
                self.assertEqual(result.decisions[0].tool_arguments, facts)
                body = result.observations[0].result["result"]
                self.assertEqual(body["status"], status)
                self.assertEqual(body[field], value)
                self.assertIs(body["diagnosis_confirmed"], False)
                self.assertIs(body["approved_for_automatic_execution"], False)
                print(f"\nPASS {label}: {value}; planner calls=0")

    def test_reports_deferrals_and_limits_reach_the_source_policy(self):
        from app.services.agentic.completion_policy import assess_terminal_evidence
        from app.services.agentic.dispatcher import ProtectedToolDispatcher

        fields = ["open_phase_reported", "wrong_application_reported", "overload_reported",
                  "low_voltage_reported", "open_circuit_reported"]
        cases = [
            ("ABB reports denied", "request_abb_stall_assistance",
             {"requested_information": "review_reports", **{key: False for key in fields}},
             "reports_complete"),
            ("ABB all deferred", "request_abb_stall_assistance",
             {"requested_information": "review_reports", "deferred_fact_ids": fields},
             "insufficient_information"),
            ("Licensing budget used", "compare_siemens_licensing",
             {"options_activated": True, "clarifications_used": 2}, "insufficient_evidence"),
            ("Licensing conflicting alarm", "compare_siemens_licensing",
             {"options_activated": True, "license_key_set": False,
              "reported_alarm_number": "8081"}, "conflicting_input"),
        ]
        registry = build_default_tool_registry()
        dispatcher = ProtectedToolDispatcher(registry)
        for label, intent, facts, status in cases:
            with self.subTest(case=label):
                state = AgentState(user_message=label, detected_intent=intent, known_facts=facts)
                decision = choose_deterministic_ready_tool(state, registry.list_specs())
                self.assertEqual(decision.tool_arguments, facts)
                observation = dispatcher.dispatch(decision)
                body = observation.result["result"]
                self.assertEqual(body["status"], status)
                self.assertFalse(assess_terminal_evidence(observation).terminal_supported)
                self.assertIs(body["diagnosis_confirmed"], False)
                self.assertIs(body["approved_for_automatic_execution"], False)
                print(f"\nPASS {label}: {status}")


if __name__ == "__main__":
    unittest.main()
