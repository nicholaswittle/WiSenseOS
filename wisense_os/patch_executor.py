"""Native reviewed-plan executor: prompt, exact patch, test, and restore."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Protocol

from .contracts import TaskRequest
from .model_adapter import ChatModel, ModelAdapterError
from .patch_protocol import PatchProtocolError, apply_candidate, parse_patch_candidate
from .plan import TaskPlan
from .workspace import WorkspacePlanError, WorkspaceSnapshot, restore_snapshot, snapshot_reviewed_files, validate_plan_files


class TestRunner(Protocol):
    def run(self, project_root: Path, targets: tuple[str, ...]) -> tuple[bool, str]: ...


@dataclass(frozen=True)
class PytestRunner:
    timeout_seconds: float = 120.0

    def run(self, project_root: Path, targets: tuple[str, ...]) -> tuple[bool, str]:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", *targets], cwd=project_root,
            capture_output=True, text=True, timeout=self.timeout_seconds, check=False,
        )
        detail = (completed.stdout + completed.stderr)[-12_000:]
        return completed.returncode == 0, detail


@dataclass
class PlanBoundPatchExecutor:
    model: ChatModel
    test_runner: TestRunner

    def run(self, request: TaskRequest, plan: TaskPlan) -> dict[str, object]:
        root = Path(request.project_root)
        try:
            targets = validate_plan_files(root, plan)
            snapshot = snapshot_reviewed_files(root, plan)
            raw = self.model.complete(_build_messages(request, plan, targets), model=request.builder_model)
            candidate = parse_patch_candidate(raw, plan)
            apply_candidate(snapshot, candidate)
            test_targets = tuple(path for path in plan.files if Path(path).name.startswith("test_") or path.endswith("_test.py"))
            if not test_targets:
                raise WorkspacePlanError("reviewed plan needs a named Python test file")
            passed, detail = self.test_runner.run(root, test_targets)
            if not passed:
                restore_snapshot(snapshot)
                repaired = self._repair_once(request, plan, targets, snapshot, test_targets, detail)
                if repaired is not None:
                    return repaired
                return {"failed": True, "reason": f"reviewed test failed after one repair; restored files\n{detail}"}
        except (OSError, ValueError, ModelAdapterError, PatchProtocolError, WorkspacePlanError, subprocess.TimeoutExpired) as exc:
            if "snapshot" in locals():
                restore_snapshot(snapshot)
            return {"failed": True, "reason": f"native plan-bound execution stopped safely: {exc}"}
        return {
            "reply": "validated, uncommitted: reviewed files changed and named tests passed",
            "changed_files": list(plan.files),
            "verification": f"named tests passed on first attempt: {', '.join(test_targets)}",
        }

    def _repair_once(
        self,
        request: TaskRequest,
        plan: TaskPlan,
        targets: tuple[Path, ...],
        snapshot: object,
        test_targets: tuple[str, ...],
        failure_detail: str,
    ) -> dict[str, object] | None:
        """Make at most one evidence-grounded repair after a named test failure."""
        if not isinstance(snapshot, WorkspaceSnapshot):
            raise WorkspacePlanError("invalid workspace snapshot")
        raw = self.model.complete(
            _build_repair_messages(request, plan, targets, failure_detail), model=request.builder_model,
        )
        candidate = parse_patch_candidate(raw, plan)
        apply_candidate(snapshot, candidate)
        passed, repair_detail = self.test_runner.run(snapshot.root, test_targets)
        if not passed:
            restore_snapshot(snapshot)
            return {
                "failed": True,
                "reason": f"reviewed test failed after one repair; restored files\n{repair_detail}",
            }
        return {
            "reply": "validated, uncommitted: reviewed files changed and named tests passed after one repair",
            "changed_files": list(plan.files),
            "verification": f"named tests passed after one repair: {', '.join(test_targets)}",
            "repair_evidence": repair_detail[-2_000:],
        }

    def continue_conversation(self, request: TaskRequest, message: str) -> dict[str, object]:
        return {"blocked": True, "reason": "native patch execution has no conversational continuation"}


def _build_messages(request: TaskRequest, plan: TaskPlan, targets: tuple[Path, ...]) -> list[dict[str, str]]:
    source_blocks = "\n\n".join(
        f"FILE: {path.relative_to(Path(request.project_root)).as_posix()}\n{path.read_text(encoding='utf-8')}"
        for path in targets
    )
    return [
        {
            "role": "system",
            "content": (
                "You are WiSense's implementation role. Reply ONLY with JSON: "
                '{"files":[{"path":"reviewed/path.py","content":"complete file content"}]}. '
                "Return exactly the reviewed paths, no markdown, no extra files, no shell commands."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Request: {request.request}\n\nReviewed plan: {plan.to_json()}\n\n"
                f"Current reviewed files:\n{source_blocks}"
            ),
        },
    ]


def _build_repair_messages(
    request: TaskRequest, plan: TaskPlan, targets: tuple[Path, ...], failure_detail: str,
) -> list[dict[str, str]]:
    """Ask for one exact-scope repair using only the named test's evidence."""
    messages = _build_messages(request, plan, targets)
    messages[0] = {
        "role": "system",
        "content": (
            "You are WiSense's one allowed repair attempt. Reply ONLY with JSON: "
            '{"files":[{"path":"reviewed/path.py","content":"complete file content"}]}. '
            "Repair only the reviewed files using the named-test failure below. No markdown, prose, or extra files."
        ),
    }
    messages.append({
        "role": "user",
        "content": f"Named test failure from the first candidate:\n{failure_detail[-12_000:]}",
    })
    return messages
