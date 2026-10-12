"""Local Ollama implementation of the grounded synthesis interface."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.grounded_synthesis import (
    GROUNDING_SYSTEM_INSTRUCTIONS,
    GroundedSynthesisRequest,
    GroundedSynthesisResult,
    build_grounded_prompt,
)


class GroundedSynthesisProviderError(
    RuntimeError
):
    """Raised when the configured synthesis provider fails."""


class OllamaGroundedSynthesizer:
    """Grounded synthesis using the local Ollama service."""

    def __init__(
        self,
        *,
        model: str = "llama3.2:3b",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 180,
    ):
        if (
            not isinstance(model, str)
            or not model.strip()
        ):
            raise ValueError(
                "Ollama model must be a non-empty string."
            )

        if (
            not isinstance(base_url, str)
            or not base_url.strip()
        ):
            raise ValueError(
                "Ollama base_url must be a non-empty string."
            )

        if (
            type(timeout_seconds) is not int
            or timeout_seconds < 1
            or timeout_seconds > 600
        ):
            raise ValueError(
                "timeout_seconds must be an integer from 1 to 600."
            )

        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _post_json(
        self,
        endpoint: str,
        payload: dict,
    ) -> dict:

        request = Request(
            self.base_url + endpoint,
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Content-Type":
                    "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:

                raw = response.read().decode(
                    "utf-8"
                )

        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
        ) as error:
            raise GroundedSynthesisProviderError(
                "Ollama grounded synthesis request failed."
            ) from error

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as error:
            raise GroundedSynthesisProviderError(
                "Ollama returned invalid JSON."
            ) from error

        if not isinstance(decoded, dict):
            raise GroundedSynthesisProviderError(
                "Ollama response must be a JSON object."
            )

        return decoded

    def synthesize(
        self,
        request: GroundedSynthesisRequest,
    ) -> GroundedSynthesisResult:

        if not isinstance(
            request,
            GroundedSynthesisRequest,
        ):
            raise TypeError(
                "request must be a GroundedSynthesisRequest."
            )

        # GroundedSynthesisRequest itself enforces:
        #
        # grounded_synthesis_ready == True
        #
        # Therefore the provider cannot be called through this
        # interface before the grounding boundary has passed.

        grounded_prompt = (
            build_grounded_prompt(
                request
            )
        )

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content":
                        GROUNDING_SYSTEM_INSTRUCTIONS,
                },
                {
                    "role": "user",
                    "content":
                        grounded_prompt,
                },
            ],
            "options": {
                "temperature": 0,
            },
        }

        response = self._post_json(
            "/api/chat",
            payload,
        )

        message = response.get(
            "message"
        )

        if not isinstance(
            message,
            dict,
        ):
            raise GroundedSynthesisProviderError(
                "Ollama response has no message object."
            )

        content = message.get(
            "content"
        )

        if (
            not isinstance(content, str)
            or not content.strip()
        ):
            raise GroundedSynthesisProviderError(
                "Ollama returned an empty synthesis response."
            )

        return GroundedSynthesisResult(
            answer_text=content.strip(),
            provider=self.provider_name,
            model=self.model,
        )