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
    with pytest.raises(ModelAdapterError, match="no chat message"):
        OllamaChatAdapter(transport=lambda _request, _timeout: b"{}").complete([], model="glm-5.2:cloud")
    with pytest.raises(ModelAdapterError, match="no chat content"):
        OllamaChatAdapter(
            transport=lambda _request, _timeout: b'{"message":{"role":"assistant","content":""}}',
        ).complete([], model="glm-5.2:cloud")


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


def test_complete_with_tools_returns_tool_calls_without_requiring_content() -> None:
    payload = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "function": {
                    "name": "grep_files",
                    "arguments": {"pattern": "def totals"},
                },
            }],
        },
    }

    def transport(request, timeout: float) -> bytes:
        body = json.loads(request.data.decode("utf-8"))
        assert "tools" in body
        assert body["tools"][0]["function"]["name"] == "glob_files"
        assert "format" not in body
        return json.dumps(payload).encode("utf-8")

    message = OllamaChatAdapter(transport=transport).complete_with_tools(
        [{"role": "user", "content": "find totals"}],
        model="qwen2.5-coder:7b",
        tools=[{
            "type": "function",
            "function": {"name": "glob_files", "parameters": {"type": "object"}},
        }],
    )
    assert message["tool_calls"][0]["function"]["name"] == "grep_files"
    assert message["content"] == ""


def test_complete_with_tools_redacts_secrets_in_history() -> None:
    captured: dict[str, object] = {}

    def transport(request, timeout: float) -> bytes:
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return b'{"message":{"role":"assistant","content":"looked at billing.py"}}'

    OllamaChatAdapter(transport=transport).complete_with_tools(
        [
            {"role": "user", "content": "API_KEY=leak-me"},
            {"role": "tool", "name": "read_file", "content": "SECRET_TOKEN=abc"},
        ],
        model="qwen2.5-coder:7b",
        tools=[],
    )
    messages = captured["payload"]["messages"]
    assert messages[0]["content"] == "API_KEY=[REDACTED]"
    assert messages[1]["content"] == "SECRET_TOKEN=[REDACTED]"
