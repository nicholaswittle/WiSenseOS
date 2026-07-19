from __future__ import annotations

import json
from pathlib import Path

from wisense_os.contracts import RunMode, TaskRequest
from wisense_os.patch_executor import PlanBoundPatchExecutor
from wisense_os.plan import TaskPlan
from wisense_os.proposal import proposal_digest


class FakeModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, messages: list[dict[str, str]], *, model: str, timeout_seconds: float = 120.0) -> str:
        self.calls += 1
        return self.reply


class FakeRunner:
    def run(self, project_root: Path, targets: tuple[str, ...]) -> tuple[bool, str]:
        return True, "ok"


def test_propose_returns_digest_and_diffs_without_writing(tmp_path: Path) -> None:
    (tmp_path / "wisense_os").mkdir()
    (tmp_path / "wisense_os" / "api.py").write_text("before api\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_api.py").write_text("before test\n", encoding="utf-8")
    candidate = {
        "files": [
            {"path": "wisense_os/api.py", "content": "after api\n"},
            {"path": "tests/test_api.py", "content": "after test\n"},
        ]
    }
    model = FakeModel(json.dumps(candidate))
    request = TaskRequest(
        "Add version", str(tmp_path), RunMode.ASK_BEFORE_CHANGES, "glm-5.2:cloud", "gemma4:31b-cloud",
    )
    plan = TaskPlan(
        "Version", "test", ("wisense_os/api.py", "tests/test_api.py"), ("contract",), ("acceptance",),
    )

    result = PlanBoundPatchExecutor(model, FakeRunner()).propose(request, plan)

    assert "failed" not in result
    assert result["digest"] == proposal_digest({
        "wisense_os/api.py": "after api\n",
        "tests/test_api.py": "after test\n",
    })
    assert "after api" in result["proposal"]["diffs"]["wisense_os/api.py"]  # type: ignore[index]
    assert (tmp_path / "wisense_os" / "api.py").read_text(encoding="utf-8") == "before api\n"
    assert model.calls == 1


def test_apply_proposal_writes_only_after_explicit_candidate(tmp_path: Path) -> None:
    (tmp_path / "wisense_os").mkdir()
    (tmp_path / "wisense_os" / "api.py").write_text("before api", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_api.py").write_text("before test", encoding="utf-8")
    files = {
        "wisense_os/api.py": "after api",
        "tests/test_api.py": "after test",
    }
    request = TaskRequest(
        "Add version", str(tmp_path), RunMode.ASK_BEFORE_CHANGES, "glm-5.2:cloud", "gemma4:31b-cloud",
    )
    plan = TaskPlan(
        "Version", "test", ("wisense_os/api.py", "tests/test_api.py"), ("contract",), ("acceptance",),
    )

    result = PlanBoundPatchExecutor(FakeModel("{}"), FakeRunner()).apply_proposal(request, plan, files)

    assert result["reply"] == "validated, uncommitted: reviewed files changed and named tests passed"
    assert (tmp_path / "wisense_os" / "api.py").read_text(encoding="utf-8") == "after api"
