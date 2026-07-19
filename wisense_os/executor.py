"""Native WiSense task-execution boundary.

No legacy project, web server, or global conversation state is reachable from
this module.  The first implementation fails closed until the plan-bound patch
executor is installed in WiSense itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import TaskRequest


class TaskExecutor(Protocol):
    def run(self, request: TaskRequest) -> dict[str, object]: ...

    def continue_conversation(self, request: TaskRequest, message: str) -> dict[str, object]: ...


@dataclass(frozen=True)
class NativeTaskExecutor:
    """Fail closed until WiSense owns its model-to-patch implementation."""

    def run(self, request: TaskRequest) -> dict[str, object]:
        return {
            "blocked": True,
            "reason": "native plan-bound patch execution is not enabled yet",
        }

    def continue_conversation(self, request: TaskRequest, message: str) -> dict[str, object]:
        return {
            "blocked": True,
            "reason": "native provider continuation is not enabled yet",
        }
