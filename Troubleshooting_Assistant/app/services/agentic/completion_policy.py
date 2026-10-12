"""Deterministic completion policy for bounded Agentic AI.

A verified protected tool observation with a terminal supported status
may finish the evidence-acquisition cycle without asking the LLM to
decide whether retrieval should stop.
"""

from pydantic import (
    BaseModel,
    ConfigDict,
)

from app.services.agentic.dispatcher import (
    ToolObservation,
)


TERMINAL_SUPPORTED_STATUSES = frozenset(
    {
        "answer_supported",
        "description_supported",
        "source_information",
    }
)


class TerminalEvidenceAssessment(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    terminal_supported: bool

    result_status: str | None = None

    reason: str


def _extract_result_status(
    result,
):
    """Extract the bounded service status without interpreting free text."""

    if not isinstance(
        result,
        dict,
    ):
        return None

    nested = result.get(
        "result"
    )

    if isinstance(
        nested,
        dict,
    ):

        nested_status = nested.get(
            "status"
        )

        if isinstance(
            nested_status,
            str,
        ):
            return nested_status

    direct_status = result.get(
        "status"
    )

    if isinstance(
        direct_status,
        str,
    ):
        return direct_status

    return None


def assess_terminal_evidence(
    observation: ToolObservation,
) -> TerminalEvidenceAssessment:
    """Classify whether verified evidence is terminal for this bounded cycle."""

    status = _extract_result_status(
        observation.result
    )

    if (
        status
        in TERMINAL_SUPPORTED_STATUSES
    ):
        return TerminalEvidenceAssessment(
            terminal_supported=True,

            result_status=status,

            reason=(
                "Verified protected evidence returned "
                f"terminal supported status: {status}."
            ),
        )

    return TerminalEvidenceAssessment(
        terminal_supported=False,

        result_status=status,

        reason=(
            "Protected observation is not a terminal "
            "supported evidence result."
        ),
    )
