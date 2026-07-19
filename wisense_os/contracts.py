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
    EXPLORING = "exploring"
    BLOCKED = "blocked"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    WAITING_FOR_PROVIDER_INPUT = "waiting_for_provider_input"
    CANCELED = "canceled"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    display_name: str
    root: str
    local_autopilot_trusted: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "display_name": self.display_name,
            "root": self.root,
            "local_autopilot_trusted": self.local_autopilot_trusted,
        }


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: ProviderKind
    roles: tuple[str, ...]
    available: bool
    supervised_testing_only: bool
    future_local_target: bool = False

    @property
    def is_cloud(self) -> bool:
        return self.provider is ProviderKind.CLOUD

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
    offline: bool = False


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


@dataclass(frozen=True)
class TaskProposal:
    """Validated write proposal awaiting digest-bound approval."""

    digest: str
    files: dict[str, str]
    diffs: dict[str, str]
    summary: str

    def to_json(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "files": dict(self.files),
            "diffs": dict(self.diffs),
            "summary": self.summary,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "TaskProposal":
        files = payload.get("files")
        diffs = payload.get("diffs")
        digest = payload.get("digest")
        summary = payload.get("summary")
        if not isinstance(digest, str) or not digest:
            raise ValueError("proposal digest is required")
        if not isinstance(summary, str):
            raise ValueError("proposal summary is required")
        if not isinstance(files, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in files.items()
        ):
            raise ValueError("proposal files must be a string map")
        if not isinstance(diffs, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in diffs.items()
        ):
            raise ValueError("proposal diffs must be a string map")
        return cls(digest=digest, files=dict(files), diffs=dict(diffs), summary=summary)


@dataclass(frozen=True)
class ApprovalRecord:
    """Digest-bound user confirmation to apply a stored proposal."""

    task_id: str
    digest: str
    action: str
    mode: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
