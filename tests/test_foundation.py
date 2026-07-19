from __future__ import annotations

from pathlib import Path
from typing import Mapping

from wisense_os.contracts import RunMode, TaskRequest, TaskStatus
from wisense_os.model_policy import ModelRegistry
from wisense_os.plan import TaskPlan
from wisense_os.proposal import proposal_digest
from wisense_os.service import TaskCoordinator
from wisense_os.store import TaskStore


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[TaskRequest] = []
        self.propose_calls: list[TaskRequest] = []
        self.apply_calls: list[TaskRequest] = []
        self.follow_ups: list[str] = []
        self.reply = "Done -- committed the change to example.py."
        self.follow_up_reply = "Done -- committed the change to example.py."
        # Typed pending signal -- the executor declares it explicitly; the
        # coordinator never guesses from reply text.
        self.pending_input = False
        self.committed = False
        self.commit_evidence = ""
        self.proposal_files = {"app.py": "new app", "test_app.py": "new test"}
        self.proposal_diffs = {"app.py": "diff app", "test_app.py": "diff test"}

    def propose(self, request: TaskRequest, _plan: TaskPlan) -> dict[str, object]:
        self.propose_calls.append(request)
        digest = proposal_digest(self.proposal_files)
        return {
            "digest": digest,
            "proposal": {
                "digest": digest,
                "files": dict(self.proposal_files),
                "diffs": dict(self.proposal_diffs),
                "summary": "fake proposal",
            },
        }

    def apply_proposal(
        self, request: TaskRequest, _plan: TaskPlan, files: Mapping[str, str],
    ) -> dict[str, object]:
        self.calls.append(request)
        self.apply_calls.append(request)
        result: dict[str, object] = {"reply": self.reply, "pending_input": self.pending_input}
        if self.committed:
            result["committed"] = True
            result["commit"] = self.commit_evidence
        return result

    def run(self, request: TaskRequest, plan: TaskPlan) -> dict[str, object]:
        proposed = self.propose(request, plan)
        return self.apply_proposal(request, plan, proposed["proposal"]["files"])  # type: ignore[index]

    def chat(self, request: TaskRequest) -> dict[str, object]:
        self.calls.append(request)
        return {"reply": "Talk-only explanation with no project writes."}

    def continue_conversation(self, request: TaskRequest, message: str) -> dict[str, object]:
        self.calls.append(request)
        self.follow_ups.append(message)
        return {"reply": self.follow_up_reply}


def make_coordinator(tmp_path: Path) -> tuple[TaskCoordinator, FakeExecutor]:
    root = Path(__file__).parents[1]
    models = ModelRegistry.from_file(root / "config" / "model_profiles.json")
    executor = FakeExecutor()
    return TaskCoordinator(TaskStore(tmp_path / "state.db"), models, executor), executor


def request(mode: RunMode = RunMode.ASK_BEFORE_CHANGES, builder: str = "gemma4:31b-cloud", *, offline: bool = False) -> TaskRequest:
    return TaskRequest(
        request="Fix the totals bug", project_root=r"C:\development\projects\demo",
        mode=mode, chat_model="glm-5.2:cloud", builder_model=builder, offline=offline,
    )


def review_plan(coordinator: TaskCoordinator, task_id: str) -> None:
    coordinator.store.save_plan(task_id, TaskPlan(
        title="Fix totals", summary="Bounded test plan", files=("app.py", "test_app.py"),
        api_contract=("fix totals",), acceptance=("relevant test passes",),
    ))


def prepare_approved_proposal(coordinator: TaskCoordinator, task_id: str) -> str:
    review_plan(coordinator, task_id)
    waiting = coordinator.prepare_proposal(task_id)
    assert waiting.status is TaskStatus.WAITING_FOR_APPROVAL
    proposal = coordinator.store.proposal(task_id)
    assert proposal is not None
    return proposal.digest


def test_cloud_profiles_are_truthful_and_execute_only_through_native_executor(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    accepted = coordinator.submit(request())
    assert accepted.status is TaskStatus.ACCEPTED
    assert "draft a plan" in coordinator.store.events(accepted.task_id)[0].detail
    assert executor.propose_calls == []
    assert executor.calls == []

    digest = prepare_approved_proposal(coordinator, accepted.task_id)
    assert executor.propose_calls == [request()]
    approved = coordinator.approve(accepted.task_id, digest=digest)
    assert approved.status is TaskStatus.ACCEPTED
    completed = coordinator.execute(accepted.task_id)
    assert completed.status is TaskStatus.COMPLETED
    assert executor.apply_calls == [request()]
    assert coordinator.store.events(accepted.task_id)[-1].kind == "completed"


def test_local_autopilot_fails_closed_without_a_local_builder(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    blocked = coordinator.submit(request(mode=RunMode.LOCAL_AUTOPILOT))
    assert blocked.status is TaskStatus.BLOCKED
    assert "no qualified local builder" in (blocked.reason or "")
    assert executor.calls == []


def test_offline_mode_hard_blocks_cloud_models(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    blocked = coordinator.submit(request(offline=True))
    assert blocked.status is TaskStatus.BLOCKED
    assert "offline mode hard-blocks cloud model" in (blocked.reason or "")
    assert executor.calls == []


def test_glm_cloud_is_allowed_for_supervised_builder_testing(tmp_path: Path) -> None:
    coordinator, _ = make_coordinator(tmp_path)
    accepted = coordinator.submit(request(builder="glm-5.2:cloud"))
    assert accepted.status is TaskStatus.ACCEPTED


def test_talk_only_uses_chat_and_never_proposes_writes(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    accepted = coordinator.submit(request(mode=RunMode.TALK_ONLY))
    completed = coordinator.execute(accepted.task_id)
    assert completed.status is TaskStatus.COMPLETED
    assert executor.propose_calls == []
    assert executor.apply_calls == []
    assert len(executor.calls) == 1
    assert "Talk-only explanation" in (completed.reason or "")
    assert [event.kind for event in coordinator.store.events(accepted.task_id)] == [
        "accepted", "exploring", "completed",
    ]


def test_task_and_events_survive_store_reopen(tmp_path: Path) -> None:
    coordinator, _ = make_coordinator(tmp_path)
    accepted = coordinator.submit(request())
    reopened = TaskStore(tmp_path / "state.db")
    assert reopened.get(accepted.task_id) == accepted
    assert [event.kind for event in reopened.events(accepted.task_id)] == ["accepted"]


def test_execute_is_idempotent_and_never_delegates_twice(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    accepted = coordinator.submit(request())
    digest = prepare_approved_proposal(coordinator, accepted.task_id)
    coordinator.approve(accepted.task_id, digest=digest)
    coordinator.execute(accepted.task_id)
    coordinator.execute(accepted.task_id)
    assert len(executor.apply_calls) == 1


def test_executor_evidence_is_persisted_before_completed_status(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    waiting = coordinator.submit(request())
    digest = prepare_approved_proposal(coordinator, waiting.task_id)
    coordinator.approve(waiting.task_id, digest=digest)
    executor.reply = "validated, uncommitted"

    def _apply(request: TaskRequest, _plan: TaskPlan, _files: Mapping[str, str]) -> dict[str, object]:
        executor.calls.append(request)
        executor.apply_calls.append(request)
        return {
            "reply": executor.reply,
            "changed_files": ["app.py", "test_app.py"],
            "verification": "named test passed: test_app.py",
        }

    executor.apply_proposal = _apply  # type: ignore[method-assign]

    coordinator.execute(waiting.task_id)

    assert [event.kind for event in coordinator.store.events(waiting.task_id)][-3:] == [
        "files_changed", "verification", "completed",
    ]


def test_approval_requires_matching_digest_and_does_not_apply(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    waiting = coordinator.submit(request())
    digest = prepare_approved_proposal(coordinator, waiting.task_id)

    try:
        coordinator.approve(waiting.task_id, digest="wrong-digest")
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("mismatched digest must be rejected")

    coordinator.approve(waiting.task_id, digest=digest)

    assert executor.apply_calls == []
    try:
        coordinator.approve(waiting.task_id, digest=digest)
    except ValueError as exc:
        assert "not awaiting approval" in str(exc)
    else:
        raise AssertionError("a task approval must be single-use")


def test_executor_confirmation_is_a_durable_second_gate(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    executor.reply = "This action needs your explicit response."
    executor.pending_input = True
    waiting = coordinator.submit(request())
    digest = prepare_approved_proposal(coordinator, waiting.task_id)

    coordinator.approve(waiting.task_id, digest=digest)
    provider_waiting = coordinator.execute(waiting.task_id)

    assert provider_waiting.status == TaskStatus.WAITING_FOR_PROVIDER_INPUT
    assert "explicit response" in (provider_waiting.reason or "")
    assert executor.follow_ups == []
    kinds = [event.kind for event in coordinator.store.events(waiting.task_id)]
    assert kinds[:2] == ["accepted", "exploring"]
    assert "proposal_ready" in kinds
    assert "awaiting_approval" in kinds
    assert kinds[-2:] == ["applying", "provider_input_required"]

    completed = coordinator.continue_with_provider_input(waiting.task_id, "go ahead")

    assert completed.status == TaskStatus.COMPLETED
    assert executor.follow_ups == ["go ahead"]
    assert [event.kind for event in coordinator.store.events(waiting.task_id)][-2:] == [
        "provider_input_submitted", "completed",
    ]


def test_executor_response_blocks_a_second_handoff(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    executor.reply = "This action needs your explicit response."
    executor.pending_input = True
    first = coordinator.submit(request())
    second = coordinator.submit(request())
    first_digest = prepare_approved_proposal(coordinator, first.task_id)
    prepare_approved_proposal(coordinator, second.task_id)
    coordinator.approve(first.task_id, digest=first_digest)
    coordinator.execute(first.task_id)

    second_proposal = coordinator.store.proposal(second.task_id)
    assert second_proposal is not None
    try:
        coordinator.approve(second.task_id, digest=second_proposal.digest)
    except ValueError as exc:
        assert "another task is awaiting an Engine response" in str(exc)
    else:
        raise AssertionError("a second handoff must not overwrite the provider conversation")
    assert len(executor.apply_calls) == 1


def test_canceling_provider_follow_up_releases_the_next_handoff(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    executor.reply = "This action needs your explicit response."
    executor.pending_input = True
    first = coordinator.submit(request())
    second = coordinator.submit(request())
    first_digest = prepare_approved_proposal(coordinator, first.task_id)
    second_digest = prepare_approved_proposal(coordinator, second.task_id)
    coordinator.approve(first.task_id, digest=first_digest)
    coordinator.execute(first.task_id)

    canceled = coordinator.cancel(first.task_id)
    approved_second = coordinator.approve(second.task_id, digest=second_digest)

    assert canceled.status == TaskStatus.CANCELED
    assert approved_second.status == TaskStatus.ACCEPTED
    assert coordinator.store.events(first.task_id)[-1].kind == "canceled"


def test_a_committed_result_emits_a_committed_event(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)
    executor.reply = "committed (commit abc1234): reviewed files changed and named tests passed"
    executor.committed = True
    executor.commit_evidence = "commit abc1234"
    waiting = coordinator.submit(request())
    digest = prepare_approved_proposal(coordinator, waiting.task_id)
    coordinator.approve(waiting.task_id, digest=digest)
    done = coordinator.execute(waiting.task_id)

    assert done.status == TaskStatus.COMPLETED
    events = coordinator.store.events(waiting.task_id)
    committed = [event for event in events if event.kind == "committed"]
    assert len(committed) == 1 and "abc1234" in committed[0].detail


def test_pending_state_is_typed_not_inferred_from_reply_text(tmp_path: Path) -> None:
    coordinator, executor = make_coordinator(tmp_path)

    # 1) A question-shaped reply with NO typed flag must COMPLETE -- the
    # former "any reply ending in ?" heuristic is gone.
    executor.reply = "Should I have done more? Anyway, it is committed."
    executor.pending_input = False
    first = coordinator.submit(request())
    digest = prepare_approved_proposal(coordinator, first.task_id)
    coordinator.approve(first.task_id, digest=digest)
    assert coordinator.execute(first.task_id).status == TaskStatus.COMPLETED

    # 2) The typed flag alone drives the pending state, even for a reply
    # that is not question-shaped; the reply becomes the prompt.
    executor.reply = "Choose a target."
    executor.pending_input = True
    second = coordinator.submit(request())
    digest = prepare_approved_proposal(coordinator, second.task_id)
    coordinator.approve(second.task_id, digest=digest)
    pending = coordinator.execute(second.task_id)
    assert pending.status == TaskStatus.WAITING_FOR_PROVIDER_INPUT
    assert (pending.reason or "") == "Choose a target."
