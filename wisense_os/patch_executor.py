"""Native reviewed-plan executor: prompt, exact patch, test, and restore."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import sys
from uuid import uuid4
from typing import Protocol

from .contracts import TaskRequest
from .model_adapter import ChatModel, ModelAdapterError
from .patch_protocol import PatchProtocolError, apply_candidate, parse_patch_candidate
from .plan import TaskPlan
from .workspace import WorkspacePlanError, WorkspaceSnapshot, restore_snapshot, snapshot_reviewed_files, validate_plan_files


class TestRunner(Protocol):
    def run(self, project_root: Path, targets: tuple[str, ...]) -> tuple[bool, str]: ...


def _clear_pycache(project_root: Path) -> None:
    for cache_dir in project_root.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)


def _git_commit_scoped(
    project_root: Path, files: tuple[str, ...], message: str
) -> tuple[bool, str]:
    """Commit ONLY the reviewed files, path-scoped, never sweeping any
    unrelated staged or working-tree change. Returns (committed,
    evidence). Never raises for ordinary environment failures (no git, no
    identity, hooks, a non-repo directory): the caller keeps the
    validated files on disk and reports them as uncommitted -- verified
    work is never thrown away by a commit problem."""
    rel = list(files)
    try:
        add = subprocess.run(
            ["git", "add", "--", *rel], cwd=project_root,
            capture_output=True, text=True)
        if add.returncode != 0:
            return False, f"git add failed: {(add.stdout + add.stderr).strip()[-300:]}"
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", *rel], cwd=project_root)
        if diff.returncode == 0:
            return False, "no staged change for the reviewed files"
        if diff.returncode > 1:
            return False, "git diff --cached failed"
        commit = subprocess.run(
            ["git", "commit", "-m", message, "--", *rel], cwd=project_root,
            capture_output=True, text=True)
        if commit.returncode != 0:
            return False, f"git commit failed: {(commit.stdout + commit.stderr).strip()[-300:]}"
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=project_root,
            capture_output=True, text=True)
        return True, f"commit {head.stdout.strip()}"
    except OSError as exc:
        return False, f"git unavailable: {exc}"


@dataclass(frozen=True)
class PytestRunner:
    timeout_seconds: float = 120.0

    def run(self, project_root: Path, targets: tuple[str, ...]) -> tuple[bool, str]:
        # Isolate the target-project pytest subprocess. Stale bytecode can
        # import an EARLIER version of a just-edited file and report a
        # false PASS on broken code -- the one validator failure that must
        # never happen. So: clear __pycache__ first, disable bytecode
        # writing and the cache provider, and use a unique project-local
        # basetemp removed afterward (a leftover untracked dir would look
        # like an undeclared change to any later git scope check).
        _clear_pycache(project_root)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        base_temp = project_root / f".wisense_pytest_{uuid4().hex}"
        try:
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider",
                 f"--basetemp={base_temp}", *targets],
                cwd=project_root, capture_output=True, text=True,
                timeout=self.timeout_seconds, check=False, env=env,
            )
        finally:
            shutil.rmtree(base_temp, ignore_errors=True)
        detail = (completed.stdout + completed.stderr)[-12_000:]
        return completed.returncode == 0, detail


@dataclass
class PlanBoundPatchExecutor:
    model: ChatModel
    test_runner: TestRunner
    # Off by default so unit tests observe the pure validate-only result;
    # the launcher enables it so a validated change lands as a scoped,
    # path-limited commit with evidence.
    commit_on_success: bool = False

    def _success(
        self, root: Path, plan: TaskPlan, test_targets: tuple[str, ...], *,
        repaired: bool, repair_detail: str | None = None,
    ) -> dict[str, object]:
        suffix = " after one repair" if repaired else ""
        result: dict[str, object] = {
            "reply": f"validated, uncommitted: reviewed files changed and named tests passed{suffix}",
            "changed_files": list(plan.files),
            "verification": (
                "named tests passed"
                f"{' after one repair' if repaired else ' on first attempt'}: "
                f"{', '.join(test_targets)}"
            ),
        }
        if repaired and repair_detail is not None:
            result["repair_evidence"] = repair_detail[-2_000:]
        if self.commit_on_success:
            committed, evidence = _git_commit_scoped(root, plan.files, f"wisense: {plan.title}")
            result["committed"] = committed
            result["commit"] = evidence
            core = f"reviewed files changed and named tests passed{suffix}"
            result["reply"] = (
                f"committed ({evidence}): {core}" if committed
                else f"validated, uncommitted ({evidence}): {core}")
        return result

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
        return self._success(root, plan, test_targets, repaired=False)

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
        return self._success(snapshot.root, plan, test_targets, repaired=True, repair_detail=repair_detail)

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
