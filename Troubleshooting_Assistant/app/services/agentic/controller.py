"""Planning-only bounded agent controller.

No tool is executed here. This layer only obtains one structured
decision from the configured model adapter and validates it against
the protected tool allow-list.
"""

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.model_adapter import (
    AgentModelAdapter,
)

from app.services.agentic.tool_registry import (
    ToolRegistry,
)


def _validate_grounded_arguments(
    state: AgentState,
    decision: AgentDecision,
    registry: ToolRegistry,
):
    """Prevent the model from inventing executable tool arguments.

    Every argument supplied to a protected tool must already exist in
    caller-carried known_facts with exactly the same value.
    """

    if decision.action != "call_tool":
        return

    if decision.tool_name is None:
        raise PermissionError(
            "A tool call requires an explicit registered tool."
        )

    spec = registry.get(
        decision.tool_name
    )

    arguments = decision.tool_arguments

    for field in spec.required_explicit_fields:
        if field not in arguments:
            raise PermissionError(
                f"Tool {decision.tool_name} requires explicit field: {field}"
            )

    for key, value in arguments.items():

        if key not in state.known_facts:
            raise PermissionError(
                "Agent attempted to supply a tool argument "
                f"that is not an explicit known fact: {key}"
            )

        if state.known_facts[key] != value:
            raise PermissionError(
                "Agent attempted to change the explicit value "
                f"of known fact: {key}"
            )


def _validate_information_request(
    state: AgentState,
    decision: AgentDecision,
):
    """Reject redundant requests for facts already explicitly known."""

    if decision.action not in {
        "ask_clarification",
        "suggest_inspection",
    }:
        return

    requested_fact = (
        decision.requested_fact
    )

    if requested_fact is None:
        return

    if requested_fact in state.known_facts:
        raise PermissionError(
            "Agent requested information that is "
            "already an explicit known fact: "
            f"{requested_fact}"
        )


def plan_next_action(
    state: AgentState,
    model: AgentModelAdapter,
    registry: ToolRegistry,
) -> AgentDecision:
    """Request and validate exactly one bounded planning decision."""

    planning_state = state.model_copy(
        deep=True
    )

    decision = model.decide(
        planning_state,
        registry.list_specs(),
    )

    if not isinstance(
        decision,
        AgentDecision,
    ):
        raise TypeError(
            "Model adapter must return AgentDecision."
        )

    # Clarification/inspection requests must never ask for a fact
    # already carried explicitly in AgentState.known_facts.
    _validate_information_request(
        state,
        decision,
    )

    if (
        decision.action
        == "call_tool"
    ):

        if not registry.contains(
            decision.tool_name
        ):
            raise PermissionError(
                "Agent selected a tool outside "
                "the protected registry."
            )

        spec = registry.get(
            decision.tool_name
        )

        # Every executable argument must already be an exact
        # caller-carried known fact.
        _validate_grounded_arguments(
            state,
            decision,
            registry,
        )

        if spec.execution_enabled:
            raise RuntimeError(
                "Structural-stage tools must not "
                "be executable."
            )

    return decision

