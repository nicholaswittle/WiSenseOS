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


def test_create_plan_removes_only_the_new_declared_file_on_restore(tmp_path: Path) -> None:
    existing = tmp_path / "app.py"
    existing.write_text("before", encoding="utf-8")
    task_plan = TaskPlan(
        "Add fixture", "test", ("app.py", "test_app.py"), ("contract",), ("acceptance",),
        create_files=("test_app.py",),
    )

    snapshot = snapshot_reviewed_files(tmp_path, task_plan)
    existing.write_text("after", encoding="utf-8")
    created = tmp_path / "test_app.py"
    created.write_text("new fixture", encoding="utf-8")
    restore_snapshot(snapshot)

    assert existing.read_text(encoding="utf-8") == "before"
    assert not created.exists()


def test_create_plan_refuses_existing_target_or_missing_parent(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x", encoding="utf-8")
    existing = TaskPlan("Create", "test", ("app.py",), ("contract",), ("acceptance",), create_files=("app.py",))
    missing_parent = TaskPlan("Create", "test", ("new/test_app.py",), ("contract",), ("acceptance",), create_files=("new/test_app.py",))

    with pytest.raises(WorkspacePlanError, match="already exists"):
        validate_plan_files(tmp_path, existing)
    with pytest.raises(WorkspacePlanError, match="parent does not exist"):
        validate_plan_files(tmp_path, missing_parent)
