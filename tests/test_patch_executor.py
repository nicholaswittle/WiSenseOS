from __future__ import annotations

import json
from pathlib import Path

from wisense_os.contracts import RunMode, TaskRequest
from wisense_os.patch_executor import PlanBoundPatchExecutor
from wisense_os.plan import TaskPlan


class FakeModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages: list[dict[str, str]] | None = None

    def complete(self, messages: list[dict[str, str]], *, model: str, timeout_seconds: float = 120.0) -> str:
        self.messages = messages
        return self.reply


class FakeRunner:
    def __init__(self, passed: bool, detail: str = "fixture result") -> None:
        self.passed = passed
        self.detail = detail
        self.targets: tuple[str, ...] | None = None

    def run(self, project_root: Path, targets: tuple[str, ...]) -> tuple[bool, str]:
        self.targets = targets
        return self.passed, self.detail


def request(root: Path) -> TaskRequest:
    return TaskRequest("Add version", str(root), RunMode.ASK_BEFORE_CHANGES, "glm-5.2:cloud", "gemma4:31b-cloud")


def plan() -> TaskPlan:
    return TaskPlan("Version", "test", ("wisense_os/api.py", "tests/test_api.py"), ("contract",), ("acceptance",))


def setup_files(root: Path) -> None:
    (root / "wisense_os").mkdir()
    (root / "wisense_os" / "api.py").write_text("before api", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_api.py").write_text("before test", encoding="utf-8")


def test_native_executor_applies_only_validated_candidate_then_runs_named_fixture(tmp_path: Path) -> None:
    setup_files(tmp_path)
    model = FakeModel(json.dumps({"files": [
        {"path": "wisense_os/api.py", "content": "after api"},
        {"path": "tests/test_api.py", "content": "after test"},
    ]}))
    runner = FakeRunner(True)

    result = PlanBoundPatchExecutor(model, runner).run(request(tmp_path), plan())

    assert result["reply"] == "validated, uncommitted: reviewed files changed and named tests passed"
    assert runner.targets == ("tests/test_api.py",)
    assert (tmp_path / "wisense_os" / "api.py").read_text(encoding="utf-8") == "after api"


def test_native_executor_restores_snapshot_when_named_fixture_fails(tmp_path: Path) -> None:
    setup_files(tmp_path)
    model = FakeModel(json.dumps({"files": [
        {"path": "wisense_os/api.py", "content": "after api"},
        {"path": "tests/test_api.py", "content": "after test"},
    ]}))

    result = PlanBoundPatchExecutor(model, FakeRunner(False, "expected failure")).run(request(tmp_path), plan())

    assert result["failed"] is True
    assert "restored files" in result["reason"]
    assert (tmp_path / "wisense_os" / "api.py").read_text(encoding="utf-8") == "before api"
