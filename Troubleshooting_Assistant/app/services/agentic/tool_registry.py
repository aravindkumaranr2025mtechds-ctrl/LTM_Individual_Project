"""Protected tool registry for the bounded agent.

At this structural stage the registry exposes metadata only.
Tool execution is deliberately disabled.
"""

from copy import deepcopy
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.services.agentic.contracts import (
    AgentToolName,
)


class ToolSpec(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    name: AgentToolName

    description: str

    source_service: str

    required_explicit_fields: list[
        str
    ] = Field(
        default_factory=list
    )

    safety_notes: list[
        str
    ] = Field(
        default_factory=list
    )

    execution_enabled: Literal[
        False
    ] = False


class ToolRegistry:
    """Allow-list of tools visible to the agent planner."""

    def __init__(
        self,
        specs: list[ToolSpec],
    ):
        self._specs = {
            spec.name: deepcopy(spec)
            for spec in specs
        }

    def names(self):
        return list(
            self._specs
        )

    def contains(
        self,
        name,
    ):
        return name in self._specs

    def get(
        self,
        name,
    ):
        if name not in self._specs:
            raise KeyError(
                f"Tool is not registered: {name}"
            )

        return deepcopy(
            self._specs[name]
        )

    def list_specs(self):
        return [
            deepcopy(spec)
            for spec in self._specs.values()
        ]

    def execute(
        self,
        name,
        arguments,
    ):
        raise PermissionError(
            "Agent tool execution is disabled at the "
            "structural integration stage."
        )


def build_default_tool_registry():
    """Return the exact initial protected tool allow-list."""

    return ToolRegistry(
        [
            ToolSpec(
                name=
                    "troubleshooting_guidance",

                description=(
                    "Describe the structured information "
                    "required by supported troubleshooting modes."
                ),

                source_service=(
                    "app.services."
                    "troubleshooting_input_guidance"
                ),

                safety_notes=[
                    (
                        "Provides guidance only and does "
                        "not establish diagnostic facts."
                    ),
                ],
            ),

            ToolSpec(
                name=
                    "troubleshooting_questions",

                description=(
                    "Return human-friendly questions for "
                    "one explicit troubleshooting mode."
                ),

                source_service=(
                    "app.services."
                    "troubleshooting_question_builder"
                ),

                required_explicit_fields=[
                    "mode",
                ],

                safety_notes=[
                    (
                        "Questions must not be treated as "
                        "observed facts."
                    ),
                ],
            ),

            ToolSpec(
                name=
                    "abb_stall",

                description=(
                    "Use the validated ABB Motor stalls "
                    "assistance policy."
                ),

                source_service=(
                    "app.services."
                    "abb_stall_assistance"
                ),

                required_explicit_fields=[
                    "requested_information",
                ],

                safety_notes=[
                    (
                        "Possible causes do not establish "
                        "a unique diagnosis."
                    ),
                    (
                        "Automatic execution is prohibited."
                    ),
                ],
            ),

            ToolSpec(
                name=
                    "siemens_licensing",

                description=(
                    "Use the bounded Siemens 8080/8081 "
                    "licensing comparison policy."
                ),

                source_service=(
                    "app.services."
                    "siemens_license_assistance"
                ),

                safety_notes=[
                    (
                        "Alarm number must not be inferred "
                        "from symptom text."
                    ),
                    (
                        "Description support is not a "
                        "confirmed diagnosis."
                    ),
                ],
            ),

            ToolSpec(
                name=
                    "siemens_logfile",

                description=(
                    "Use the validated Siemens logfile "
                    "parameter evidence policy."
                ),

                source_service=(
                    "app.services."
                    "siemens_logfile_answer"
                ),

                required_explicit_fields=[
                    "alarm_scope",
                ],

                safety_notes=[
                    (
                        "alarm_scope must be explicitly "
                        "supplied by the caller."
                    ),
                    (
                        "The agent may never guess alarm_scope."
                    ),
                ],
            ),
        ]
    )


def build_enterprise_evidence_tool_spec():
    """
    Return the opt-in enterprise evidence-search capability.

    It is deliberately excluded from the historical default
    troubleshooting registry.
    """

    return ToolSpec(
        name=
            "enterprise_evidence_search",

        description=(
            "Search eligible registered industrial "
            "technical evidence through trusted "
            "enterprise retrieval."
        ),

        source_service=(
            "app.services.retrieval_service."
            "retrieve_enterprise_sections_configured"
        ),

        required_explicit_fields=[
            "query",
        ],

        safety_notes=[
            (
                "Similarity retrieval does not establish "
                "a diagnosis."
            ),
            (
                "The caller cannot select backend, "
                "storage path, collection, vector "
                "artifact, or access level."
            ),
            (
                "Automatic execution is prohibited."
            ),
        ],
    )
