"""Normalize detailed troubleshooting states into a stable outcome.

The detailed workflow status and agent actions remain unchanged.

This module exposes only the high-level decision contract:

ANSWER / CLARIFY / ABSTAIN / ESCALATE.

It performs no diagnosis and cannot approve automatic execution.
"""

from __future__ import annotations

from typing import (
    Any,
    Literal,
)

from pydantic import (
    BaseModel,
    ConfigDict,
)


FinalDecision = Literal[
    "ANSWER",
    "CLARIFY",
    "ABSTAIN",
    "ESCALATE",
]


class FinalOutcome(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    schema_version: Literal[
        "final_outcome_v1"
    ] = "final_outcome_v1"

    decision: FinalDecision

    reason_code: str

    source_status: str | None = None

    terminal_action: str | None = None

    diagnosis_confirmed: Literal[
        False
    ] = False

    approved_for_automatic_execution: Literal[
        False
    ] = False


_ANSWER_STATUSES = {
    "source_information",
    "reports_complete",
    "description_supported",
    "answer_supported",
    "evidence_retrieved",
}


_CLARIFY_STATUSES = {
    "needs_clarification",
}


_ABSTAIN_STATUSES = {
    "abstained",
    "insufficient_information",
    "insufficient_evidence",
    "not_found",
    "conflicting_input",
    "irrelevant_input",
    "input_rejected",
}


def _text(
    value: Any,
) -> str | None:

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    return value


def _terminal_action(
    response: dict[str, Any],
) -> str | None:

    trace = response.get(
        "trace"
    )

    if not isinstance(
        trace,
        dict,
    ):
        return None


    actions = trace.get(
        "actions"
    )

    if not isinstance(
        actions,
        list,
    ):
        return None


    for value in reversed(
        actions
    ):

        action = _text(
            value
        )

        if action:
            return action


    return None


def _step_action(
    value: Any,
) -> str | None:

    if isinstance(
        value,
        str,
    ):

        value = value.strip()

        return (
            value.lower()
            if value
            else None
        )


    if not isinstance(
        value,
        dict,
    ):
        return None


    for key in (
        "action",
        "step",
        "step_type",
        "type",
        "status",
    ):

        action = _text(
            value.get(
                key
            )
        )

        if action:
            return action.lower()


    return None


def _contains_explicit_escalation(
    value: Any,
) -> bool:
    """
    Escalation is accepted only from an explicit structured
    escalation contract.

    A message merely containing the word 'escalate' does not qualify.
    """

    if isinstance(
        value,
        list,
    ):

        return any(
            _contains_explicit_escalation(
                item
            )
            for item in value
        )


    if not isinstance(
        value,
        dict,
    ):
        return False


    status = _text(
        value.get(
            "status"
        )
    )


    if (
        status
        and status.lower()
        == "escalate"
    ):

        final_step = value.get(
            "final_step"
        )


        if (
            _step_action(
                final_step
            )
            == "escalate"
        ):
            return True


        for key in (
            "steps",
            "guidance_steps",
            "actions",
        ):

            sequence = value.get(
                key
            )


            if (
                isinstance(
                    sequence,
                    list,
                )
                and sequence
                and _step_action(
                    sequence[-1]
                )
                == "escalate"
            ):
                return True


    for nested in value.values():

        if isinstance(
            nested,
            (
                dict,
                list,
            ),
        ):

            if _contains_explicit_escalation(
                nested
            ):
                return True


    return False


def build_final_outcome(
    response: dict[str, Any],
) -> dict[str, Any]:

    if not isinstance(
        response,
        dict,
    ):
        raise TypeError(
            "response must be a dictionary."
        )


    if (
        response.get(
            "diagnosis_confirmed",
            False,
        )
        is not False
    ):
        raise ValueError(
            "Final outcome cannot normalize "
            "a confirmed diagnosis."
        )


    if (
        response.get(
            "approved_for_automatic_execution",
            False,
        )
        is not False
    ):
        raise ValueError(
            "Final outcome cannot normalize "
            "automatic execution approval."
        )


    status = _text(
        response.get(
            "status"
        )
    )


    terminal = _terminal_action(
        response
    )


    # --------------------------------------------------------
    # ESCALATE
    #
    # Highest priority, but only for the explicit structured
    # escalation contract.
    # --------------------------------------------------------

    if _contains_explicit_escalation(
        response
    ):

        return FinalOutcome(
            decision=
                "ESCALATE",

            reason_code=
                "explicit_escalation_contract",

            source_status=
                status,

            terminal_action=
                terminal,
        ).model_dump()


    # --------------------------------------------------------
    # CLARIFY
    # --------------------------------------------------------

    if response.get(
        "next_question"
    ) is not None:

        return FinalOutcome(
            decision=
                "CLARIFY",

            reason_code=
                "next_question_present",

            source_status=
                status,

            terminal_action=
                terminal,
        ).model_dump()


    if terminal == "ask_clarification":

        return FinalOutcome(
            decision=
                "CLARIFY",

            reason_code=
                "agent_requested_clarification",

            source_status=
                status,

            terminal_action=
                terminal,
        ).model_dump()


    # --------------------------------------------------------
    # ABSTAIN
    #
    # Explicit agent abstention takes precedence over a
    # superficially answer-like source status.
    # --------------------------------------------------------

    if terminal == "abstain":

        return FinalOutcome(
            decision=
                "ABSTAIN",

            reason_code=
                "agent_abstained",

            source_status=
                status,

            terminal_action=
                terminal,
        ).model_dump()


    if status in _CLARIFY_STATUSES:

        return FinalOutcome(
            decision=
                "CLARIFY",

            reason_code=
                "response_status_requires_clarification",

            source_status=
                status,

            terminal_action=
                terminal,
        ).model_dump()


    if status in _ABSTAIN_STATUSES:

        return FinalOutcome(
            decision=
                "ABSTAIN",

            reason_code=
                "response_status_not_answerable",

            source_status=
                status,

            terminal_action=
                terminal,
        ).model_dump()


    # --------------------------------------------------------
    # ANSWER
    # --------------------------------------------------------

    if terminal == "return_information":

        return FinalOutcome(
            decision=
                "ANSWER",

            reason_code=
                "agent_returned_information",

            source_status=
                status,

            terminal_action=
                terminal,
        ).model_dump()


    if status in _ANSWER_STATUSES:

        return FinalOutcome(
            decision=
                "ANSWER",

            reason_code=
                "answer_status",

            source_status=
                status,

            terminal_action=
                terminal,
        ).model_dump()


    # --------------------------------------------------------
    # UNKNOWN STATE
    #
    # Fail closed rather than inventing an answer.
    # --------------------------------------------------------

    return FinalOutcome(
        decision=
            "ABSTAIN",

        reason_code=
            "conservative_default",

        source_status=
            status,

        terminal_action=
            terminal,
    ).model_dump()
