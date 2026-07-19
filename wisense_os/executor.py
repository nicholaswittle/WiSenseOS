"""Native WiSense task-execution boundary.

No legacy project, web server, or global conversation state is reachable from
this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .contracts import TaskRequest
from .plan import TaskPlan


class TaskExecutor(Protocol):
    def propose(self, request: TaskRequest, plan: TaskPlan) -> dict[str, object]: ...

    def apply_proposal(
        self, request: TaskRequest, plan: TaskPlan, files: Mapping[str, str],
    ) -> dict[str, object]: ...

    def run(self, request: TaskRequest, plan: TaskPlan) -> dict[str, object]: ...

    def chat(self, request: TaskRequest) -> dict[str, object]: ...

    def continue_conversation(self, request: TaskRequest, message: str) -> dict[str, object]: ...


@dataclass(frozen=True)
class NativeTaskExecutor:
    """Fail-closed stand-in used only when a real executor is not injected."""

    def propose(self, request: TaskRequest, plan: TaskPlan) -> dict[str, object]:
        return {"blocked": True, "reason": "native plan-bound proposal is not enabled"}

    def apply_proposal(
        self, request: TaskRequest, plan: TaskPlan, files: Mapping[str, str],
    ) -> dict[str, object]:
        return {"blocked": True, "reason": "native plan-bound apply is not enabled"}

    def run(self, request: TaskRequest, plan: TaskPlan) -> dict[str, object]:
        return {"blocked": True, "reason": "native plan-bound patch execution is not enabled"}

    def chat(self, request: TaskRequest) -> dict[str, object]:
        return {"blocked": True, "reason": "native talk-only chat is not enabled"}

    def continue_conversation(self, request: TaskRequest, message: str) -> dict[str, object]:
        return {"blocked": True, "reason": "native provider continuation is not enabled"}
