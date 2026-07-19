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


def redact_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{**message, "content": redact_text(message.get("content", ""))} for message in messages]


@dataclass
class OllamaChatAdapter:
    base_url: str = "http://127.0.0.1:11434"
    transport: Callable[[Request, float], bytes] | None = None

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        timeout_seconds: float = 120.0,
        structured_patch: bool = True,
    ) -> str:
        payload: dict[str, object] = {
            "model": model,
            "messages": redact_messages(messages),
            "stream": False,
        }
        if structured_patch:
            payload["format"] = _PATCH_RESPONSE_SCHEMA
        request = Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            raw = (self.transport or _urlopen_bytes)(request, timeout_seconds)
            response = json.loads(raw.decode("utf-8"))
            content = response.get("message", {}).get("content")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            raise ModelAdapterError("Ollama chat request failed") from exc
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
