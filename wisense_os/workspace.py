"""Plan-bound local workspace operations for the native WiSense executor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .plan import TaskPlan


class WorkspacePlanError(ValueError):
    """A reviewed plan cannot safely operate in the selected workspace."""


@dataclass(frozen=True)
class FileSnapshot:
    existed: bool
    content: bytes = b""


@dataclass(frozen=True)
class WorkspaceSnapshot:
    root: Path
    files: Mapping[str, FileSnapshot]
    reviewed_paths: tuple[str, ...]
    created: tuple[str, ...] = ()


def validate_plan_files(project_root: Path, plan: TaskPlan) -> tuple[Path, ...]:
    """Resolve the reviewed file list under root, rejecting ambiguous inputs."""
    root = project_root.resolve()
    if not root.is_dir():
        raise WorkspacePlanError("project root is not an existing directory")
    if not plan.files:
        raise WorkspacePlanError("reviewed plan has no files")
    create_paths = set(plan.create_files)
    if len(create_paths) != len(plan.create_files) or not create_paths.issubset(set(plan.files)):
        raise WorkspacePlanError("reviewed create paths must be distinct declared plan files")
    seen: set[str] = set()
    resolved: list[Path] = []
    for relative in plan.files:
        normalized = relative.replace("\\", "/")
        candidate = Path(normalized)
        if candidate.is_absolute() or ".." in candidate.parts or not normalized or normalized.startswith("."):
            raise WorkspacePlanError(f"invalid reviewed path: {relative}")
        key = candidate.as_posix()
        if key in seen:
            raise WorkspacePlanError(f"duplicate reviewed path: {relative}")
        target = (root / candidate).resolve()
        if root not in target.parents:
            raise WorkspacePlanError(f"reviewed path escapes project root: {relative}")
        if relative in create_paths:
            if target.exists():
                raise WorkspacePlanError(f"reviewed create target already exists: {relative}")
            if not target.parent.is_dir():
                raise WorkspacePlanError(f"reviewed create parent does not exist: {relative}")
        elif not target.is_file():
            raise WorkspacePlanError(f"reviewed edit target does not exist: {relative}")
        seen.add(key)
        resolved.append(target)
    return tuple(resolved)


def snapshot_reviewed_files(project_root: Path, plan: TaskPlan) -> WorkspaceSnapshot:
    """Capture only the plan-reviewed files before an executor mutates them."""
    root = project_root.resolve()
    targets = validate_plan_files(root, plan)
    return WorkspaceSnapshot(
        root=root,
        files={
            target.relative_to(root).as_posix(): FileSnapshot(True, target.read_bytes())
            for target in targets if target.is_file()
        },
        reviewed_paths=tuple(target.relative_to(root).as_posix() for target in targets),
        created=tuple(plan.create_files),
    )


def restore_snapshot(snapshot: WorkspaceSnapshot) -> None:
    """Restore exactly the previously snapshotted files; no repository reset."""
    for relative, saved in snapshot.files.items():
        target = (snapshot.root / relative).resolve()
        if snapshot.root not in target.parents:
            raise WorkspacePlanError(f"snapshot path escapes project root: {relative}")
        if saved.existed:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(saved.content)
    for relative in snapshot.created:
        target = (snapshot.root / relative).resolve()
        if snapshot.root not in target.parents:
            raise WorkspacePlanError(f"snapshot path escapes project root: {relative}")
        if target.exists():
            if not target.is_file():
                raise WorkspacePlanError(f"created target is no longer a file: {relative}")
            target.unlink()
