"""Narrow adapter to the existing Local Agent Work Center API.

This is intentionally the only future execution integration point. It does
not reimplement validators, budgets, model calls, or write logic. Tests inject
a fake bridge and never make HTTP requests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.request import Request, urlopen

from .contracts import TaskRequest


class WorkCenterBridge(Protocol):
    def run(self, request: TaskRequest) -> dict[str, object]: ...


@dataclass
class HttpWorkCenterBridge:
    base_url: str = "http://127.0.0.1:5001"
    timeout_seconds: float = 900.0

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec: loopback base URL is configured by operator
            return json.loads(response.read().decode("utf-8"))

    def run(self, request: TaskRequest) -> dict[str, object]:
        # Configure the existing engine before the message. This uses its own
        # cloud confirmation, redaction, budget, validator, and test pathways.
        self._post("/api/settings", {
            "chat_model": request.chat_model,
            "builder_model": request.builder_model,
            "model_mode": "hybrid",
        })
        self._post("/api/root", {"path": request.project_root})
        return self._post("/api/message", {"message": request.request})

