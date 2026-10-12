"""Execute one bounded agent planning step.

This does not implement a full autonomous loop yet.
One model decision is obtained, validated and, when permitted,
one protected tool may be executed.
"""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
)

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.controller import (
    plan_next_action,
)

from app.services.agentic.dispatcher import (
    ProtectedToolDispatcher,
    ToolObservation,
)

from app.services.agentic.model_adapter import (
    AgentModelAdapter,
)

from app.services.agentic.tool_registry import (
    ToolRegistry,
)


class AgentStepResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    status: Literal[
        "decision_only",
        "tool_observed",
    ]

    decision: AgentDecision

    observation: (
        ToolObservation
        | None
    ) = None

    diagnosis_confirmed: Literal[
        False
    ] = False

    approved_for_automatic_execution: Literal[
        False
    ] = False


def run_agent_step(
    state: AgentState,
    model: AgentModelAdapter,
    registry: ToolRegistry,
    dispatcher: ProtectedToolDispatcher,
) -> AgentStepResult:
    """Execute exactly one bounded agent step."""

    decision = plan_next_action(
        state,
        model,
        registry,
    )

    if (
        decision.action
        != "call_tool"
    ):
        return AgentStepResult(
            status=
                "decision_only",

            decision=
                decision,
        )

    observation = (
        dispatcher.dispatch(
            decision
        )
    )

    return AgentStepResult(
        status=
            "tool_observed",

        decision=
            decision,

        observation=
            observation,
    )
