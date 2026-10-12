"""Bounded multi-step Agentic AI loop.

Flow:
AgentState
 -> planner
 -> controller
 -> protected dispatcher
 -> verified observation
 -> updated AgentState
 -> re-plan

The loop is intentionally bounded and does not permit autonomous
physical execution.
"""

from copy import deepcopy
import json
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.services.agentic.completion_policy import (
    assess_terminal_evidence,
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

from app.services.agentic.routing_policy import (
    choose_deterministic_ready_tool,
)

from app.services.agentic.model_adapter import (
    AgentModelAdapter,
)

from app.services.agentic.tool_registry import (
    ToolRegistry,
)

from app.services.agentic.verifier import (
    verify_return_information,
    verify_tool_observation,
)


AgentLoopStatus = Literal[
    "completed",
    "needs_user_input",
    "inspection_suggested",
    "abstained",
    "guard_blocked",
    "max_steps_exceeded",
]


class AgentLoopResult(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    status: AgentLoopStatus

    state: AgentState

    decisions: list[
        AgentDecision
    ] = Field(
        default_factory=list
    )

    observations: list[
        ToolObservation
    ] = Field(
        default_factory=list
    )

    final_decision: (
        AgentDecision
        | None
    ) = None

    blocked_reason: str | None = None

    diagnosis_confirmed: Literal[
        False
    ] = False

    approved_for_automatic_execution: Literal[
        False
    ] = False


def _tool_call_signature(
    decision: AgentDecision,
):
    return json.dumps(
        {
            "tool_name":
                decision.tool_name,

            "tool_arguments":
                decision.tool_arguments,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def run_agent_loop(
    initial_state: AgentState,
    model: AgentModelAdapter,
    registry: ToolRegistry,
    dispatcher: ProtectedToolDispatcher,
    max_steps=4,
):
    """Run a bounded troubleshooting agent loop."""

    if not isinstance(
        max_steps,
        int,
    ):
        raise TypeError(
            "max_steps must be an integer."
        )

    if not (
        1 <= max_steps <= 10
    ):
        raise ValueError(
            "max_steps must be between 1 and 10."
        )

    state = initial_state.model_copy(
        deep=True
    )

    decisions = []
    observations = []

    seen_tool_calls = set()

    for _ in range(
        max_steps
    ):

        if state.step_count >= 20:

            return AgentLoopResult(
                status=
                    "max_steps_exceeded",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=(
                    decisions[-1]
                    if decisions
                    else None
                ),

                blocked_reason=(
                    "AgentState reached the "
                    "global step-count limit."
                ),
            )

        try:

            decision = (
                choose_deterministic_ready_tool(
                    state,
                    registry.list_specs(),
                )
            )

            if decision is None:

                decision = (
                    plan_next_action(
                        state,
                        model,
                        registry,
                    )
                )

        except PermissionError as error:

            return AgentLoopResult(
                status=
                    "guard_blocked",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                blocked_reason=
                    str(error),
            )


        decisions.append(
            decision
        )

        state.step_count += 1

        if (
            decision.action
            == "ask_clarification"
        ):

            return AgentLoopResult(
                status=
                    "needs_user_input",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=
                    decision,
            )

        if (
            decision.action
            == "suggest_inspection"
        ):

            return AgentLoopResult(
                status=
                    "inspection_suggested",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=
                    decision,
            )

        if (
            decision.action
            == "abstain"
        ):

            return AgentLoopResult(
                status=
                    "abstained",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=
                    decision,
            )

        if (
            decision.action
            == "return_information"
        ):

            try:

                verify_return_information(
                    state,
                    decision,
                )

            except PermissionError as error:

                return AgentLoopResult(
                    status=
                        "guard_blocked",

                    state=
                        state,

                    decisions=
                        decisions,

                    observations=
                        observations,

                    final_decision=
                        decision,

                    blocked_reason=
                        str(error),
                )

            return AgentLoopResult(
                status=
                    "completed",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=
                    decision,
            )

        if (
            decision.action
            != "call_tool"
        ):

            return AgentLoopResult(
                status=
                    "guard_blocked",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=
                    decision,

                blocked_reason=(
                    "Unsupported AgentDecision action."
                ),
            )

        signature = (
            _tool_call_signature(
                decision
            )
        )

        if (
            signature
            in seen_tool_calls
        ):

            return AgentLoopResult(
                status=
                    "guard_blocked",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=
                    decision,

                blocked_reason=(
                    "Agent attempted to repeat "
                    "the exact same protected tool call."
                ),
            )

        seen_tool_calls.add(
            signature
        )

        try:

            observation = (
                dispatcher.dispatch(
                    decision
                )
            )

            verify_tool_observation(
                observation
            )

        except (
            PermissionError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:

            return AgentLoopResult(
                status=
                    "guard_blocked",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=
                    decision,

                blocked_reason=
                    str(error),
            )

        observations.append(
            observation
        )

        state.last_tool_result = {
            "tool_name":
                observation.tool_name,

            "result":
                deepcopy(
                    observation.result
                ),

            "diagnosis_confirmed":
                False,

            "approved_for_automatic_execution":
                False,
        }

        terminal_assessment = (
            assess_terminal_evidence(
                observation
            )
        )

        if (
            terminal_assessment.
            terminal_supported
        ):

            final_decision = (
                AgentDecision(
                    action=
                        "return_information",

                    reason=(
                        "Deterministic terminal-evidence "
                        "gate accepted verified status "
                        f"{terminal_assessment.result_status}."
                    ),
                )
            )

            verify_return_information(
                state,
                final_decision,
            )

            decisions.append(
                final_decision
            )

            return AgentLoopResult(
                status=
                    "completed",

                state=
                    state,

                decisions=
                    decisions,

                observations=
                    observations,

                final_decision=
                    final_decision,
            )


    return AgentLoopResult(
        status=
            "max_steps_exceeded",

        state=
            state,

        decisions=
            decisions,

        observations=
            observations,

        final_decision=(
            decisions[-1]
            if decisions
            else None
        ),

        blocked_reason=(
            "Agent reached the configured "
            "maximum planning steps."
        ),
    )
