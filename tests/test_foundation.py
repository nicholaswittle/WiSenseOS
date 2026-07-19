from __future__ import annotations

from pathlib import Path

from wisense_os.contracts import RunMode, TaskRequest, TaskStatus
from wisense_os.model_policy import ModelRegistry
from wisense_os.service import TaskCoordinator
from wisense_os.store import TaskStore


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[TaskRequest] = []
        self.follow_ups: list[str] = []
        self.reply = "Done -- committed the change to example.py."
        self.follow_up_reply = "Done -- committed the change to example.py."

    def run(self, request: TaskRequest) -> dict[str, object]:
        self.calls.append(request)
        return {"reply": self.reply}

    def continue_conversation(self, request: TaskRequest, message: str) -> dict[str, object]:
        self.calls.append(request)
        self.follow_ups.append(message)
        return {"reply": self.follow_up_reply}


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
    assert accepted.status is TaskStatus.WAITING_FOR_APPROVAL
    assert "approve before" in coordinator.store.events(accepted.task_id)[0].detail
    assert bridge.calls == []

    approved = coordinator.approve(accepted.task_id)
    assert approved.status is TaskStatus.ACCEPTED
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


def test_glm_cloud_is_allowed_for_supervised_builder_testing(tmp_path: Path) -> None:
    coordinator, _ = make_coordinator(tmp_path)
    accepted = coordinator.submit(request(builder="glm-5.2:cloud"))
    assert accepted.status is TaskStatus.WAITING_FOR_APPROVAL


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
    assert [event.kind for event in reopened.events(accepted.task_id)] == ["awaiting_approval"]


def test_execute_is_idempotent_and_never_delegates_twice(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    accepted = coordinator.submit(request())
    coordinator.approve(accepted.task_id)
    coordinator.execute(accepted.task_id)
    coordinator.execute(accepted.task_id)
    assert len(bridge.calls) == 1


def test_approval_is_single_use_and_does_not_run_a_model(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    waiting = coordinator.submit(request())

    coordinator.approve(waiting.task_id)

    assert bridge.calls == []
    try:
        coordinator.approve(waiting.task_id)
    except ValueError as exc:
        assert "not awaiting approval" in str(exc)
    else:
        raise AssertionError("a task approval must be single-use")


def test_provider_confirmation_is_a_durable_second_gate(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    bridge.reply = "This would use gemma4:31b-cloud, which may spend quota -- go ahead?"
    waiting = coordinator.submit(request())

    coordinator.approve(waiting.task_id)
    provider_waiting = coordinator.execute(waiting.task_id)

    assert provider_waiting.status == TaskStatus.WAITING_FOR_PROVIDER_INPUT
    assert "may spend quota" in (provider_waiting.reason or "")
    assert bridge.follow_ups == []
    assert [event.kind for event in coordinator.store.events(waiting.task_id)] == [
        "awaiting_approval", "approved", "delegating", "provider_input_required",
    ]

    completed = coordinator.continue_with_provider_input(waiting.task_id, "go ahead")

    assert completed.status == TaskStatus.COMPLETED
    assert bridge.follow_ups == ["go ahead"]
    assert [event.kind for event in coordinator.store.events(waiting.task_id)][-2:] == [
        "provider_input_submitted", "completed",
    ]


def test_provider_response_blocks_a_second_work_center_handoff(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    bridge.reply = "This may spend quota -- go ahead?"
    first = coordinator.submit(request())
    second = coordinator.submit(request())
    coordinator.approve(first.task_id)
    coordinator.execute(first.task_id)

    try:
        coordinator.approve(second.task_id)
    except ValueError as exc:
        assert "another task is awaiting a Work Center response" in str(exc)
    else:
        raise AssertionError("a second handoff must not overwrite the provider conversation")
    assert bridge.calls == [request()]


def test_canceling_provider_follow_up_releases_the_next_handoff(tmp_path: Path) -> None:
    coordinator, bridge = make_coordinator(tmp_path)
    bridge.reply = "This may spend quota -- go ahead?"
    first = coordinator.submit(request())
    second = coordinator.submit(request())
    coordinator.approve(first.task_id)
    coordinator.execute(first.task_id)

    canceled = coordinator.cancel(first.task_id)
    approved_second = coordinator.approve(second.task_id)

    assert canceled.status == TaskStatus.CANCELED
    assert approved_second.status == TaskStatus.ACCEPTED
    assert coordinator.store.events(first.task_id)[-1].kind == "canceled"
