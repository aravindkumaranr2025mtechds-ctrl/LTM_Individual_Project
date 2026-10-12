"""Typed contracts for the bounded industrial troubleshooting agent."""

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


AgentAction = Literal[
    "ask_clarification",
    "suggest_inspection",
    "call_tool",
    "return_information",
    "abstain",
]


AgentToolName = Literal[
    "troubleshooting_guidance",
    "troubleshooting_questions",
    "abb_stall",
    "siemens_licensing",
    "siemens_logfile",
    "enterprise_evidence_search",
]


class AgentState(BaseModel):
    """Caller-carried state visible to the agent planner."""

    model_config = ConfigDict(
        extra="forbid"
    )

    user_message: str

    conversation_context: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    detected_intent: str | None = None

    manufacturer_candidate: str | None = None

    requested_goal: str | None = None

    known_facts: dict[
        str,
        Any
    ] = Field(
        default_factory=dict
    )

    unknown_facts: list[str] = Field(
        default_factory=list
    )

    contradicted_facts: list[str] = Field(
        default_factory=list
    )

    conflicting_facts: list[str] = Field(
        default_factory=list
    )

    evidence: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    citations: list[str] = Field(
        default_factory=list
    )

    last_tool_result: dict[
        str,
        Any
    ] | None = None

    step_count: int = Field(
        default=0,
        ge=0,
        le=20,
    )

    diagnosis_confirmed: Literal[
        False
    ] = False

    approved_for_automatic_execution: Literal[
        False
    ] = False


class AgentDecision(BaseModel):
    """One bounded action selected by a model adapter."""

    model_config = ConfigDict(
        extra="forbid"
    )

    action: AgentAction

    reason: str = Field(
        min_length=1,
        max_length=2000,
    )

    tool_name: AgentToolName | None = None

    tool_arguments: dict[
        str,
        Any
    ] = Field(
        default_factory=dict
    )

    requested_fact: str | None = None

    question: str | None = None

    suggestion: str | None = None

    @model_validator(
        mode="after"
    )
    def validate_action_contract(self):
        if self.action == "call_tool":
            if self.tool_name is None:
                raise ValueError(
                    "call_tool requires tool_name."
                )

        else:
            if self.tool_name is not None:
                raise ValueError(
                    "Only call_tool may specify tool_name."
                )

            if self.tool_arguments:
                raise ValueError(
                    "Only call_tool may contain tool_arguments."
                )

        if (
            self.action
            == "ask_clarification"
            and not self.question
        ):
            raise ValueError(
                "ask_clarification requires question."
            )

        if (
            self.action
            == "suggest_inspection"
        ):
            if not self.requested_fact:
                raise ValueError(
                    "suggest_inspection requires requested_fact."
                )

            if not self.suggestion:
                raise ValueError(
                    "suggest_inspection requires suggestion."
                )

        return self
