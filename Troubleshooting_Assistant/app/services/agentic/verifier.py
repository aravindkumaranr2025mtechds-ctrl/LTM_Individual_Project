"""Deterministic verifier for bounded Agentic AI execution."""

from typing import Any

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.dispatcher import (
    ToolObservation,
)


_SAFETY_FIELDS = {
    "diagnosis_confirmed",
    "approved_for_automatic_execution",
    "automatic_execution",
}


def _verify_safety_tree(
    value: Any,
    path="root",
):
    """Reject unsafe execution/diagnosis flags anywhere in a result tree."""

    if isinstance(
        value,
        dict,
    ):

        for key, child in value.items():

            child_path = (
                f"{path}.{key}"
            )

            if (
                key in _SAFETY_FIELDS
                and child is not False
            ):
                raise PermissionError(
                    "Unsafe safety flag detected at "
                    f"{child_path}: {child!r}"
                )

            _verify_safety_tree(
                child,
                child_path,
            )

    elif isinstance(
        value,
        list,
    ):

        for index, child in enumerate(
            value
        ):

            _verify_safety_tree(
                child,
                f"{path}[{index}]",
            )


def verify_tool_observation(
    observation: ToolObservation,
):
    """Verify a protected tool observation before giving it back to the agent."""

    if (
        observation.diagnosis_confirmed
        is not False
    ):
        raise PermissionError(
            "Tool observation attempted "
            "to confirm a diagnosis."
        )

    if (
        observation.
        approved_for_automatic_execution
        is not False
    ):
        raise PermissionError(
            "Tool observation attempted "
            "to permit automatic execution."
        )

    if not isinstance(
        observation.result,
        dict,
    ):
        raise TypeError(
            "Tool observation result must be an object."
        )

    _verify_safety_tree(
        observation.result,
        path="tool_result",
    )

    return True


def verify_return_information(
    state: AgentState,
    decision: AgentDecision,
):
    """Require evidence/observation before the agent may finish with information."""

    if (
        decision.action
        != "return_information"
    ):
        raise ValueError(
            "verify_return_information requires "
            "a return_information decision."
        )

    has_tool_observation = (
        state.last_tool_result
        is not None
    )

    has_explicit_evidence = bool(
        state.evidence
    )

    if not (
        has_tool_observation
        or has_explicit_evidence
    ):
        raise PermissionError(
            "Agent attempted to return information "
            "without a protected tool observation "
            "or explicit evidence."
        )

    if (
        state.last_tool_result
        is not None
    ):
        _verify_safety_tree(
            state.last_tool_result,
            path="last_tool_result",
        )

    if state.evidence:
        _verify_safety_tree(
            state.evidence,
            path="evidence",
        )

    return True
