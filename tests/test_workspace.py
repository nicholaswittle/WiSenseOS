from __future__ import annotations

from pathlib import Path

import pytest

from wisense_os.plan import TaskPlan
from wisense_os.workspace import WorkspacePlanError, restore_snapshot, snapshot_reviewed_files, validate_plan_files


def plan(*files: str) -> TaskPlan:
    return TaskPlan("Scoped edit", "test", files, ("contract",), ("acceptance",))


def test_snapshot_and_restore_touch_only_reviewed_existing_files(tmp_path: Path) -> None:
    target = tmp_path / "wisense_os" / "api.py"
    target.parent.mkdir()
    target.write_text("before", encoding="utf-8")
    unrelated = tmp_path / "README.md"
    unrelated.write_text("leave me", encoding="utf-8")

    snapshot = snapshot_reviewed_files(tmp_path, plan("wisense_os/api.py"))
    target.write_text("after", encoding="utf-8")
    restore_snapshot(snapshot)

    assert target.read_text(encoding="utf-8") == "before"
    assert unrelated.read_text(encoding="utf-8") == "leave me"


@pytest.mark.parametrize("relative", ["../outside.py", "C:/outside.py", ".pytest_tmp/a.py", ""])
def test_plan_rejects_escape_or_transient_paths(tmp_path: Path, relative: str) -> None:
    with pytest.raises(WorkspacePlanError):
        validate_plan_files(tmp_path, plan(relative))


def test_plan_rejects_missing_or_duplicate_edit_targets(tmp_path: Path) -> None:
    file = tmp_path / "api.py"
    file.write_text("x", encoding="utf-8")
    with pytest.raises(WorkspacePlanError, match="does not exist"):
        validate_plan_files(tmp_path, plan("missing.py"))
    with pytest.raises(WorkspacePlanError, match="duplicate"):
        validate_plan_files(tmp_path, plan("api.py", "api.py"))
