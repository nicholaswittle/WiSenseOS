"""Scoped git commit after a validated change: commit ONLY the reviewed
files, and never discard verified work when a commit cannot be made."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from wisense_os.contracts import RunMode, TaskRequest
from wisense_os.patch_executor import PlanBoundPatchExecutor
from wisense_os.plan import TaskPlan


class FakeModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def complete(self, messages, *, model, timeout_seconds: float = 120.0) -> str:
        return self.reply


class FakeRunner:
    def __init__(self, passed: bool) -> None:
        self.passed = passed

    def run(self, project_root: Path, targets: tuple[str, ...]) -> tuple[bool, str]:
        return self.passed, "fixture result"


def _request(root: Path) -> TaskRequest:
    return TaskRequest("Edit api", str(root), RunMode.ASK_BEFORE_CHANGES, "glm-5.2:cloud", "gemma4:31b-cloud")


def _plan() -> TaskPlan:
    return TaskPlan("Edit api", "test", ("app.py", "test_app.py"), ("c",), ("a",))


def _candidate() -> str:
    return json.dumps({"files": [
        {"path": "app.py", "content": "after app\n"},
        {"path": "test_app.py", "content": "after test\n"},
    ]})


def _setup(root: Path) -> None:
    (root / "app.py").write_text("before app\n", encoding="utf-8")
    (root / "test_app.py").write_text("before test\n", encoding="utf-8")


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_commit_is_scoped_to_reviewed_files_only(tmp_path: Path) -> None:
    _setup(tmp_path)
    (tmp_path / "unrelated.txt").write_text("committed baseline\n", encoding="utf-8")
    _git(["init"], tmp_path)
    _git(["config", "user.email", "t@t"], tmp_path)
    _git(["config", "user.name", "t"], tmp_path)
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "baseline"], tmp_path)
    # an unrelated uncommitted local change that must NOT be swept in
    (tmp_path / "unrelated.txt").write_text("local edit\n", encoding="utf-8")

    executor = PlanBoundPatchExecutor(FakeModel(_candidate()), FakeRunner(True), commit_on_success=True)
    result = executor.run(_request(tmp_path), _plan())

    assert result["committed"] is True
    assert result["reply"].startswith("committed (")
    show = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=tmp_path, capture_output=True, text=True).stdout
    assert "app.py" in show and "test_app.py" in show
    assert "unrelated.txt" not in show
    # the unrelated local change is preserved, not committed and not reverted
    assert (tmp_path / "unrelated.txt").read_text(encoding="utf-8") == "local edit\n"
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True).stdout
    assert "unrelated.txt" in status


def test_commit_failure_keeps_validated_files(tmp_path: Path) -> None:
    # tmp_path is NOT a git repo -> commit cannot be made. The validated
    # change must remain on disk and be reported uncommitted, never failed.
    _setup(tmp_path)
    executor = PlanBoundPatchExecutor(FakeModel(_candidate()), FakeRunner(True), commit_on_success=True)
    result = executor.run(_request(tmp_path), _plan())

    assert result["committed"] is False
    assert "failed" not in result
    assert result["reply"].startswith("validated, uncommitted (")
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "after app\n"


def test_commit_disabled_by_default_stays_uncommitted(tmp_path: Path) -> None:
    _setup(tmp_path)
    executor = PlanBoundPatchExecutor(FakeModel(_candidate()), FakeRunner(True))
    result = executor.run(_request(tmp_path), _plan())

    assert result["reply"] == "validated, uncommitted: reviewed files changed and named tests passed"
    assert "committed" not in result
