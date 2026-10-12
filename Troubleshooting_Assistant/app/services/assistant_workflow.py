"""Local conversation boundary: explicit answers in, fresh source evidence out."""
from copy import deepcopy
import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.services.agentic.contracts import AgentDecision, AgentState
from app.services.agentic.dispatcher import ProtectedToolDispatcher, _ALLOWED_ARGUMENTS
from app.services.agentic.loop import run_agent_loop
from app.services.agentic.model_adapter import AgentModelAdapter
from app.services.agentic.ollama_adapter import OllamaAgentModelAdapter
from app.services.agentic.tool_registry import ToolRegistry, build_default_tool_registry
from app.services.source_page_service import (
    build_registered_source_page,
)

from app.services.itrs import calculate_itrs
from app.services.troubleshooting_answer_builder import TRI_STATE_FIELDS
from app.services.input_relevance_gate import assess_input_relevance
from app.services.evidence_sufficiency_gate import assess_enterprise_evidence_sufficiency
from app.services.semantic_relevance_gate import assess_semantic_relevance
from app.services.grounded_evidence_bundle import build_grounded_evidence_bundle
from app.services.grounded_synthesis_runtime import (
    execute_grounded_synthesis,
    grounded_synthesis_runtime_enabled,
)
from app.services.final_outcome import build_final_outcome
from app.services.evidence_contract import build_evidence_contract

router = APIRouter()
logger = logging.getLogger(__name__)
INTENTS = {
    "abb_stall": "request_abb_stall_assistance",
    "siemens_licensing": "compare_siemens_licensing",
    "siemens_logfile": "request_logfile_parameter",
}
CHOICES = {
    "requested_information": [
        ("List manual causes", "list_possible_causes"),
        ("Review existing reports", "review_reports"),
        ("Can a cause be identified?", "identify_cause"),
    ],
    "alarm_scope": [(value.replace("_or_", " or "), value) for value in (
        "61352", "61353", "61352_or_61353", "61358", "61352_or_61353_or_61358"
    )],
}
PROMPTS = {
    "requested_information": "What information do you need for ABB Motor stalls?",
    "alarm_scope": "Which alarm scope should be checked?",
}


class ConversationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    mode: Literal[
        "abb_stall",
        "siemens_licensing",
        "siemens_logfile",
        "enterprise_evidence",
    ]

    user_message: str = Field(
        default="",
        strict=True,
        max_length=2000,
    )

    answers: dict[
        str,
        Any
    ] = Field(
        default_factory=dict,
        max_length=16,
    )



def validated_answers(request):
    answers = deepcopy(request.answers)
    fields = TRI_STATE_FIELDS.get(request.mode, set())
    if set(answers) - _ALLOWED_ARGUMENTS[request.mode]:
        raise ValueError("Unsupported answer field for the selected mode.")
    deferred = answers.get("deferred_fact_ids", [])
    if (not isinstance(deferred, list) or any(type(key) is not str or key not in fields for key in deferred)
            or len(deferred) != len(set(deferred))):
        raise ValueError("Deferred fields must be unique supported report fields.")
    for key in fields & answers.keys():
        value = answers[key]
        if value is not None and type(value) is not bool:
            raise ValueError(f"{key} accepts true, false, or null (defer).")
        if value is None:
            if key not in deferred:
                deferred.append(key)
            del answers[key]
        elif key in deferred:
            deferred.remove(key)
    if deferred or "deferred_fact_ids" in answers:
        answers["deferred_fact_ids"] = deferred
    for key, options in CHOICES.items():
        if key in answers and answers[key] not in [value for _, value in options]:
            raise ValueError(f"Select an explicit supported value for {key}.")
    if "reported_alarm_number" in answers and answers["reported_alarm_number"] not in (None, "8080", "8081"):
        raise ValueError("Reported licensing alarm must be 8080, 8081, or null.")
    if "clarifications_used" in answers:
        count = answers["clarifications_used"]
        if type(count) is not int or not 0 <= count <= 2:
            raise ValueError("clarifications_used must be an integer from 0 to 2.")
    return answers


def source_question(mode, body):
    if mode == "abb_stall":
        return (body.get("clarification") or {}).get("question")
    return body.get("question")


class PlannerUnavailable(RuntimeError):
    pass


class SourceAwareAdapter(AgentModelAdapter):
    """Use structured source outcomes before asking Ollama to plan."""
    def __init__(self, mode):
        self.mode = mode
        self.ollama_calls = 0

    @property
    def provider_name(self):
        return "source_policy_and_ollama"

    def decide(self, state, allowed_tools):
        if state.last_tool_result is not None:
            body = state.last_tool_result["result"]["result"]
            question = source_question(self.mode, body)
            if question:
                return AgentDecision(
                    action="ask_clarification", reason="The source policy requests an explicit report.",
                    requested_fact=question["fact_id"], question=question["text"],
                )
            action = "return_information" if body["status"] == "reports_complete" else "abstain"
            return AgentDecision(action=action, reason=body.get("message") or "The source policy has no further question.")
        self.ollama_calls += 1
        try:
            decision = OllamaAgentModelAdapter(model="llama3.2:3b", timeout_seconds=180).decide(state, allowed_tools)
            missing = "requested_information" if self.mode == "abb_stall" else "alarm_scope"
            if decision.action == "ask_clarification" and decision.requested_fact == missing:
                return AgentDecision(
                    action="ask_clarification", reason="An explicit request detail is missing.",
                    requested_fact=missing, question=PROMPTS[missing],
                )
            if decision.action == "abstain":
                return AgentDecision(action="abstain", reason="The planner could not resolve the request.")
            raise ValueError("Planner did not request the missing supported field.")
        except Exception as error:
            raise PlannerUnavailable("Select the request details in the form, or check that Ollama is running.") from error


def _validated_enterprise_answers(
    request,
):
    """
    Validate only explicit enterprise-search inputs.

    user_message is deliberately not converted into query
    or any other structured fact.
    """

    answers = deepcopy(
        request.answers
    )


    allowed = {
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


    unexpected = (
        set(
            answers
        )
        - allowed
    )


    if unexpected:
        raise ValueError(
            "Unsupported enterprise evidence fields: "
            + ", ".join(
                sorted(
                    unexpected
                )
            )
        )


    query = answers.get(
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
            "enterprise_evidence requires an explicit "
            "non-empty answers.query value."
        )


    validated = {
        "query":
            query.strip()
    }


    if "top_k" in answers:

        top_k = answers[
            "top_k"
        ]


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


        validated[
            "top_k"
        ] = top_k


    if "alarm_number" in answers:

        alarm_number = answers[
            "alarm_number"
        ]


        if alarm_number is not None:

            if isinstance(
                alarm_number,
                bool,
            ):
                raise ValueError(
                    "alarm_number must be explicitly "
                    "reported as text or an integer."
                )


            if isinstance(
                alarm_number,
                str,
            ):

                alarm_number = (
                    alarm_number.strip()
                )


                if not alarm_number:
                    raise ValueError(
                        "alarm_number cannot be blank."
                    )


            elif not isinstance(
                alarm_number,
                int,
            ):
                raise ValueError(
                    "alarm_number must be text "
                    "or an integer."
                )


            validated[
                "alarm_number"
            ] = alarm_number


    metadata_fields = (
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


    for field in metadata_fields:

        if field not in answers:
            continue


        value = answers[
            field
        ]


        if value is None:
            continue


        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                f"{field} must be explicit text."
            )


        value = value.strip()


        if not value:
            raise ValueError(
                f"{field} cannot be blank."
            )


        validated[
            field
        ] = value


    return validated


class EnterpriseEvidenceAdapter(
    AgentModelAdapter
):
    """
    Deterministic adapter for explicit enterprise evidence search.

    It performs no free-text fact inference and makes no Ollama call.
    """

    def __init__(
        self,
    ):
        self.ollama_calls = 0


    @property
    def provider_name(
        self,
    ):
        return (
            "deterministic_enterprise_evidence"
        )


    def decide(
        self,
        state,
        allowed_tools,
    ):

        if (
            state.last_tool_result
            is None
        ):

            return AgentDecision(
                action=
                    "call_tool",

                reason=(
                    "Execute the explicitly requested "
                    "registered-evidence search."
                ),

                tool_name=
                    "enterprise_evidence_search",

                tool_arguments=
                    deepcopy(
                        state.known_facts
                    ),
            )


        body = (
            state.last_tool_result[
                "result"
            ][
                "result"
            ]
        )


        status = body.get(
            "status"
        )


        if (
            status
            == "evidence_retrieved"
        ):

            return AgentDecision(
                action=
                    "return_information",

                reason=(
                    body.get(
                        "message"
                    )
                    or
                    "Registered evidence was retrieved."
                ),
            )


        return AgentDecision(
            action=
                "abstain",

            reason=(
                body.get(
                    "message"
                )
                or
                "No eligible registered evidence "
                "supports this request."
            ),
        )


def _run_conversation_core(
    request,
):
    enterprise_mode = (
        request.mode
        == "enterprise_evidence"
    )


    if enterprise_mode:

        from app.services.agentic.tool_registry import (
            build_enterprise_evidence_tool_spec,
        )


        answers = (
            _validated_enterprise_answers(
                request
            )
        )
        # INPUT_RELEVANCE_GATE_V1
        #
        # The enterprise-specific validator above remains the
        # authoritative field boundary. Only the already-validated
        # explicit query is screened here. user_message is never
        # promoted into query or trusted machine observations.
        input_gate = (
            assess_input_relevance(
                answers[
                    "query"
                ]
            )
        )

        if not input_gate[
            "continue_to_retrieval"
        ]:

            response_status = (
                "needs_more_detail"

                if input_gate[
                    "status"
                ]
                == "needs_more_detail"

                else "input_rejected"
            )

            return {
                "status":
                    response_status,

                "mode":
                    request.mode,

                "source_result":
                    None,

                "next_question":
                    None,

                "continuation_answers":
                    deepcopy(
                        answers
                    ),

                "message":
                    input_gate[
                        "message"
                    ],

                "input_gate":
                    deepcopy(
                        input_gate
                    ),

                "trace": {
                    "loop_status":
                        response_status,

                    "ollama_calls":
                        0,

                    "tool_calls":
                        0,

                    "actions":
                        [],
                },

                "diagnosis_confirmed":
                    False,

                "approved_for_automatic_execution":
                    False,
            }



        tool_spec = (
            build_enterprise_evidence_tool_spec()
        )


        registry = ToolRegistry(
            [
                tool_spec
            ]
        )


        adapter = (
            EnterpriseEvidenceAdapter()
        )


        tool_name = (
            "enterprise_evidence_search"
        )


        required = (
            tool_spec
            .required_explicit_fields
        )


        detected_intent = (
            "search_enterprise_evidence"
        )


        manufacturer_candidate = (
            answers.get(
                "manufacturer"
            )
        )


    else:

        answers = (
            validated_answers(
                request
            )
        )


        registry = ToolRegistry(
            [
                build_default_tool_registry()
                .get(
                    request.mode
                )
            ]
        )


        adapter = (
            SourceAwareAdapter(
                request.mode
            )
        )


        tool_name = (
            request.mode
        )


        required = (
            registry.get(
                tool_name
            )
            .required_explicit_fields
        )


        detected_intent = (
            INTENTS[
                request.mode
            ]
        )


        manufacturer_candidate = (
            "ABB"
            if request.mode
            == "abb_stall"
            else "Siemens"
        )


    state = AgentState(
        user_message=(
            request.user_message
            or
            "Explicit guided assistance request"
        ),

        detected_intent=
            detected_intent,

        known_facts=
            answers,

        unknown_facts=[
            key

            for key in required

            if key not in answers
        ],

        manufacturer_candidate=
            manufacturer_candidate,
    )


    result = run_agent_loop(
        state,
        adapter,
        registry,
        ProtectedToolDispatcher(
            registry
        ),
        max_steps=3,
    )


    if result.status in {
        "guard_blocked",
        "max_steps_exceeded",
    }:
        raise ValueError(
            result.blocked_reason
            or
            "The bounded workflow could not "
            "finish this turn."
        )


    body = (
        result.observations[
            -1
        ].result[
            "result"
        ]

        if result.observations

        else None
    )
    # EVIDENCE_SUFFICIENCY_GATE_V1
    #
    # Enterprise retrieval is assessed only after the protected
    # retrieval/agent path has completed. The gate does not use
    # similarity as confidence and does not generate a diagnosis.
    evidence_sufficiency = None

    if enterprise_mode:

        evidence_sufficiency = (
            assess_enterprise_evidence_sufficiency(
                body
            )
        )
    # SEMANTIC_RELEVANCE_GATE_V1
    #
    # Structural sufficiency and semantic relevance are separate.
    # Similarity is never interpreted as confidence.
    # Only semantic candidate retrievals explicitly held by the
    # sufficiency gate are assessed here.
    semantic_relevance = None

    if (
        enterprise_mode
        and evidence_sufficiency
        and evidence_sufficiency[
            "requires_relevance_assessment"
        ]
    ):

        semantic_source = (
            body.get(
                "evidence"
            )

            if isinstance(
                body,
                dict,
            )

            else None
        )

        relevance_query = (
            answers[
                "query"
            ]
        )

        if isinstance(
            semantic_source,
            dict,
        ):

            candidate_relevance_query = (
                semantic_source.get(
                    "relevance_query"
                )
            )

            if (
                isinstance(
                    candidate_relevance_query,
                    str,
                )
                and
                candidate_relevance_query.strip()
            ):

                relevance_query = (
                    candidate_relevance_query.strip()
                )

        semantic_relevance = (
            assess_semantic_relevance(
                relevance_query,
                semantic_source,
            )
        )
    # GROUNDED_EVIDENCE_BUNDLE_V1
    #
    # Existing evidence-gate permission remains unchanged.
    # Final LLM readiness additionally requires a successfully
    # validated evidence bundle.
    grounded_evidence_bundle = None
    grounded_evidence_ready = False
    grounded_evidence_reason = "upstream_gate_blocked"

    grounded_bundle_allowed = False

    if (
        enterprise_mode
        and evidence_sufficiency
    ):

        grounded_bundle_allowed = bool(
            evidence_sufficiency[
                "allow_grounded_synthesis"
            ]
        )

        if evidence_sufficiency[
            "requires_relevance_assessment"
        ]:

            grounded_bundle_allowed = bool(
                semantic_relevance
                and semantic_relevance[
                    "allow_grounded_synthesis"
                ]
            )


    if grounded_bundle_allowed:

        retrieval_payload = (
            body.get(
                "evidence"
            )

            if isinstance(
                body,
                dict,
            )

            else None
        )


        if not isinstance(
            retrieval_payload,
            dict,
        ):

            grounded_evidence_reason = (
                "missing_retrieval_payload"
            )

        else:

            try:

                grounded_evidence_bundle = (
                    build_grounded_evidence_bundle(
                        retrieval_payload,
                        evidence_sufficiency,
                        semantic_relevance,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                grounded_evidence_bundle = None
                grounded_evidence_ready = False

                grounded_evidence_reason = (
                    "packaging_validation_failed"
                )

            else:

                grounded_evidence_ready = True

                grounded_evidence_reason = (
                    "ready"
                )





    question = None


    if (
        body
        and not enterprise_mode
    ):
        question = (
            source_question(
                request.mode,
                body,
            )
        )


    final = (
        result.final_decision
    )


    if (
        final
        and final.action
        == "ask_clarification"
    ):

        question = (
            deepcopy(
                question
            )

            if question

            else {
                "fact_id":
                    final.requested_fact,

                "text":
                    final.question,
            }
        )


        options = CHOICES.get(
            question[
                "fact_id"
            ],
            [
                (
                    "Reported present",
                    True,
                ),
                (
                    "Reported absent",
                    False,
                ),
                (
                    "Cannot clarify now",
                    None,
                ),
            ],
        )


        question[
            "choices"
        ] = [
            {
                "label":
                    label,

                "value":
                    value,
            }

            for label, value
            in options
        ]


    continuation = deepcopy(
        answers
    )


    if (
        request.mode
        == "siemens_licensing"
        and question
    ):

        continuation[
            "clarifications_used"
        ] = question[
            "next_clarifications_used"
        ]


    response = {
        "status": (
            body[
                "status"
            ]
            if body

            else result.status
        ),

        "mode":
            request.mode,

        "source_result":
            body,

        "next_question":
            question,

        "continuation_answers":
            continuation,

        "message": (
            body.get(
                "message",
                "",
            )
            if body

            else (
                final.reason
                if final

                else "No result."
            )
        ),

        "trace": {
            "loop_status":
                result.status,

            "ollama_calls":
                adapter.ollama_calls,

            "tool_calls":
                len(
                    result.observations
                ),

            "actions": [
                decision.action

                for decision
                in result.decisions
            ],
        },

        "diagnosis_confirmed":
            False,

        "approved_for_automatic_execution":
            False,
    }
    if enterprise_mode:

        response[
            "evidence_sufficiency"
        ] = deepcopy(
            evidence_sufficiency
        )

        response[
            "grounded_synthesis_allowed"
        ] = bool(
            evidence_sufficiency[
                "allow_grounded_synthesis"
            ]
        )

        response[
            "semantic_relevance_assessment_required"
        ] = bool(
            evidence_sufficiency[
                "requires_relevance_assessment"
            ]
        )
    if enterprise_mode:

        response[
            "semantic_relevance"
        ] = (
            deepcopy(
                semantic_relevance
            )

            if semantic_relevance
            is not None

            else None
        )

        response[
            "semantic_relevance_assessed"
        ] = (
            semantic_relevance
            is not None
        )

        if evidence_sufficiency[
            "requires_relevance_assessment"
        ]:

            response[
                "grounded_synthesis_allowed"
            ] = bool(
                semantic_relevance
                and semantic_relevance[
                    "allow_grounded_synthesis"
                ]
            )
    if enterprise_mode:

        response[
            "grounded_evidence_bundle"
        ] = (
            deepcopy(
                grounded_evidence_bundle
            )

            if grounded_evidence_bundle
            is not None

            else None
        )

        response[
            "eligible_evidence_ids"
        ] = (
            list(
                grounded_evidence_bundle[
                    "evidence_ids"
                ]
            )

            if grounded_evidence_bundle
            is not None

            else []
        )

        response[
            "grounded_evidence_ready"
        ] = bool(
            grounded_evidence_ready
        )

        response[
            "grounded_evidence_reason"
        ] = (
            grounded_evidence_reason
        )

        response[
            "grounded_synthesis_ready"
        ] = bool(
            response[
                "grounded_synthesis_allowed"
            ]
            and
            grounded_evidence_ready
        )

        response[
            "grounded_synthesis_execution_enabled"
        ] = (
            grounded_synthesis_runtime_enabled()
        )

        response[
            "grounded_synthesis"
        ] = None

        response[
            "trace"
        ][
            "grounded_synthesis_calls"
        ] = 0

        if (
            response[
                "grounded_synthesis_ready"
            ]
            and response[
                "grounded_synthesis_execution_enabled"
            ]
        ):

            response[
                "trace"
            ][
                "grounded_synthesis_calls"
            ] = 1

            response[
                "grounded_synthesis"
            ] = (
                execute_grounded_synthesis(
                    answers[
                        "query"
                    ],

                    grounded_evidence_bundle,

                    grounded_synthesis_ready=
                        True,
                )
            )

    response[
        "itrs"
    ] = calculate_itrs(
        response,
        answers,
    )


    return response





def run_conversation(request):
    """Run the existing workflow and attach a normalized final outcome."""

    response = _run_conversation_core(
        request
    )


    if not isinstance(
        response,
        dict,
    ):
        raise TypeError(
            "Conversation workflow must return a dictionary."
        )


    response[
        "final_outcome"
    ] = build_final_outcome(
        response
    )


    response[
        "evidence_contract"
    ] = build_evidence_contract(
        response
    )


    return response


@router.post("/assistant/turn", tags=["Assistant"])
def conversation_turn(request: ConversationRequest):
    try:
        return run_conversation(request)
    except FileNotFoundError as error:
        raise HTTPException(404, "Required prepared manual or evidence index was not found.") from error
    except PlannerUnavailable as error:
        raise HTTPException(503, str(error)) from error
    except (ValueError, PermissionError) as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        logger.exception("Assistant conversation failed")
        raise HTTPException(500, "Conversation failed; check the backend terminal.") from error



@router.get(
    "/assistant/source-page/{document_id}/{page_number}",
    include_in_schema=False,
)
def assistant_source_page(
    document_id: str,
    page_number: int,
):
    """
    Serve one verified registered source-PDF page.

    The browser never supplies a filesystem path.
    """
    try:
        preview = build_registered_source_page(
            document_id,
            page_number,
        )

    except FileNotFoundError as error:
        raise HTTPException(
            404,
            "Registered source document or PDF was not found.",
        ) from error

    except ValueError as error:
        raise HTTPException(
            422,
            str(error),
        ) from error

    except PermissionError as error:
        raise HTTPException(
            403,
            "Source-page preview was rejected by provenance validation.",
        ) from error

    except Exception as error:
        logger.exception(
            "Source-page preview failed"
        )
        raise HTTPException(
            500,
            "Source-page preview failed; check the backend terminal.",
        ) from error

    return Response(
        content=preview.content,
        media_type="application/pdf",
        headers={
            "Cache-Control":
                "private, no-store",
            "Content-Disposition":
                (
                    "inline; "
                    f'filename="source-page-{preview.page_number}.pdf"'
                ),
            "X-Content-Type-Options":
                "nosniff",
        },
    )


@router.get("/assistant", include_in_schema=False)
def assistant_page():
    return FileResponse(Path(__file__).resolve().parents[1] / "static/assistant_v2.html",
                        media_type="text/html", headers={"Cache-Control": "no-store"})
