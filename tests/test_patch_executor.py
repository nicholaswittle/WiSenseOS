from __future__ import annotations

import json
from pathlib import Path

from wisense_os.contracts import RunMode, TaskRequest
from wisense_os.patch_executor import PlanBoundPatchExecutor
from wisense_os.plan import TaskPlan


class FakeModel:
    def __init__(self, reply: str | list[str]) -> None:
        self.replies = [reply] if isinstance(reply, str) else reply
        self.messages: list[dict[str, str]] | None = None
        self.calls = 0

    def complete(self, messages: list[dict[str, str]], *, model: str, timeout_seconds: float = 120.0) -> str:
        self.messages = messages
        reply = self.replies[self.calls]
        self.calls += 1
        return reply


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
    failed_candidate = json.dumps({"files": [
        {"path": "wisense_os/api.py", "content": "after api"},
        {"path": "tests/test_api.py", "content": "after test"},
    ]})
    model = FakeModel([failed_candidate, failed_candidate])
    runner = FakeRunner(True)

    result = PlanBoundPatchExecutor(model, runner).run(request(tmp_path), plan())

    assert result["reply"] == "validated, uncommitted: reviewed files changed and named tests passed"
    assert runner.targets == ("tests/test_api.py",)
    assert (tmp_path / "wisense_os" / "api.py").read_text(encoding="utf-8") == "after api"


def test_native_executor_restores_snapshot_when_named_fixture_fails(tmp_path: Path) -> None:
    setup_files(tmp_path)
    failed_candidate = json.dumps({"files": [
        {"path": "wisense_os/api.py", "content": "after api"},
        {"path": "tests/test_api.py", "content": "after test"},
    ]})
    model = FakeModel([failed_candidate, failed_candidate])

    result = PlanBoundPatchExecutor(model, FakeRunner(False, "expected failure")).run(request(tmp_path), plan())

    assert result["failed"] is True
    assert "restored files" in result["reason"]
    assert model.calls == 2
    assert (tmp_path / "wisense_os" / "api.py").read_text(encoding="utf-8") == "before api"


def test_native_executor_allows_one_evidence_driven_repair(tmp_path: Path) -> None:
    setup_files(tmp_path)
    first = json.dumps({"files": [
        {"path": "wisense_os/api.py", "content": "bad first candidate"},
        {"path": "tests/test_api.py", "content": "bad first test"},
    ]})
    repaired = json.dumps({"files": [
        {"path": "wisense_os/api.py", "content": "fixed api"},
        {"path": "tests/test_api.py", "content": "fixed test"},
    ]})
    model = FakeModel([first, repaired])
    runner = SequencedRunner([False, True])

    result = PlanBoundPatchExecutor(model, runner).run(request(tmp_path), plan())

    assert "after one repair" in result["reply"]
    assert model.calls == 2
    assert "Named test failure" in model.messages[-1]["content"]
    assert (tmp_path / "wisense_os" / "api.py").read_text(encoding="utf-8") == "fixed api"


class SequencedRunner(FakeRunner):
    def __init__(self, outcomes: list[bool]) -> None:
        super().__init__(True)
        self.outcomes = outcomes

    def run(self, project_root: Path, targets: tuple[str, ...]) -> tuple[bool, str]:
        self.targets = targets
        return self.outcomes.pop(0), "evidence from named fixture"


def test_native_executor_removes_a_failed_declared_create_on_restore(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("before", encoding="utf-8")
    create_plan = TaskPlan(
        "Create fixture", "test", ("app.py", "test_app.py"), ("contract",), ("acceptance",),
        create_files=("test_app.py",),
    )
    model = FakeModel(json.dumps({"files": [
        {"path": "app.py", "content": "after"},
        {"path": "test_app.py", "content": "def test_example(): pass"},
    ]}))

    result = PlanBoundPatchExecutor(model, FakeRunner(False, "expected failure")).run(request(tmp_path), create_plan)

    assert result["failed"] is True
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "before"
    assert not (tmp_path / "test_app.py").exists()
