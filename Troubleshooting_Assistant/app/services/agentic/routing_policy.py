"""Route explicit supported intents using caller-supplied arguments."""

from copy import deepcopy

from app.services.agentic.contracts import AgentDecision, AgentState
from app.services.agentic.planning_context import build_tool_readiness
from app.services.agentic.tool_registry import ToolSpec


INTENT_TOOL_POLICY = {
    "request_logfile_parameter": "siemens_logfile",
    "request_abb_stall_assistance": "abb_stall",
    "compare_siemens_licensing": "siemens_licensing",
}

# Keep these fields aligned with the protected dispatcher's allow-list.
# Copy optional values too: False, None, zero, and deferrals are meaningful.
_TOOL_ARGUMENT_FIELDS = {
    "siemens_logfile": {"alarm_scope"},
    "abb_stall": {
        "requested_information", "open_phase_reported",
        "wrong_application_reported", "overload_reported",
        "low_voltage_reported", "open_circuit_reported", "deferred_fact_ids",
    },
    "siemens_licensing": {
        "options_activated", "license_key_set",
        "entered_key_covers_activated_options", "reported_alarm_number",
        "clarifications_used", "deferred_fact_ids",
    },
}


def choose_deterministic_ready_tool(
    state: AgentState, allowed_tools: list[ToolSpec],
):
    """Choose one registered tool without interpreting free-text reports.

    Readiness means the tool can accept a request; it does not imply that
    observations are complete or that the source can answer the request.
    Argument types and values remain subject to dispatcher validation.
    """
    target_tool = INTENT_TOOL_POLICY.get(state.detected_intent)
    if target_tool is None:
        return None

    if isinstance(state.last_tool_result, dict):
        if state.last_tool_result.get("tool_name") == target_tool:
            return None

    readiness = build_tool_readiness(state, allowed_tools)
    target = next(
        (item for item in readiness if item["tool_name"] == target_tool), None,
    )
    if target is None or not target["ready_for_call"]:
        return None

    allowed = _TOOL_ARGUMENT_FIELDS[target_tool]
    if set(target["required_explicit_fields"]) - allowed:
        raise PermissionError("Routing fields no longer match the tool contract.")

    arguments = {
        key: deepcopy(value)
        for key, value in state.known_facts.items()
        if key in allowed
    }
    return AgentDecision(
        action="call_tool",
        reason=(
            "An explicit intent selects a registered tool with its required "
            "inputs. All supplied supported arguments are copied unchanged."
        ),
        tool_name=target_tool,
        tool_arguments=arguments,
    )
