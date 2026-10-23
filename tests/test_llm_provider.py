import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.llm.protocol import LLMError, LLMProviderProtocol
from app.llm.providers.groq_provider import (
    DEFAULT_MODEL,
    GROQ_BASE_URL,
    GroqLLMProvider,
)

# Placeholder credential: no test touches the network or a real key.
FAKE_KEY = "gsk_placeholder_key_never_a_real_one"


def _completion_body(content: str | None = "TOTAL REVENUE 1500") -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": DEFAULT_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _provider(
    handler: Callable[[httpx.Request], httpx.Response], **kwargs: Any
) -> GroqLLMProvider:
    """Build a provider whose traffic is served by a local mock transport."""
    return GroqLLMProvider(
        api_key=FAKE_KEY,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        **kwargs,
    )


# --------------------------------------------------------------------------
# Contract and configuration
# --------------------------------------------------------------------------


def test_provider_satisfies_the_protocol():
    provider = _provider(lambda request: httpx.Response(200, json=_completion_body()))
    assert isinstance(provider, LLMProviderProtocol)


def test_missing_api_key_is_rejected_at_construction(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqLLMProvider()


def test_blank_api_key_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GROQ_API_KEY", "   ")
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqLLMProvider()


def test_error_messages_never_contain_the_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMError) as caught:
        GroqLLMProvider()
    assert "gsk_" not in str(caught.value)


def test_default_model_is_llama_3_3_70b():
    provider = _provider(lambda request: httpx.Response(200, json=_completion_body()))
    assert provider.model == "llama-3.3-70b-versatile"
    assert provider.model == DEFAULT_MODEL


def test_llm_model_environment_variable_overrides_the_default(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LLM_MODEL", "llama-3.1-8b-instant")
    provider = _provider(lambda request: httpx.Response(200, json=_completion_body()))
    assert provider.model == "llama-3.1-8b-instant"


def test_explicit_model_argument_beats_the_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("LLM_MODEL", "llama-3.1-8b-instant")
    provider = _provider(
        lambda request: httpx.Response(200, json=_completion_body()),
        model="explicit-model",
    )
    assert provider.model == "explicit-model"


# --------------------------------------------------------------------------
# Request shape
# --------------------------------------------------------------------------


def test_generate_posts_both_prompts_to_groq_with_deterministic_temperature():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion_body("Revenue is 1500"))

    provider = _provider(handler)
    result = provider.generate("You are an audit reviewer.", "What is revenue?")

    assert result == "Revenue is 1500"
    assert captured["url"] == f"{GROQ_BASE_URL}/chat/completions"
    assert captured["body"]["model"] == DEFAULT_MODEL
    assert captured["body"]["temperature"] == 0.0
    assert captured["body"]["messages"] == [
        {"role": "system", "content": "You are an audit reviewer."},
        {"role": "user", "content": "What is revenue?"},
    ]


def test_explicit_temperature_is_passed_through():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion_body("ok"))

    provider = _provider(handler)
    provider.generate("sys", "usr", temperature=0.7)
    assert captured["body"]["temperature"] == 0.7


# --------------------------------------------------------------------------
# Failure handling -- every path surfaces as LLMError
# --------------------------------------------------------------------------


def test_http_401_is_wrapped_and_does_not_leak_the_key():
    provider = _provider(
        lambda request: httpx.Response(
            401, json={"error": {"message": "Invalid API Key"}}
        )
    )
    with pytest.raises(LLMError) as caught:
        provider.generate("sys", "usr")
    assert FAKE_KEY not in str(caught.value)


def test_network_failure_is_wrapped():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(handler, max_retries=0)
    with pytest.raises(LLMError, match="network"):
        provider.generate("sys", "usr")


def test_rate_limit_is_wrapped():
    provider = _provider(
        lambda request: httpx.Response(
            429, json={"error": {"message": "rate limited"}}
        ),
        max_retries=0,
    )
    with pytest.raises(LLMError, match="rate limit"):
        provider.generate("sys", "usr")


def test_server_error_reports_the_status_code():
    provider = _provider(
        lambda request: httpx.Response(500, json={"error": {"message": "boom"}}),
        max_retries=0,
    )
    with pytest.raises(LLMError, match="HTTP 500"):
        provider.generate("sys", "usr")


def test_completion_with_no_choices_is_an_error():
    body = _completion_body()
    body["choices"] = []
    provider = _provider(lambda request: httpx.Response(200, json=body))
    with pytest.raises(LLMError, match="no completion choices"):
        provider.generate("sys", "usr")


def test_completion_with_null_content_is_an_error():
    body = _completion_body(content=None)
    provider = _provider(lambda request: httpx.Response(200, json=body))
    with pytest.raises(LLMError, match="empty content"):
        provider.generate("sys", "usr")
