"""Deterministic planning context for the bounded troubleshooting agent.

The LLM does not decide whether required explicit facts exist.
This module calculates tool readiness from AgentState and ToolSpec before
planning begins.
"""

from copy import deepcopy

from app.services.agentic.contracts import (
    AgentState,
)

from app.services.agentic.tool_registry import (
    ToolSpec,
)


def build_tool_readiness(
    state: AgentState,
    allowed_tools: list[ToolSpec],
):
    """Return deterministic readiness metadata for each protected tool."""

    readiness = []

    for spec in allowed_tools:

        missing = [
            field
            for field
            in spec.required_explicit_fields
            if field
            not in state.known_facts
        ]

        explicit_arguments = {
            field:
                deepcopy(
                    state.known_facts[field]
                )
            for field
            in spec.required_explicit_fields
            if field
            in state.known_facts
        }

        readiness.append(
            {
                "tool_name":
                    spec.name,

                "ready_for_call":
                    len(missing) == 0,

                "required_explicit_fields":
                    list(
                        spec.required_explicit_fields
                    ),

                "missing_required_fields":
                    missing,

                "explicit_arguments":
                    explicit_arguments,
            }
        )

    return readiness
