"""WiSense-owned Ollama chat adapter with prompt redaction.

The adapter is transport-only: policy and approval remain in the coordinator.
It supports current Ollama Cloud profiles and a future local Gemma profile
through the same loopback daemon endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Callable, Protocol
from urllib.request import Request, urlopen


_SECRET_ASSIGNMENT = re.compile(
    r"(?im)\b([A-Z][A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASSWD)|"
    r"(?:api[_-]?key|token|secret|password|passwd))\b\s*([:=])\s*([^\s#]+)"
)

_PATCH_RESPONSE_SCHEMA = {
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


class ModelAdapterError(RuntimeError):
    """The local Ollama service did not return a usable model response."""


class ChatModel(Protocol):
    def complete(self, messages: list[dict[str, str]], *, model: str, timeout_seconds: float = 120.0) -> str: ...


def redact_text(text: str) -> str:
    """Remove common assignment-style secrets while preserving surrounding context."""
    def replace(match: re.Match[str]) -> str:
        # A code expression such as ``token = fetch_token()`` is context, not
        # a literal credential; redact only literal-looking assignments.
        if "(" in match.group(3) or ")" in match.group(3):
            return match.group(0)
        return f"{match.group(1)}{match.group(2)}[REDACTED]"

    return _SECRET_ASSIGNMENT.sub(replace, text)


def redact_messages(messages: list[dict]) -> list[dict]:
    """Redact string contents; preserve tool_calls / non-string fields."""
    redacted: list[dict] = []
    for message in messages:
        row = dict(message)
        content = row.get("content")
        if isinstance(content, str):
            row["content"] = redact_text(content)
        redacted.append(row)
    return redacted


@dataclass
class OllamaChatAdapter:
    base_url: str = "http://127.0.0.1:11434"
    transport: Callable[[Request, float], bytes] | None = None

    def _chat(
        self,
        messages: list[dict],
        *,
        model: str,
        timeout_seconds: float = 120.0,
        structured_patch: bool = False,
        tools: list[dict] | None = None,
    ) -> dict:
        payload: dict[str, object] = {
            "model": model,
            "messages": redact_messages(messages),
            "stream": False,
        }
        if structured_patch:
            payload["format"] = _PATCH_RESPONSE_SCHEMA
        if tools is not None:
            payload["tools"] = tools
        request = Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            raw = (self.transport or _urlopen_bytes)(request, timeout_seconds)
            response = json.loads(raw.decode("utf-8"))
            message = response.get("message")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            raise ModelAdapterError("Ollama chat request failed") from exc
        if not isinstance(message, dict):
            raise ModelAdapterError("Ollama returned no chat message")
        return message

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        timeout_seconds: float = 120.0,
        structured_patch: bool = True,
    ) -> str:
        message = self._chat(
            messages,
            model=model,
            timeout_seconds=timeout_seconds,
            structured_patch=structured_patch,
        )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ModelAdapterError("Ollama returned no chat content")
        return content

    def complete_text(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        timeout_seconds: float = 120.0,
    ) -> str:
        """Unstructured chat completion for talk-only / explain paths."""
        return self.complete(
            messages, model=model, timeout_seconds=timeout_seconds, structured_patch=False,
        )

    def complete_with_tools(
        self,
        messages: list[dict],
        *,
        model: str,
        tools: list[dict] | None = None,
        timeout_seconds: float = 120.0,
    ) -> dict:
        """Return the raw assistant message, including optional tool_calls.

        Used by agentic read-only explore. Callers must never treat this as a
        write authority — tools are dispatched by exploration_tools only.
        """
        message = self._chat(
            messages,
            model=model,
            timeout_seconds=timeout_seconds,
            structured_patch=False,
            tools=tools,
        )
        content = message.get("content")
        tool_calls = message.get("tool_calls")
        has_tools = isinstance(tool_calls, list) and bool(tool_calls)
        if has_tools:
            return {
                "role": message.get("role", "assistant"),
                "content": content if isinstance(content, str) else "",
                "tool_calls": tool_calls,
            }
        if not isinstance(content, str) or not content.strip():
            raise ModelAdapterError("Ollama returned no chat content")
        return {
            "role": message.get("role", "assistant"),
            "content": content,
        }

    def available_models(self, timeout_seconds: float = 2.0) -> set[str]:
        """Return names reported by the loopback Ollama runtime, or none on failure."""
        request = Request(f"{self.base_url.rstrip('/')}/api/tags", method="GET")
        try:
            raw = (self.transport or _urlopen_bytes)(request, timeout_seconds)
            response = json.loads(raw.decode("utf-8"))
            models = response.get("models")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return set()
        if not isinstance(models, list):
            return set()
        return {
            row["name"] for row in models
            if isinstance(row, dict) and isinstance(row.get("name"), str) and row["name"]
        }


def _urlopen_bytes(request: Request, timeout_seconds: float) -> bytes:
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec: loopback operator-configured endpoint
        return response.read()
