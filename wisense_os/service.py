"""Task coordinator with durable status changes and no model-specific logic."""

from __future__ import annotations

from threading import Lock
from uuid import uuid4

from .bridge import WorkCenterBridge
from .contracts import RunMode, TaskRecord, TaskRequest, TaskStatus
from .model_policy import ModelPolicyError, ModelRegistry
from .store import TaskStore


class TaskCoordinator:
    def __init__(self, store: TaskStore, models: ModelRegistry, bridge: WorkCenterBridge) -> None:
        self.store = store
        self.models = models
        self.bridge = bridge
        # The current Work Center API owns one active project/model state.  Until
        # it exposes isolated per-task state, serializing bridge execution keeps
        # one task from changing another task's selected root or model.
        self._execution_lock = Lock()

    def submit(self, request: TaskRequest) -> TaskRecord:
        task_id = str(uuid4())
        try:
            self.models.validate(request)
        except ModelPolicyError as exc:
            record = TaskRecord(task_id, request, TaskStatus.BLOCKED, str(exc))
            self.store.create(record)
            self.store.append_event(task_id, "blocked", str(exc))
            return record
        initial_status = (
            TaskStatus.WAITING_FOR_APPROVAL
            if request.mode == RunMode.ASK_BEFORE_CHANGES
            else TaskStatus.ACCEPTED
        )
        record = TaskRecord(task_id, request, initial_status)
        self.store.create(record)
        if initial_status == TaskStatus.WAITING_FOR_APPROVAL:
            self.store.append_event(
                task_id,
                "awaiting_approval",
                "task persisted; approve before the Engine contacts a model or changes a project",
            )
        else:
            self.store.append_event(task_id, "accepted", "task persisted; no model call has been made")
        return record

    def approve(self, task_id: str) -> TaskRecord:
        with self._execution_lock:
            record = self.store.get(task_id)
            if record is None:
                raise KeyError(f"unknown task: {task_id}")
            if record.status != TaskStatus.WAITING_FOR_APPROVAL:
                raise ValueError(f"task is not awaiting approval: {record.status.value}")
            self.store.update_status(task_id, TaskStatus.ACCEPTED)
            self.store.append_event(task_id, "approved", "user approved Engine handoff")
            approved = self.store.get(task_id)
            assert approved is not None
            return approved

    def execute(self, task_id: str) -> TaskRecord:
        record = self.store.get(task_id)
        if record is None:
            raise KeyError(f"unknown task: {task_id}")
        if record.status != TaskStatus.ACCEPTED:
            return record
        with self._execution_lock:
            # A second API worker may have waited on the lock while the first
            # completed. Re-read durable state before any side effect.
            record = self.store.get(task_id)
            if record is None:
                raise KeyError(f"unknown task: {task_id}")
            if record.status != TaskStatus.ACCEPTED:
                return record
            if record.request.mode == RunMode.TALK_ONLY:
                self.store.update_status(task_id, TaskStatus.COMPLETED, "talk-only task is not delegated to a builder")
                self.store.append_event(task_id, "completed", "talk-only policy prevented a builder call")
                return self.store.get(task_id)  # type: ignore[return-value]
            self.store.update_status(task_id, TaskStatus.RUNNING)
            self.store.append_event(task_id, "delegating", "delegating to Local Agent Work Center canonical API")
            try:
                result = self.bridge.run(record.request)
            except Exception as exc:
                self.store.update_status(task_id, TaskStatus.FAILED, f"engine bridge failed: {exc}")
                self.store.append_event(task_id, "failed", "engine bridge failed before a result was recorded")
            else:
                reply = str(result.get("reply", "engine returned no reply"))
                self.store.update_status(task_id, TaskStatus.COMPLETED, reply)
                self.store.append_event(task_id, "completed", "engine response recorded")
            return self.store.get(task_id)  # type: ignore[return-value]
