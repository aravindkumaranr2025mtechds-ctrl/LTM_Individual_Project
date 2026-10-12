"""Local Ollama model adapter for bounded agent planning.

The model receives tool metadata and AgentState only.
It returns one schema-constrained AgentDecision.
It never receives executable Python functions.
"""

import json
import urllib.error
import urllib.request

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.model_adapter import (
    AgentModelAdapter,
)

from app.services.agentic.tool_registry import (
    ToolSpec,
)

from app.services.agentic.planning_context import (
    build_tool_readiness,
)



_SYSTEM_PROMPT = """You are the bounded planning component of an
industrial troubleshooting assistant.

Your responsibility is to select exactly ONE safe next action.

STRICT RULES:

1. Never diagnose a machine.

2. Never invent or assume measurements, alarm numbers, alarm scopes,
   inspection results, machine conditions, or technical observations.

3. known_facts contains the ONLY technical facts that may be supplied
   as tool arguments.

4. If a required fact is absent from known_facts, do NOT call the tool.

5. For a missing alarm number or alarm scope, prefer ask_clarification.

6. For a missing physical observation that a technician could reasonably
   check or measure, ask_clarification or suggest_inspection.

7. A suggested inspection is NOT an observed fact. Its result remains
   unknown until explicitly reported.

8. Use only tools listed in allowed_tools.

9. For call_tool, copy argument values exactly from known_facts.
   Never rewrite or infer them.

10. Never request machine control, parameter changes, resets, restarts,
    shutdowns, protection bypasses, or automatic physical execution.

11. If the request is outside the available tools, choose abstain.

12. Use return_information only when information is already supported
    by the supplied state or previous tool observation.

Return only the JSON object required by the response schema.
"""


class OllamaAgentModelAdapter(
    AgentModelAdapter
):
    """Provider adapter using Ollama's local /api/chat endpoint."""

    def __init__(
        self,
        model="llama3.2:3b",
        base_url="http://127.0.0.1:11434",
        timeout_seconds=180,
    ):
        self._model = model
        self._base_url = (
            base_url.rstrip("/")
        )
        self._timeout_seconds = (
            timeout_seconds
        )

    @property
    def provider_name(self):
        return "ollama"

    @property
    def model_name(self):
        return self._model

    def _post_json(
        self,
        endpoint,
        payload,
    ):
        request = urllib.request.Request(
            self._base_url + endpoint,
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Content-Type":
                    "application/json"
            },
            method="POST",
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:

                return json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

        except urllib.error.HTTPError as error:

            detail = error.read().decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                f"Ollama HTTP {error.code}: {detail}"
            ) from error

        except urllib.error.URLError as error:

            raise RuntimeError(
                "Cannot reach the local Ollama service."
            ) from error

    def _build_planning_input(
        self,
        state,
        allowed_tools,
    ):
        """Build deterministic context presented to the LLM planner."""

        tool_metadata = []

        for spec in allowed_tools:

            tool_metadata.append(
                {
                    "name":
                        spec.name,

                    "description":
                        spec.description,

                    "required_explicit_fields":
                        spec.required_explicit_fields,

                    "safety_notes":
                        spec.safety_notes,
                }
            )

        tool_readiness = (
            build_tool_readiness(
                state,
                allowed_tools,
            )
        )

        last_tool_name = None
        last_result_status = None
        supported_result_available = False

        if (
            isinstance(
                state.last_tool_result,
                dict,
            )
        ):

            last_tool_name = (
                state.last_tool_result.get(
                    "tool_name"
                )
            )

            outer_result = (
                state.last_tool_result.get(
                    "result"
                )
            )

            if isinstance(
                outer_result,
                dict,
            ):

                inner_result = (
                    outer_result.get(
                        "result"
                    )
                )

                if isinstance(
                    inner_result,
                    dict,
                ):

                    last_result_status = (
                        inner_result.get(
                            "status"
                        )
                    )

                elif isinstance(
                    outer_result.get(
                        "status"
                    ),
                    str,
                ):

                    last_result_status = (
                        outer_result.get(
                            "status"
                        )
                    )

        if last_result_status in {
            "answer_supported",
            "description_supported",
            "source_information",
        }:
            supported_result_available = True

        return {
            "agent_state":
                state.model_dump(
                    mode="json"
                ),

            "allowed_tools":
                tool_metadata,

            "tool_readiness":
                tool_readiness,

            "post_observation_context": {
                "has_tool_observation":
                    state.last_tool_result
                    is not None,

                "last_tool_name":
                    last_tool_name,

                "last_result_status":
                    last_result_status,

                "supported_result_available":
                    supported_result_available,
            },

            "decision_policy": [
                (
                    "Never ask for a requested_fact that already "
                    "exists in agent_state.known_facts."
                ),

                (
                    "If the user's request clearly matches a tool "
                    "and tool_readiness says ready_for_call=true, "
                    "prefer call_tool when no suitable previous "
                    "tool observation exists."
                ),

                (
                    "If the relevant tool has missing_required_fields, "
                    "ask for one of those fields rather than guessing it."
                ),

                (
                    "For call_tool, copy explicit_arguments exactly "
                    "from tool_readiness."
                ),

                (
                    "Never repeat the same protected tool call merely "
                    "because the tool remains ready_for_call."
                ),

                (
                    "If post_observation_context.has_tool_observation "
                    "is true, examine that observation before selecting "
                    "another tool action."
                ),

                (
                    "If post_observation_context."
                    "supported_result_available is true and the previous "
                    "tool result answers the user's current goal, choose "
                    "return_information."
                ),

                (
                    "Do not call post_observation_context.last_tool_name "
                    "again unless genuinely new explicit facts would "
                    "change the tool request."
                ),

                (
                    "A successful evidence observation should normally "
                    "lead to return_information rather than repeated "
                    "retrieval."
                ),

                (
                    "Do not turn a suggested inspection into an "
                    "observed technical fact."
                ),
            ],

            "planning_instruction": (
                "Select exactly one next action. "
                "First inspect post_observation_context. "
                "If supported evidence from a previous protected tool "
                "already answers the current request, return_information. "
                "Otherwise select the safest necessary next action."
            ),

            "response_contract": {
                "required_field_names": [
                    "action",
                    "reason",
                    "tool_name",
                    "tool_arguments",
                    "requested_fact",
                    "question",
                    "suggestion",
                ],

                "allowed_actions": [
                    "ask_clarification",
                    "suggest_inspection",
                    "call_tool",
                    "return_information",
                    "abstain",
                ],

                "rules": [
                    (
                        "Use field name action, never next_action."
                    ),

                    (
                        "Use field name reason, never rationale."
                    ),

                    (
                        "Always include all seven fields."
                    ),

                    (
                        "Use null for fields that do not apply."
                    ),

                    (
                        "tool_arguments must always be a JSON object."
                    ),
                ],

                "example_ask_clarification": {
                    "action":
                        "ask_clarification",

                    "reason":
                        "A required explicit fact is missing.",

                    "tool_name":
                        None,

                    "tool_arguments":
                        {},

                    "requested_fact":
                        "alarm_scope",

                    "question":
                        "Which alarm scope should be checked?",

                    "suggestion":
                        None,
                },

                "example_call_tool": {
                    "action":
                        "call_tool",

                    "reason":
                        "The required explicit fact is available "
                        "and no previous observation answers the goal.",

                    "tool_name":
                        "siemens_logfile",

                    "tool_arguments": {
                        "alarm_scope":
                            "61352_or_61353"
                    },

                    "requested_fact":
                        None,

                    "question":
                        None,

                    "suggestion":
                        None,
                },

                "example_return_information": {
                    "action":
                        "return_information",

                    "reason":
                        "Verified protected evidence already "
                        "answers the user's request.",

                    "tool_name":
                        None,

                    "tool_arguments":
                        {},

                    "requested_fact":
                        None,

                    "question":
                        None,

                    "suggestion":
                        None,
                },
            },
        }



    def decide(
        self,
        state: AgentState,
        allowed_tools: list[ToolSpec],
    ) -> AgentDecision:

        payload = {
            "model":
                self._model,

            "stream":
                False,

            "format":
                AgentDecision.
                model_json_schema(),

            "options": {
                "temperature": 0,
            },

            "messages": [
                {
                    "role":
                        "system",

                    "content":
                        _SYSTEM_PROMPT,
                },
                {
                    "role":
                        "user",

                    "content":
                        json.dumps(
                            self._build_planning_input(
                                state,
                                allowed_tools,
                            ),
                            indent=2,
                            ensure_ascii=False,
                        ),
                },
            ],
        }

        try:
            response = self._post_json(
                "/api/chat",
                payload,
            )

        except RuntimeError as error:

            message = str(
                error
            ).lower()

            if (
                "failed to parse grammar"
                not in message
            ):
                raise

            # Some Ollama / llama.cpp builds cannot compile every
            # valid Pydantic JSON Schema into a sampling grammar.
            #
            # Fall back only at the generation-format layer.
            # The returned JSON is still validated below using the
            # full AgentDecision Pydantic model, and subsequent
            # controller/grounding guards remain unchanged.
            fallback_payload = dict(
                payload
            )

            fallback_payload[
                "format"
            ] = "json"

            response = self._post_json(
                "/api/chat",
                fallback_payload,
            )

        message = response.get(
            "message"
        )

        if not isinstance(
            message,
            dict,
        ):
            raise RuntimeError(
                "Ollama response does not contain message."
            )

        content = message.get(
            "content"
        )

        if not isinstance(
            content,
            str,
        ):
            raise RuntimeError(
                "Ollama response does not contain valid content."
            )

        try:

            return (
                AgentDecision.
                model_validate_json(
                    content
                )
            )

        except Exception as error:

            raise RuntimeError(
                "Ollama returned an invalid AgentDecision."
            ) from error
