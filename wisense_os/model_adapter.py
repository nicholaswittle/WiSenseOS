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

    def complete(self, messages: list[dict[str, str]], *, model: str, timeout_seconds: float = 120.0) -> str:
        payload = json.dumps({
            "model": model,
            "messages": redact_messages(messages),
            "stream": False,
        }).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=payload,
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


def _urlopen_bytes(request: Request, timeout_seconds: float) -> bytes:
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec: loopback operator-configured endpoint
        return response.read()
