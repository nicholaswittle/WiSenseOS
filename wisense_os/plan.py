"""Evidence-backed task-plan drafting with no model or write surface.

This is the native contract a future local/cloud planning adapter must fill.
The initial drafter deliberately recognizes only a narrow, inspectable REST
endpoint shape; unknown requests refuse rather than invent files.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any


_ENDPOINT = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+`?(/api/v\d+/[\w/-]+)`?", re.IGNORECASE)


@dataclass(frozen=True)
class TaskPlan:
    title: str
    summary: str
    files: tuple[str, ...]
    api_contract: tuple[str, ...]
    acceptance: tuple[str, ...]
    source: str = "evidence"

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        for name in ("files", "api_contract", "acceptance"):
            data[name] = list(data[name])
        return data


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


def _first_matching(root: Path, pattern: str, required_text: str) -> Path | None:
    if not root.is_dir():
        return None
    for candidate in sorted(root.rglob(pattern)):
        if not candidate.is_file() or ".git" in candidate.parts:
            continue
        try:
            if required_text in candidate.read_text(encoding="utf-8"):
                return candidate
        except OSError:
            continue
    return None
