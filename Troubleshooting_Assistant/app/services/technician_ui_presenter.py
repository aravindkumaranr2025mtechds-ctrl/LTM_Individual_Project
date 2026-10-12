"""Human-readable presentation layer for the industrial technician UI.

This module intentionally separates internal Agentic AI terminology from
operator-facing language.

Backend/internal values remain unchanged. Only their presentation changes.
"""

from copy import deepcopy
from typing import Any


FIELD_LABELS = {
    "alarm_scope":
        "Alarm source",

    "reported_alarm_number":
        "Alarm number",

    "open_phase_reported":
        "Open-phase condition",

    "wrong_application_reported":
        "Application or motor sizing",

    "overload_reported":
        "Overload condition",

    "low_voltage_reported":
        "Supply voltage condition",

    "open_circuit_reported":
        "Open-circuit condition",

    "options_activated":
        "Machine options activated",

    "license_key_set":
        "License key installed",

    "entered_key_covers_activated_options":
        "License key coverage",
}


ALARM_SCOPE_OPTIONS = [
    {
        "value":
            "61352",

        "label":
            "Alarm 61352",
    },
    {
        "value":
            "61353",

        "label":
            "Alarm 61353",
    },
    {
        "value":
            "61358",

        "label":
            "Alarm 61358",
    },
    {
        "value":
            "61352_or_61353",

        "label":
            "Alarm 61352 or 61353",
    },
    {
        "value":
            "61352_or_61353_or_61358",

        "label":
            "Alarm 61352, 61353 or 61358",
    },
]


BOOLEAN_CHOICES = [
    {
        "value": True,
        "label": "Yes",
    },
    {
        "value": False,
        "label": "No",
    },
    {
        "value": None,
        "label": "Not sure",
    },
]


STATUS_PRESENTATION = {
    "completed": {
        "headline":
            "Verified guidance is available",

        "tone":
            "success",

        "progress_stage":
            "guidance",
    },

    "needs_user_input": {
        "headline":
            "A little more information is needed",

        "tone":
            "attention",

        "progress_stage":
            "clarification",
    },

    "inspection_suggested": {
        "headline":
            "One condition should be checked",

        "tone":
            "attention",

        "progress_stage":
            "inspection",
    },

    "abstained": {
        "headline":
            "Verified guidance is not available yet",

        "tone":
            "neutral",

        "progress_stage":
            "stopped",
    },

    "guard_blocked": {
        "headline":
            "The request was stopped for safety",

        "tone":
            "warning",

        "progress_stage":
            "verification",
    },

    "max_steps_exceeded": {
        "headline":
            "The troubleshooting session needs review",

        "tone":
            "warning",

        "progress_stage":
            "review",
    },
}


PROGRESS_STAGES = [
    {
        "id":
            "understand",

        "label":
            "Understand the problem",
    },
    {
        "id":
            "clarification",

        "label":
            "Check missing information",
    },
    {
        "id":
            "evidence",

        "label":
            "Search technical evidence",
    },
    {
        "id":
            "verification",

        "label":
            "Verify the evidence",
    },
    {
        "id":
            "guidance",

        "label":
            "Provide guidance",
    },
]


def humanize_field(
    field_name: str | None,
):
    """Return a technician-readable field label."""

    if field_name is None:
        return None

    return FIELD_LABELS.get(
        field_name,
        field_name.replace(
            "_",
            " ",
        ).strip().capitalize(),
    )


def choices_for_fact(
    field_name: str | None,
):
    """Return UI-safe response choices for a requested fact."""

    if (
        field_name
        == "alarm_scope"
    ):
        return deepcopy(
            ALARM_SCOPE_OPTIONS
        )

    if field_name in {
        "open_phase_reported",
        "wrong_application_reported",
        "overload_reported",
        "low_voltage_reported",
        "open_circuit_reported",
        "options_activated",
        "license_key_set",
        "entered_key_covers_activated_options",
    }:
        return deepcopy(
            BOOLEAN_CHOICES
        )

    return []


def _known_fact_cards(
    known_facts,
):
    cards = []

    if not isinstance(
        known_facts,
        dict,
    ):
        return cards

    for field, value in known_facts.items():

        if value is True:
            display_value = "Yes"

        elif value is False:
            display_value = "No"

        elif value is None:
            display_value = "Not sure"

        else:
            display_value = str(
                value
            )

        cards.append(
            {
                "field":
                    field,

                "label":
                    humanize_field(
                        field
                    ),

                "value":
                    display_value,

                "state":
                    "known",
            }
        )

    return cards


def _unknown_fact_cards(
    unknown_facts,
):
    if not isinstance(
        unknown_facts,
        list,
    ):
        return []

    return [
        {
            "field":
                field,

            "label":
                humanize_field(
                    field
                ),

            "value":
                "Needs checking",

            "state":
                "unknown",
        }
        for field
        in unknown_facts
    ]


def _extract_final_decision(
    payload,
):
    decision = payload.get(
        "final_decision"
    )

    if isinstance(
        decision,
        dict,
    ):
        return decision

    decisions = payload.get(
        "decisions"
    )

    if (
        isinstance(
            decisions,
            list,
        )
        and decisions
        and isinstance(
            decisions[-1],
            dict,
        )
    ):
        return decisions[-1]

    return {}


def _extract_state(
    payload,
):
    state = payload.get(
        "state"
    )

    if isinstance(
        state,
        dict,
    ):
        return state

    return {}


def _extract_evidence_summary(
    state,
):
    last_tool = state.get(
        "last_tool_result"
    )

    if not isinstance(
        last_tool,
        dict,
    ):
        return None

    protected = last_tool.get(
        "result"
    )

    if not isinstance(
        protected,
        dict,
    ):
        return None

    inner = protected.get(
        "result"
    )

    if not isinstance(
        inner,
        dict,
    ):
        inner = protected

    status = inner.get(
        "status"
    )

    answer = inner.get(
        "answer"
    )

    return {
        "tool":
            last_tool.get(
                "tool_name"
            ),

        "status":
            status,

        "answer":
            answer,

        "source_available":
            bool(
                inner.get(
                    "citations"
                )
                or inner.get(
                    "source_records"
                )
                or protected.get(
                    "citations"
                )
                or protected.get(
                    "source_records"
                )
            ),
    }


def build_technician_view(
    payload: dict[str, Any],
):
    """Convert an Agentic/backend response into operator-facing UI data."""

    if not isinstance(
        payload,
        dict,
    ):
        raise TypeError(
            "Technician view input must be an object."
        )

    payload = deepcopy(
        payload
    )

    status = payload.get(
        "status",
        "unknown",
    )

    presentation = (
        STATUS_PRESENTATION.get(
            status,
            {
                "headline":
                    "Troubleshooting information",

                "tone":
                    "neutral",

                "progress_stage":
                    "understand",
            },
        )
    )

    state = _extract_state(
        payload
    )

    decision = (
        _extract_final_decision(
            payload
        )
    )

    requested_fact = (
        decision.get(
            "requested_fact"
        )
    )

    known = _known_fact_cards(
        state.get(
            "known_facts",
            {},
        )
    )

    unknown = _unknown_fact_cards(
        state.get(
            "unknown_facts",
            [],
        )
    )

    evidence = (
        _extract_evidence_summary(
            state
        )
    )

    question = decision.get(
        "question"
    )

    suggestion = decision.get(
        "suggestion"
    )

    return {
        "status":
            status,

        "headline":
            presentation[
                "headline"
            ],

        "tone":
            presentation[
                "tone"
            ],

        "progress_stage":
            presentation[
                "progress_stage"
            ],

        "progress":
            deepcopy(
                PROGRESS_STAGES
            ),

        "question":
            question,

        "requested_fact": {
            "id":
                requested_fact,

            "label":
                humanize_field(
                    requested_fact
                ),

            "choices":
                choices_for_fact(
                    requested_fact
                ),
        }
        if requested_fact
        else None,

        "inspection_suggestion":
            suggestion,

        "what_we_know":
            known,

        "what_needs_checking":
            unknown,

        "evidence":
            evidence,

        "safety": {
            "diagnosis": {
                "confirmed":
                    False,

                "label":
                    "Cause not yet confirmed",
            },

            "automatic_execution": {
                "approved":
                    False,

                "label":
                    "No automatic machine action will be performed",
            },
        },

        "advanced": {
            "developer_status":
                status,

            "agent_action":
                decision.get(
                    "action"
                ),

            "tool_name":
                decision.get(
                    "tool_name"
                ),
        },
    }
