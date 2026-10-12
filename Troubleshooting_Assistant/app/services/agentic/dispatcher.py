"""Protected dispatcher for bounded agent tool calls.

The language model never receives executable Python functions.
It may propose a structured AgentDecision. This dispatcher independently
validates the requested tool and arguments before invoking existing,
already-validated troubleshooting services.
"""

from copy import deepcopy
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
)

from app.services.agentic.contracts import (
    AgentDecision,
    AgentToolName,
)

from app.services.agentic.tool_registry import (
    ToolRegistry,
)

from app.services.development_troubleshooting_orchestrator import (
    DevelopmentTroubleshootingRequest,
    orchestrate_development_troubleshooting,
)

from app.services.troubleshooting_answer_builder import (
    build_structured_assistance,
)

from app.services.troubleshooting_input_guidance import (
    get_troubleshooting_input_guidance,
)

from app.services.troubleshooting_question_builder import (
    get_question_form,
)


from app.services.enterprise_abb_router import (
    retrieve_enterprise_evidence_with_abb,
)

class ToolObservation(BaseModel):
    """Result returned to the agent after protected tool execution."""

    model_config = ConfigDict(
        extra="forbid"
    )

    status: Literal[
        "tool_result"
    ] = "tool_result"

    tool_name: AgentToolName

    result: dict[
        str,
        Any
    ]

    diagnosis_confirmed: Literal[
        False
    ] = False

    approved_for_automatic_execution: Literal[
        False
    ] = False


_ALLOWED_ARGUMENTS = {
    "troubleshooting_guidance": {
        "mode",
    },

    "troubleshooting_questions": {
        "mode",
    },

    "abb_stall": {
        "requested_information",
        "open_phase_reported",
        "wrong_application_reported",
        "overload_reported",
        "low_voltage_reported",
        "open_circuit_reported",
        "deferred_fact_ids",
    },

    "siemens_licensing": {
        "options_activated",
        "license_key_set",
        "entered_key_covers_activated_options",
        "reported_alarm_number",
        "clarifications_used",
        "deferred_fact_ids",
    },

    "siemens_logfile": {
        "alarm_scope",
    },
}

_ENTERPRISE_EVIDENCE_ARGUMENTS = {
    "query",
    "alarm_number",
    "top_k",
    "manufacturer",
    "plant_id",
    "department",
    "equipment_id",
    "equipment_type",
    "model",
    "document_type",
    "document_status",
    "revision",
    "document_family_id",
}



def _validate_argument_keys(
    tool_name,
    arguments,
):
    if not isinstance(
        arguments,
        dict,
    ):
        raise ValueError(
            "Tool arguments must be an object."
        )


    if (
        tool_name
        == "enterprise_evidence_search"
    ):
        allowed = (
            _ENTERPRISE_EVIDENCE_ARGUMENTS
        )

    else:
        allowed = (
            _ALLOWED_ARGUMENTS[
                tool_name
            ]
        )


    unexpected = (
        set(arguments)
        - allowed
    )


    if unexpected:
        raise ValueError(
            "Unsupported tool arguments: "
            + ", ".join(
                sorted(
                    unexpected
                )
            )
        )



def _assert_safe_assistance(
    assistance,
):
    if (
        assistance.get(
            "diagnosis_confirmed"
        )
        is not False
    ):
        raise RuntimeError(
            "Protected tool returned an unsafe "
            "diagnosis_confirmed value."
        )

    if (
        assistance.get(
            "approved_for_automatic_execution"
        )
        is not False
    ):
        raise RuntimeError(
            "Protected tool returned an unsafe "
            "automatic-execution value."
        )


class ProtectedToolDispatcher:
    """Execute only registered, bounded troubleshooting tools."""

    def __init__(
        self,
        registry: ToolRegistry,
    ):
        self._registry = registry

    def dispatch(
        self,
        decision: AgentDecision,
    ) -> ToolObservation:

        if (
            decision.action
            != "call_tool"
        ):
            raise ValueError(
                "Dispatcher accepts only call_tool decisions."
            )

        tool_name = (
            decision.tool_name
        )

        if tool_name is None:
            raise ValueError(
                "Tool name is required."
            )

        if not self._registry.contains(
            tool_name
        ):
            raise PermissionError(
                "Tool is outside the protected registry."
            )

        arguments = deepcopy(
            decision.tool_arguments
        )

        _validate_argument_keys(
            tool_name,
            arguments,
        )

        if (
            tool_name
            == "troubleshooting_guidance"
        ):
            result = (
                get_troubleshooting_input_guidance(
                    arguments.get(
                        "mode"
                    )
                )
            )

            _assert_safe_assistance(
                result
            )

            return ToolObservation(
                tool_name=
                    tool_name,

                result=
                    result,
            )

        if (
            tool_name
            == "troubleshooting_questions"
        ):
            mode = arguments.get(
                "mode"
            )

            if not mode:
                raise ValueError(
                    "troubleshooting_questions "
                    "requires explicit mode."
                )

            result = get_question_form(
                mode
            )

            _assert_safe_assistance(
                result
            )

            return ToolObservation(
                tool_name=
                    tool_name,

                result=
                    result,
            )

        if (
            tool_name
            == "enterprise_evidence_search"
        ):

            from app.services import (
                retrieval_service,
            )


            query = arguments.get(
                "query"
            )


            if (
                not isinstance(
                    query,
                    str,
                )
                or not query.strip()
            ):
                raise ValueError(
                    "enterprise_evidence_search requires "
                    "an explicit non-empty query."
                )


            top_k = arguments.get(
                "top_k",
                5,
            )


            if (
                not isinstance(
                    top_k,
                    int,
                )
                or isinstance(
                    top_k,
                    bool,
                )
                or not (
                    1 <= top_k <= 20
                )
            ):
                raise ValueError(
                    "top_k must be an integer "
                    "between 1 and 20."
                )


            metadata_keys = (
                "manufacturer",
                "plant_id",
                "department",
                "equipment_id",
                "equipment_type",
                "model",
                "document_type",
                "document_status",
                "revision",
                "document_family_id",
            )


            metadata_filters = {
                key:
                    arguments[key]

                for key in metadata_keys

                if (
                    key in arguments
                    and arguments[key]
                    is not None
                )
            }


            retrieved = (
                retrieve_enterprise_evidence_with_abb(
                    query=
                        query.strip(),

                    alarm_number=
                        arguments.get(
                            "alarm_number"
                        ),

                    top_k=
                        top_k,

                    metadata_filters=(
                        metadata_filters
                        or None
                    ),
                )
            )


            if not isinstance(
                retrieved,
                dict,
            ):
                raise TypeError(
                    "Enterprise retrieval must "
                    "return an object."
                )


            results = (
                retrieved.get(
                    "results"
                )
                or []
            )


            if not isinstance(
                results,
                list,
            ):
                raise TypeError(
                    "Enterprise retrieval results "
                    "must be a list."
                )


            body = {
                "status": (
                    "evidence_retrieved"
                    if results
                    else "not_found"
                ),

                "message": (
                    "Registered industrial evidence "
                    "was retrieved."
                    if results
                    else
                    "No eligible registered industrial "
                    "evidence matched the request."
                ),

                "evidence":
                    retrieved,

                "diagnosis_confirmed":
                    False,

                "approved_for_automatic_execution":
                    False,
            }


            assistance = {
                "result":
                    body,

                "diagnosis_confirmed":
                    False,

                "approved_for_automatic_execution":
                    False,
            }


            _assert_safe_assistance(
                assistance
            )


            return ToolObservation(
                tool_name=
                    tool_name,

                result=
                    assistance,
            )


        structured = (
            build_structured_assistance(
                tool_name,
                arguments,
            )
        )

        validated = TypeAdapter(
            DevelopmentTroubleshootingRequest
        ).validate_python(
            structured
        )

        assistance = (
            orchestrate_development_troubleshooting(
                validated
            )
        )

        _assert_safe_assistance(
            assistance
        )

        return ToolObservation(
            tool_name=
                tool_name,

            result=
                assistance,
        )
