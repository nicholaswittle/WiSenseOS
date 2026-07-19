from __future__ import annotations

from pathlib import Path

from wisense_os.contracts import RunMode, TaskRequest, TaskStatus
from wisense_os.model_policy import ModelRegistry
from wisense_os.service import TaskCoordinator
from wisense_os.store import TaskStore


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[TaskRequest] = []

    def run(self, request: TaskRequest) -> dict[str, object]:
        self.calls.append(request)
        return {"reply": "Done -- committed the change to example.py."}


def make_coordinator(tmp_path: Path) -> tuple[TaskCoordinator, FakeBridge]:
    root = Path(__file__).parents[1]
    models = ModelRegistry.from_file(root / "config" / "model_profiles.json")
    bridge = FakeBridge()
    return TaskCoordinator(TaskStore(tmp_path / "state.db"), models, bridge), bridge


def request(mode: RunMode = RunMode.ASK_BEFORE_CHANGES, builder: str = "gemma4:31b-cloud") -> TaskRequest:
    return TaskRequest(
        request="Fix the totals bug", project_root=r"C:\development\projects\demo",
        mode=mode, chat_model="glm-5.2:cloud", builder_model=builder,
    )


def test_cloud_profiles_are_truthful_and_execute_only_through_bridge(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    accepted = coordinator.submit(request())
    assert accepted.status is TaskStatus.ACCEPTED
    assert "no model call" in coordinator.store.events(accepted.task_id)[0].detail

    completed = coordinator.execute(accepted.task_id)
    assert completed.status is TaskStatus.COMPLETED
    assert bridge.calls == [request()]
    assert coordinator.store.events(accepted.task_id)[-1].kind == "completed"


def test_local_autopilot_fails_closed_without_a_local_builder(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    blocked = coordinator.submit(request(mode=RunMode.LOCAL_AUTOPILOT))
    assert blocked.status is TaskStatus.BLOCKED
    assert "no qualified local builder" in (blocked.reason or "")
    assert bridge.calls == []


def test_talk_only_never_delegates_to_builder(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    accepted = coordinator.submit(request(mode=RunMode.TALK_ONLY))
    completed = coordinator.execute(accepted.task_id)
    assert completed.status is TaskStatus.COMPLETED
    assert bridge.calls == []


def test_task_and_events_survive_store_reopen(tmp_path: Path) -> None:
    coordinator, _ = make_coordinator(tmp_path)
    accepted = coordinator.submit(request())
    reopened = TaskStore(tmp_path / "state.db")
    assert reopened.get(accepted.task_id) == accepted
    assert [event.kind for event in reopened.events(accepted.task_id)] == ["accepted"]


def test_execute_is_idempotent_and_never_delegates_twice(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    accepted = coordinator.submit(request())
    coordinator.execute(accepted.task_id)
    coordinator.execute(accepted.task_id)
    assert len(bridge.calls) == 1
