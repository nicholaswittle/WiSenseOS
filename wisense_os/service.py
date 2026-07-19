"""Task coordinator with durable status changes and no model-specific logic."""

from __future__ import annotations

from threading import Lock
from uuid import uuid4

import json

from .budget import BudgetExceededError, BudgetLedger, UnknownModelPricingError, estimate_tokens
from .contracts import ProviderKind, RunMode, TaskProposal, TaskRecord, TaskRequest, TaskStatus
from .executor import TaskExecutor
from .plan import TaskPlan
from .model_policy import ModelPolicyError, ModelRegistry
from .qualification import QualificationStore
from .store import TaskStore


def json_dumps_plan(plan: TaskPlan) -> str:
    return json.dumps(plan.to_json(), ensure_ascii=False)


class TaskCoordinator:
    def __init__(
        self,
        store: TaskStore,
        models: ModelRegistry,
        executor: TaskExecutor,
        *,
        budget: BudgetLedger | None = None,
        qualification: QualificationStore | None = None,
    ) -> None:
        self.store = store
        self.models = models
        self.executor = executor
        self.budget = budget
        self.qualification = qualification
        # Every future WiSense executor runs under this lock until per-project
        # isolation is proven. No external app state is involved.
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

        # Ask Before Changes starts accepted: draft a plan, prepare a proposal
        # (may contact a model), then digest-bound approval gates writes.
        # Local Autopilot also starts accepted and applies after a plan exists.
        record = TaskRecord(task_id, request, TaskStatus.ACCEPTED)
        self.store.create(record)
        if request.mode == RunMode.ASK_BEFORE_CHANGES:
            self.store.append_event(
                task_id,
                "accepted",
                "task persisted; draft a plan then prepare a proposal before writes",
            )
        elif request.mode == RunMode.TALK_ONLY:
            self.store.append_event(
                task_id,
                "accepted",
                "talk-only task persisted; builder writes remain hard-blocked",
            )
        else:
            self.store.append_event(
                task_id,
                "accepted",
                "task persisted; no model call has been made",
            )
        return record

    def prepare_proposal(self, task_id: str) -> TaskRecord:
        """Contact the builder to prepare a write proposal without mutating files."""
        with self._execution_lock:
            record = self.store.get(task_id)
            if record is None:
                raise KeyError(f"unknown task: {task_id}")
            if record.status not in {TaskStatus.ACCEPTED, TaskStatus.EXPLORING}:
                raise ValueError(f"proposal cannot be prepared in state: {record.status.value}")
            if record.request.mode != RunMode.ASK_BEFORE_CHANGES:
                raise ValueError("proposal preparation is only for ask_before_changes")
            saved_plan = self.store.plan(task_id)
            if saved_plan is None:
                raise ValueError("task needs a reviewed plan before proposal preparation")

            active_provider_turn = self.store.provider_input_waiting_task(exclude_task_id=task_id)
            if active_provider_turn is not None:
                raise ValueError(
                    "another task is awaiting an Engine response; finish or cancel "
                    f"task {active_provider_turn.task_id} before preparing a proposal"
                )

            self.store.update_status(task_id, TaskStatus.EXPLORING)
            self.store.append_event(task_id, "exploring", "preparing a write proposal from the reviewed plan")
            request = record.request
            plan = TaskPlan.from_json(saved_plan)

        reservation_id: str | None = None
        try:
            if self.budget is not None:
                builder = self.models.get(request.builder_model)
                if builder.provider is ProviderKind.CLOUD:
                    prompt_chars = request.request + json_dumps_plan(plan)
                    reservation_id = self.budget.reserve(
                        model=request.builder_model,
                        input_tokens=estimate_tokens(prompt_chars),
                        output_tokens=estimate_tokens(prompt_chars) * 2,
                        task_id=task_id,
                    )
                    self.store.append_event(
                        task_id,
                        "budget_reserved",
                        f"reserved cloud spend for {request.builder_model}",
                    )
            result = self.executor.propose(request, plan)
        except (BudgetExceededError, UnknownModelPricingError) as exc:
            with self._execution_lock:
                if self._is_canceled(task_id):
                    return self.store.get(task_id)  # type: ignore[return-value]
                self.store.update_status(task_id, TaskStatus.BLOCKED, str(exc))
                self.store.append_event(task_id, "blocked", str(exc))
                return self.store.get(task_id)  # type: ignore[return-value]
        except Exception as exc:
            if reservation_id and self.budget is not None:
                self.budget.release(reservation_id)
            with self._execution_lock:
                if self._is_canceled(task_id):
                    return self.store.get(task_id)  # type: ignore[return-value]
                self.store.update_status(task_id, TaskStatus.FAILED, f"proposal failed: {exc}")
                self.store.append_event(task_id, "failed", "proposal preparation failed before a result was recorded")
                return self.store.get(task_id)  # type: ignore[return-value]

        if reservation_id and self.budget is not None:
            if result.get("failed") is True or result.get("blocked") is True:
                self.budget.release(reservation_id)
            else:
                self.budget.reconcile(reservation_id)

        with self._execution_lock:
            if self._is_canceled(task_id):
                return self.store.get(task_id)  # type: ignore[return-value]
            if result.get("failed") is True or result.get("blocked") is True:
                reason = str(result.get("reason", "proposal preparation failed"))
                status = TaskStatus.BLOCKED if result.get("blocked") is True else TaskStatus.FAILED
                self.store.update_status(task_id, status, reason)
                self.store.append_event(task_id, status.value, reason)
                return self.store.get(task_id)  # type: ignore[return-value]

            proposal_payload = result.get("proposal")
            if not isinstance(proposal_payload, dict):
                self.store.update_status(task_id, TaskStatus.FAILED, "proposal missing from executor result")
                self.store.append_event(task_id, "failed", "proposal missing from executor result")
                return self.store.get(task_id)  # type: ignore[return-value]

            proposal = TaskProposal.from_json(proposal_payload)
            self.store.save_proposal(task_id, proposal)
            self.store.update_status(
                task_id,
                TaskStatus.WAITING_FOR_APPROVAL,
                "proposal ready; approve the digest to apply writes",
            )
            self.store.append_event(
                task_id,
                "proposal_ready",
                f"digest {proposal.digest[:12]}… — {proposal.summary}",
            )
            self.store.append_event(
                task_id,
                "awaiting_approval",
                "approve the exact proposal digest before any project file is changed",
            )
            return self.store.get(task_id)  # type: ignore[return-value]

    def approve(self, task_id: str, *, digest: str) -> TaskRecord:
        clean_digest = digest.strip()
        if not clean_digest:
            raise ValueError("approval digest is required")
        with self._execution_lock:
            record = self.store.get(task_id)
            if record is None:
                raise KeyError(f"unknown task: {task_id}")
            if record.status != TaskStatus.WAITING_FOR_APPROVAL:
                raise ValueError(f"task is not awaiting approval: {record.status.value}")
            if self.store.plan(task_id) is None:
                raise ValueError("task needs a reviewed plan before Engine handoff")
            proposal = self.store.proposal(task_id)
            if proposal is None:
                raise ValueError("task needs a prepared proposal before approval")
            if proposal.digest != clean_digest:
                raise ValueError("approval digest does not match the prepared proposal")
            active_provider_turn = self.store.provider_input_waiting_task(exclude_task_id=task_id)
            if active_provider_turn is not None:
                raise ValueError(
                    "another task is awaiting an Engine response; finish or cancel "
                    f"task {active_provider_turn.task_id} before approving a new handoff"
                )
            self.store.save_approval(
                task_id,
                digest=clean_digest,
                action="apply_proposal",
                mode=record.request.mode.value,
            )
            self.store.update_status(task_id, TaskStatus.ACCEPTED)
            self.store.append_event(
                task_id,
                "approved",
                f"user approved apply_proposal digest {clean_digest[:12]}…",
            )
            approved = self.store.get(task_id)
            assert approved is not None
            return approved

    def cancel(self, task_id: str) -> TaskRecord:
        """Discard a waiting or running task without further model/write work."""
        with self._execution_lock:
            record = self.store.get(task_id)
            if record is None:
                raise KeyError(f"unknown task: {task_id}")
            cancellable = {
                TaskStatus.ACCEPTED,
                TaskStatus.EXPLORING,
                TaskStatus.WAITING_FOR_APPROVAL,
                TaskStatus.WAITING_FOR_PROVIDER_INPUT,
                TaskStatus.RUNNING,
            }
            if record.status not in cancellable:
                raise ValueError(f"task cannot be canceled in state: {record.status.value}")
            self.store.update_status(task_id, TaskStatus.CANCELED, "canceled by user before further handoff")
            self.store.append_event(task_id, "canceled", "user canceled the pending task")
            canceled = self.store.get(task_id)
            assert canceled is not None
            return canceled

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
            mode = record.request.mode
            request = record.request
            plan: TaskPlan | None = None
            approved_files: dict[str, str] | None = None

            if mode == RunMode.TALK_ONLY:
                self.store.update_status(task_id, TaskStatus.RUNNING)
                self.store.append_event(task_id, "exploring", "talk-only chat with writes hard-blocked")
            else:
                saved_plan = self.store.plan(task_id)
                if saved_plan is None:
                    self.store.update_status(task_id, TaskStatus.FAILED, "task needs a reviewed plan before execution")
                    self.store.append_event(task_id, "failed", "missing reviewed plan")
                    return self.store.get(task_id)  # type: ignore[return-value]

                proposal = self.store.proposal(task_id)
                approval = self.store.approval(task_id)

                # Ask Before Changes must apply only a digest-approved proposal.
                if mode == RunMode.ASK_BEFORE_CHANGES:
                    if proposal is None or approval is None:
                        self.store.update_status(
                            task_id,
                            TaskStatus.FAILED,
                            "ask_before_changes requires a digest-approved proposal before writes",
                        )
                        self.store.append_event(task_id, "failed", "missing approved proposal")
                        return self.store.get(task_id)  # type: ignore[return-value]
                    if approval["digest"] != proposal.digest:
                        self.store.update_status(task_id, TaskStatus.FAILED, "approval digest no longer matches proposal")
                        self.store.append_event(task_id, "failed", "approval digest mismatch")
                        return self.store.get(task_id)  # type: ignore[return-value]

                self.store.update_status(task_id, TaskStatus.RUNNING)
                self.store.append_event(task_id, "applying", "applying the approved proposal to the project")
                plan = TaskPlan.from_json(saved_plan)
                approved_files = dict(proposal.files) if proposal is not None else None

        try:
            if mode == RunMode.TALK_ONLY:
                result = self.executor.chat(request)
            elif mode == RunMode.ASK_BEFORE_CHANGES:
                assert approved_files is not None
                assert plan is not None
                result = self.executor.apply_proposal(request, plan, approved_files)
            else:
                assert plan is not None
                result = self.executor.run(request, plan)
        except Exception as exc:
            with self._execution_lock:
                if self._is_canceled(task_id):
                    return self.store.get(task_id)  # type: ignore[return-value]
                self.store.update_status(task_id, TaskStatus.FAILED, f"native executor failed: {exc}")
                self.store.append_event(task_id, "failed", "native executor failed before a result was recorded")
                return self.store.get(task_id)  # type: ignore[return-value]

        with self._execution_lock:
            if self._is_canceled(task_id):
                return self.store.get(task_id)  # type: ignore[return-value]
            self._record_executor_result(task_id, result)
            return self.store.get(task_id)  # type: ignore[return-value]

    def continue_with_provider_input(self, task_id: str, message: str) -> TaskRecord:
        """Forward a deliberate user response to an existing Engine turn."""
        clean_message = message.strip()
        if not clean_message:
            raise ValueError("provider input is required")
        with self._execution_lock:
            record = self.store.get(task_id)
            if record is None:
                raise KeyError(f"unknown task: {task_id}")
            if record.status != TaskStatus.WAITING_FOR_PROVIDER_INPUT:
                raise ValueError(f"task is not awaiting provider input: {record.status.value}")
            self.store.update_status(task_id, TaskStatus.RUNNING)
            self.store.append_event(task_id, "provider_input_submitted", "user sent an explicit response to the Engine")
            try:
                result = self.executor.continue_conversation(record.request, clean_message)
            except Exception as exc:
                self.store.update_status(task_id, TaskStatus.FAILED, f"native executor failed: {exc}")
                self.store.append_event(task_id, "failed", "native executor failed before a follow-up result was recorded")
            else:
                self._record_executor_result(task_id, result)
            return self.store.get(task_id)  # type: ignore[return-value]

    def _is_canceled(self, task_id: str) -> bool:
        current = self.store.get(task_id)
        return current is not None and current.status == TaskStatus.CANCELED

    def _record_executor_result(self, task_id: str, result: dict[str, object]) -> None:
        if result.get("blocked") is True:
            reason = str(result.get("reason", "native execution is unavailable"))
            self.store.update_status(task_id, TaskStatus.BLOCKED, reason)
            self.store.append_event(task_id, "blocked", reason)
            return
        if result.get("failed") is True:
            reason = str(result.get("reason", "native execution failed"))
            self.store.update_status(task_id, TaskStatus.FAILED, reason)
            if result.get("rolled_back") is True:
                self.store.append_event(task_id, "rolled_back", reason)
            self.store.append_event(task_id, "failed", reason)
            return
        changed_files = result.get("changed_files")
        if isinstance(changed_files, list) and all(isinstance(path, str) for path in changed_files):
            self.store.append_event(task_id, "files_changed", ", ".join(changed_files))
        verification = result.get("verification")
        if isinstance(verification, str) and verification:
            self.store.append_event(task_id, "verification", verification)
        if result.get("committed") is True:
            self.store.append_event(task_id, "committed", str(result.get("commit", "")))
        reply = str(result.get("reply", "engine returned no reply"))
        # Typed pending state, NEVER inferred from reply text. The executor
        # must explicitly declare that it needs another user turn; the
        # coordinator does not read the reply to guess lifecycle state.
        if result.get("pending_input") is True:
            prompt = str(result.get("pending_prompt") or reply)
            self.store.update_status(task_id, TaskStatus.WAITING_FOR_PROVIDER_INPUT, prompt)
            self.store.append_event(task_id, "provider_input_required", "Engine requires an explicit user response")
            return
        self.store.update_status(task_id, TaskStatus.COMPLETED, reply)
        self.store.append_event(task_id, "completed", "engine response recorded")
