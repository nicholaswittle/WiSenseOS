from __future__ import annotations

import json

import pytest

from wisense_os.model_adapter import ModelAdapterError, OllamaChatAdapter, redact_text


def test_adapter_redacts_prompt_before_using_loopback_transport() -> None:
    captured: dict[str, object] = {}

    def transport(request, timeout: float) -> bytes:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return b'{"message":{"content":"{\\"files\\":[]}"}}'

    reply = OllamaChatAdapter(transport=transport).complete(
        [{"role": "user", "content": "API_KEY=super-secret\nPlease plan this."}],
        model="gemma4:31b-cloud",
    )

    assert reply == '{"files":[]}'
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["messages"][0]["content"] == "API_KEY=[REDACTED]\nPlease plan this."
    assert captured["payload"]["format"] == {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["files"],
        "additionalProperties": False,
    }


def test_redactor_handles_unquoted_environment_style_assignments() -> None:
    assert redact_text("DB_PASSWORD=s3cr3t\ntoken = fetch_token()") == "DB_PASSWORD=[REDACTED]\ntoken = fetch_token()"


def test_adapter_rejects_missing_model_content() -> None:
    with pytest.raises(ModelAdapterError, match="no chat content"):
        OllamaChatAdapter(transport=lambda _request, _timeout: b"{}").complete([], model="glm-5.2:cloud")


def test_adapter_discovers_only_names_reported_by_loopback_ollama() -> None:
    adapter = OllamaChatAdapter(transport=lambda request, _timeout: (
        b'{"models":[{"name":"gemma4:31b-cloud"},{"name":"glm-5.2:cloud"}]}'
        if request.full_url.endswith("/api/tags") else b"{}"
    ))

    assert adapter.available_models() == {"gemma4:31b-cloud", "glm-5.2:cloud"}


def test_adapter_reports_no_available_models_when_loopback_is_unreachable() -> None:
    def unavailable(_request, _timeout: float) -> bytes:
        raise OSError("offline")

    assert OllamaChatAdapter(transport=unavailable).available_models() == set()
