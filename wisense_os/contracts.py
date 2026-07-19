"""Small, JSON-serializable task contracts shared by future clients."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class ProviderKind(StrEnum):
    LOCAL = "local"
    CLOUD = "cloud"


class RunMode(StrEnum):
    TALK_ONLY = "talk_only"
    ASK_BEFORE_CHANGES = "ask_before_changes"
    LOCAL_AUTOPILOT = "local_autopilot"


class TaskStatus(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: ProviderKind
    roles: tuple[str, ...]
    available: bool
    supervised_testing_only: bool
    future_local_target: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider.value,
            "roles": list(self.roles),
            "available": self.available,
            "supervised_testing_only": self.supervised_testing_only,
            "future_local_target": self.future_local_target,
        }


@dataclass(frozen=True)
class TaskRequest:
    request: str
    project_root: str
    mode: RunMode
    chat_model: str
    builder_model: str


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    request: TaskRequest
    status: TaskStatus
    reason: str | None = None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["request"]["mode"] = self.request.mode.value
        return data


@dataclass(frozen=True)
class TaskEvent:
    task_id: str
    sequence: int
    kind: str
    detail: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
