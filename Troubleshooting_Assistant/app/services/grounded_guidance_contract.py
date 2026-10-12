from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


GuidancePhase = Literal[
    "start",
    "check",
    "observe",
    "next",
    "stop",
    "escalate",
]


GuidanceStatus = Literal[
    "ready",
    "clarification_required",
    "stop",
    "escalate",
]


OrderingBasis = Literal[
    "source_explicit",
    "safety_then_source",
    "source_list_no_mandatory_order",
]


class GroundedGuidanceStep(
    BaseModel
):

    model_config = ConfigDict(
        extra="forbid",
    )

    step_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    phase: GuidancePhase

    instruction: str = Field(
        min_length=1,
        max_length=1200,
    )

    observation_request: (
        str
        | None
    ) = Field(
        default=None,
        min_length=1,
        max_length=800,
    )

    stop_condition: (
        str
        | None
    ) = Field(
        default=None,
        min_length=1,
        max_length=800,
    )

    evidence_ids: list[
        str
    ] = Field(
        min_length=1,
        max_length=8,
    )

    page_numbers: list[
        int
    ] = Field(
        min_length=1,
        max_length=32,
    )

    actionable: StrictBool = False


    @field_validator(
        "instruction",
        "observation_request",
        "stop_condition",
    )
    @classmethod
    def normalize_text(
        cls,
        value,
    ):

        if value is None:
            return None

        normalized = (
            value.strip()
        )

        if not normalized:
            raise ValueError(
                "Guidance text cannot be blank."
            )

        return normalized


    @field_validator(
        "evidence_ids",
    )
    @classmethod
    def validate_evidence_ids(
        cls,
        value,
    ):

        normalized = []

        for evidence_id in value:

            if not isinstance(
                evidence_id,
                str,
            ):
                raise ValueError(
                    "Every evidence ID must be a string."
                )

            evidence_id = (
                evidence_id.strip()
            )

            if not evidence_id:
                raise ValueError(
                    "Evidence IDs cannot be blank."
                )

            normalized.append(
                evidence_id
            )


        if (
            len(
                normalized
            )
            != len(
                set(
                    normalized
                )
            )
        ):
            raise ValueError(
                "Evidence IDs must be unique within a step."
            )


        return normalized


    @field_validator(
        "page_numbers",
    )
    @classmethod
    def validate_pages(
        cls,
        value,
    ):

        if any(
            (
                type(page)
                is not int
                or page < 1
            )

            for page
            in value
        ):
            raise ValueError(
                "Source pages must be positive integers."
            )


        if (
            len(
                value
            )
            != len(
                set(
                    value
                )
            )
        ):
            raise ValueError(
                "Source pages must be unique within a step."
            )


        return value


    @model_validator(
        mode="after"
    )
    def enforce_phase_contract(
        self,
    ):

        if (
            self.phase
            == "observe"
            and not self.observation_request
        ):
            raise ValueError(
                "observe steps require observation_request."
            )


        if (
            self.phase
            in {
                "stop",
                "escalate",
            }
            and not self.stop_condition
        ):
            raise ValueError(
                "stop/escalate steps require stop_condition."
            )


        return self


class GroundedGuidance(
    BaseModel
):

    model_config = ConfigDict(
        extra="forbid",
    )

    schema_version: Literal[
        "grounded_guidance_v1"
    ] = "grounded_guidance_v1"

    status: GuidanceStatus

    reported_problem: str = Field(
        min_length=1,
        max_length=1200,
    )

    ordering_basis: OrderingBasis

    ordering_note: str = Field(
        min_length=1,
        max_length=1000,
    )

    steps: list[
        GroundedGuidanceStep
    ] = Field(
        min_length=1,
        max_length=20,
    )

    limitations: list[
        str
    ] = Field(
        default_factory=list,
        max_length=20,
    )

    diagnosis_confirmed: Literal[
        False
    ] = False

    approved_for_automatic_execution: Literal[
        False
    ] = False


    @field_validator(
        "reported_problem",
        "ordering_note",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value,
    ):

        value = (
            value.strip()
        )

        if not value:
            raise ValueError(
                "Required guidance text cannot be blank."
            )

        return value


    @field_validator(
        "limitations",
    )
    @classmethod
    def normalize_limitations(
        cls,
        value,
    ):

        normalized = []

        for item in value:

            if not isinstance(
                item,
                str,
            ):
                raise ValueError(
                    "Limitations must be strings."
                )

            item = (
                item.strip()
            )

            if not item:
                raise ValueError(
                    "Limitations cannot contain blank entries."
                )

            normalized.append(
                item
            )


        if (
            len(
                normalized
            )
            != len(
                set(
                    normalized
                )
            )
        ):
            raise ValueError(
                "Limitations must be unique."
            )


        return normalized


    @model_validator(
        mode="after"
    )
    def enforce_guidance_structure(
        self,
    ):

        step_ids = [
            step.step_id

            for step
            in self.steps
        ]


        if (
            len(
                step_ids
            )
            != len(
                set(
                    step_ids
                )
            )
        ):
            raise ValueError(
                "Guidance step IDs must be unique."
            )


        if (
            self.steps[
                0
            ].phase
            != "start"
        ):
            raise ValueError(
                "Grounded guidance must begin with a start step."
            )


        terminal_indexes = [
            index

            for index, step
            in enumerate(
                self.steps
            )

            if step.phase
            in {
                "stop",
                "escalate",
            }
        ]


        if terminal_indexes:

            if len(
                terminal_indexes
            ) > 1:
                raise ValueError(
                    "Only one terminal stop/escalate step is allowed."
                )

            if (
                terminal_indexes[
                    0
                ]
                != len(
                    self.steps
                )
                - 1
            ):
                raise ValueError(
                    "A stop/escalate step must be the final step."
                )


        if (
            self.status
            == "stop"
            and self.steps[
                -1
            ].phase
            != "stop"
        ):
            raise ValueError(
                "status=stop requires a final stop step."
            )


        if (
            self.status
            == "escalate"
            and self.steps[
                -1
            ].phase
            != "escalate"
        ):
            raise ValueError(
                "status=escalate requires a final escalate step."
            )


        if (
            self.ordering_basis
            == "source_list_no_mandatory_order"
            and
            "no mandatory order"
            not in self.ordering_note.casefold()
        ):
            raise ValueError(
                "When the source does not establish mandatory order, "
                "ordering_note must explicitly state that no mandatory "
                "order is established."
            )


        return self


def validate_grounded_guidance(
    payload,
    *,
    allowed_evidence_ids:
        set[str]
        | None
        = None,
):
    """
    Validate the structural grounded-guidance contract.

    This function does not determine whether a statement is actually
    supported by the cited evidence. Evidence-content verification is
    a separate later verifier stage.
    """

    guidance = (
        GroundedGuidance
        .model_validate(
            payload
        )
    )


    if (
        allowed_evidence_ids
        is not None
    ):

        if not isinstance(
            allowed_evidence_ids,
            set,
        ):
            raise TypeError(
                "allowed_evidence_ids must be a set of strings or None."
            )


        if any(
            not isinstance(
                value,
                str,
            )
            or not value

            for value
            in allowed_evidence_ids
        ):
            raise ValueError(
                "allowed_evidence_ids must contain non-empty strings."
            )


        referenced = {
            evidence_id

            for step
            in guidance.steps

            for evidence_id
            in step.evidence_ids
        }


        unknown = (
            referenced
            - allowed_evidence_ids
        )


        if unknown:
            raise ValueError(
                "Guidance references evidence IDs outside the "
                "eligible evidence set: "
                + ", ".join(
                    sorted(
                        unknown
                    )
                )
            )


    return (
        guidance
        .model_dump(
            mode="json"
        )
    )
