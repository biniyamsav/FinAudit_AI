"""Groq-backed implementation of the provider-independent LLM contract.

Groq exposes an OpenAI-compatible chat completions API, so the official
``openai`` SDK is pointed at Groq's base URL rather than adding a second
vendor SDK.  The rest of the application only ever sees
``LLMProviderProtocol``.
"""

import os
from typing import Any

import httpx
import openai
from openai import OpenAI

from app.llm.protocol import LLMError

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TEMPERATURE = 0.0


class GroqLLMProvider:
    """Generates audit text through Groq's OpenAI-compatible endpoint.

    Configuration is read from the environment so credentials never reach
    source code or Git:

    * ``GROQ_API_KEY`` -- required; the provider refuses to construct
      without it rather than failing later inside a request.
    * ``LLM_MODEL`` -- optional model override, defaulting to
      ``llama-3.3-70b-versatile``.

    ``generate`` defaults to ``temperature=0.0`` because financial audit
    output must be deterministic: rerunning the same evidence and prompt
    has to yield the same answer, otherwise a reviewer cannot reproduce or
    defend a finding.  Only callers doing explicitly creative work should
    raise it.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        base_url: str = GROQ_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Build a provider from explicit values or, by default, the environment.

        ``http_client`` exists so tests can inject an ``httpx.MockTransport``
        and assert on the outgoing request without touching the network.
        """
        key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY", "")
        if not key or not key.strip():
            # Fail fast at startup with an actionable, credential-free message
            # instead of a confusing 401 deep inside the agent workflow.
            raise LLMError(
                "GROQ_API_KEY is not set. Export GROQ_API_KEY to enable the "
                "external LLM provider, or use the mock provider."
            )

        resolved_model = (
            model if model is not None else os.environ.get("LLM_MODEL", "")
        )
        self.model = resolved_model.strip() or DEFAULT_MODEL
        self.base_url = base_url

        self._client = OpenAI(
            api_key=key.strip(),
            base_url=base_url,
            timeout=timeout,
            # The SDK only retries transient statuses (408/429/5xx), never 401.
            max_retries=max_retries,
            http_client=http_client,
        )

    def generate(
        self, system_prompt: str, user_prompt: str, temperature: float = DEFAULT_TEMPERATURE
    ) -> str:
        """Return Groq's completion for the two-part prompt.

        Raises :class:`LLMError` for every failure mode -- missing key,
        unreachable host, rejected credentials, rate limiting, and empty
        responses -- so callers handle one exception type and never see SDK
        internals.  The API key is never included in an error message.
        """
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
        except openai.AuthenticationError as error:
            raise LLMError("Groq rejected the API key (authentication failed).") from error
        except openai.RateLimitError as error:
            raise LLMError("Groq rate limit exceeded; retry later.") from error
        except (openai.APITimeoutError, openai.APIConnectionError) as error:
            # APITimeoutError subclasses APIConnectionError; both mean we
            # never got a usable answer off the wire.
            raise LLMError(
                "Could not reach the Groq API (network error)."
            ) from error
        except openai.APIStatusError as error:
            raise LLMError(f"Groq API returned HTTP {error.status_code}.") from error
        except openai.APIError as error:
            raise LLMError("Groq API request failed.") from error

        return _completion_text(completion)


def _completion_text(completion: Any) -> str:
    """Extract the assistant message, treating an empty reply as an error.

    A completion with no choices (or a null ``content``, which Groq returns
    for some tool-only replies) is not an answer the audit workflow can
    cite, so it surfaces as :class:`LLMError` rather than ``""``, which
    would silently look like a successful empty response downstream.
    """
    choices = getattr(completion, "choices", None) or []
    if not choices:
        raise LLMError("Groq returned no completion choices.")

    content = choices[0].message.content
    if content is None:
        raise LLMError("Groq returned a completion with empty content.")

    return content
