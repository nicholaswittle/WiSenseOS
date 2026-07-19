"""Evidence-backed task-plan drafting with no model or write surface.

This is the native contract a future local/cloud planning adapter must fill.
The initial drafter deliberately recognizes only a narrow, inspectable REST
endpoint shape; unknown requests refuse rather than invent files.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any, Mapping

from .explore import explore_project
from .file_finder import resolve_target_file


_ENDPOINT = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+`?(/api/v\d+/[\w/-]+)`?", re.IGNORECASE)
_PY_FILE = re.compile(r"\b([\w./-]+\.py)\b")


@dataclass(frozen=True)
class TaskPlan:
    title: str
    summary: str
    files: tuple[str, ...]
    api_contract: tuple[str, ...]
    acceptance: tuple[str, ...]
    source: str = "evidence"
    create_files: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        for name in ("files", "api_contract", "acceptance", "create_files"):
            data[name] = list(data[name])
        return data

    @classmethod
    def from_json(cls, payload: Mapping[str, object]) -> "TaskPlan":
        def text_list(name: str) -> tuple[str, ...]:
            value = payload.get(name)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"invalid task plan {name}")
            return tuple(value)

        title = payload.get("title")
        summary = payload.get("summary")
        source = payload.get("source", "evidence")
        if not all(isinstance(value, str) and value.strip() for value in (title, summary, source)):
            raise ValueError("invalid task plan text")
        create_files = payload.get("create_files", [])
        if not isinstance(create_files, list) or not all(isinstance(item, str) for item in create_files):
            raise ValueError("invalid task plan create_files")
        return cls(
            title, summary, text_list("files"), text_list("api_contract"), text_list("acceptance"),
            source, tuple(create_files),
        )


@dataclass(frozen=True)
class PlanDraftResult:
    ok: bool
    reason: str = ""
    plan: TaskPlan | None = None


def draft_evidence_plan(request: str, project_root: Path) -> PlanDraftResult:
    """Produce a bounded plan only when source evidence identifies both files."""
    match = _ENDPOINT.search(request)
    if match is None:
        return PlanDraftResult(False, "evidence_plan_unavailable")
    method, route = match.group(1).upper(), match.group(2)
    api_file = _first_matching(project_root, "api.py", "Flask")
    test_file = _first_matching(project_root / "tests", "test_*.py", "test_client")
    if api_file is None or test_file is None:
        return PlanDraftResult(False, "evidence_files_not_found")
    api_rel = api_file.relative_to(project_root).as_posix()
    test_rel = test_file.relative_to(project_root).as_posix()
    plan = TaskPlan(
        title=f"Add {method} {route}",
        summary="Extend the existing Flask API and its existing deterministic API fixture.",
        files=(api_rel, test_rel),
        api_contract=(f"{method} {route} returns the requested JSON payload.",),
        acceptance=(
            f"The {method} {route} route is registered in the existing Flask app.",
            f"The existing no-network fixture verifies {method} {route}.",
            "No unrelated files are modified.",
        ),
    )
    return PlanDraftResult(True, plan=plan)


def _is_test_name(relative: str) -> bool:
    name = Path(relative).name
    return name.startswith("test_") or name.endswith("_test.py")


def _named_existing_py_files(request: str, root: Path) -> list[str]:
    named: list[str] = []
    for match in _PY_FILE.finditer(request):
        rel = match.group(1).replace("\\", "/")
        candidate = (root / rel)
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        if candidate.is_file() and rel not in named:
            named.append(rel)
    return named


def _locate_test_for(root: Path, impl_rel: str, named: list[str]) -> str | None:
    """Find the ONE test that covers impl_rel, or None (refuse rather than
    guess). Signals, strongest first: a test explicitly named in the
    request; the test_<stem>.py / <stem>_test.py convention; a test file
    importing the module. Ambiguity returns None."""
    explicit_tests = [rel for rel in named if _is_test_name(rel)]
    if len(explicit_tests) == 1:
        return explicit_tests[0]
    if len(explicit_tests) > 1:
        return None

    stem = Path(impl_rel).stem
    convention = {f"test_{stem}.py", f"{stem}_test.py"}
    by_convention = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*.py")
        if p.name in convention and "__pycache__" not in p.parts
    )
    if len(by_convention) == 1:
        return by_convention[0]
    if len(by_convention) > 1:
        return None

    module = impl_rel[:-3].replace("/", ".")
    importers: list[str] = []
    for path in root.rglob("*.py"):
        if not _is_test_name(path.relative_to(root).as_posix()) or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(rf"\b(import|from)\s+{re.escape(module)}\b", text) or \
                re.search(rf"\b(import|from)\s+{re.escape(stem)}\b", text):
            importers.append(path.relative_to(root).as_posix())
    return importers[0] if len(importers) == 1 else None


def draft_edit_plan(request: str, project_root: Path) -> PlanDraftResult:
    """Draft a bounded EDIT plan when exactly one implementation file and
    its covering test can be located.

    Uses the file-finder ladder when the request does not literally name a
    path. The human still reviews the drafted files before approval.
    """
    root = project_root
    if not root.is_dir():
        return PlanDraftResult(False, "project_root_missing")
    named = _named_existing_py_files(request, root)
    impls = [rel for rel in named if not _is_test_name(rel)]
    unique_impls = set(impls)
    if len(unique_impls) > 1:
        return PlanDraftResult(False, "edit_plan_needs_one_named_existing_file")
    if len(unique_impls) == 1:
        impl_rel = next(iter(unique_impls))
    else:
        # No literal path — use the deterministic resolve ladder (still no writes).
        resolved = resolve_target_file(root, request)
        if resolved.status != "resolved" or not resolved.file:
            if resolved.status == "ambiguous":
                return PlanDraftResult(
                    False,
                    f"edit_plan_ambiguous:{','.join(resolved.candidates[:5])}",
                )
            return PlanDraftResult(False, "edit_plan_needs_one_named_existing_file")
        if _is_test_name(resolved.file) or not resolved.file.endswith(".py"):
            return PlanDraftResult(False, "edit_plan_needs_one_named_existing_file")
        impl_rel = resolved.file
    test_rel = _locate_test_for(root, impl_rel, named)
    if test_rel is None:
        return PlanDraftResult(False, "edit_plan_test_not_found")
    if test_rel == impl_rel:
        return PlanDraftResult(False, "edit_plan_needs_a_distinct_test")
    envelope = explore_project(root, request)
    summary = f"Apply the requested change to {impl_rel} and verify it with {test_rel}."
    if envelope.snippets:
        summary += f" Explorer cited {len(envelope.snippets)} verified snippet(s)."
    plan = TaskPlan(
        title=f"Edit {Path(impl_rel).name}",
        summary=summary,
        files=(impl_rel, test_rel),
        api_contract=("Preserve the existing public interface unless the request requires a change.",),
        acceptance=(f"{test_rel} passes.", "No unrelated files are modified."),
        source="explore" if envelope.target else "evidence",
    )
    return PlanDraftResult(True, plan=plan)


def _first_matching(root: Path, pattern: str, required_text: str) -> Path | None:
    if not root.is_dir():
        return None
    for candidate in sorted(root.rglob(pattern)):
        relative_parts = candidate.relative_to(root).parts
        if (
            not candidate.is_file()
            or any(part.startswith(".") for part in relative_parts)
            or any(part in {"build", "__pycache__"} for part in relative_parts)
        ):
            continue
        try:
            if required_text in candidate.read_text(encoding="utf-8"):
                return candidate
        except OSError:
            continue
    return None
