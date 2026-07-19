"""Strict model-output contract for native plan-bound edits."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping

from .plan import TaskPlan
from .workspace import WorkspacePlanError, WorkspaceSnapshot


class PatchProtocolError(ValueError):
    """Untrusted model output did not match the reviewed plan."""


@dataclass(frozen=True)
class PatchCandidate:
    files: Mapping[str, str]


def parse_patch_candidate(raw: str, plan: TaskPlan) -> PatchCandidate:
    """Accept only a JSON full-content proposal for exactly the reviewed files."""
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PatchProtocolError("candidate is not valid JSON") from exc
    entries = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        raise PatchProtocolError("candidate needs a non-empty files list")
    expected = set(plan.files)
    files: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PatchProtocolError("candidate file entry is not an object")
        path, content = entry.get("path"), entry.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            raise PatchProtocolError("candidate file needs string path and content")
        if path in files:
            raise PatchProtocolError(f"candidate repeats reviewed path: {path}")
        if path not in expected:
            raise PatchProtocolError(f"candidate changes an unreviewed path: {path}")
        if len(content.encode("utf-8")) > 512_000:
            raise PatchProtocolError(f"candidate content is too large: {path}")
        files[path] = content
    if set(files) != expected:
        missing = sorted(expected - set(files))
        raise PatchProtocolError(f"candidate omits reviewed paths: {', '.join(missing)}")
    return PatchCandidate(files)


def apply_candidate(snapshot: WorkspaceSnapshot, candidate: PatchCandidate) -> None:
    """Write the validated candidate only inside the exact snapshot scope."""
    expected = set(snapshot.files)
    if set(candidate.files) != expected:
        raise WorkspacePlanError("candidate does not match snapshotted file scope")
    for relative, content in candidate.files.items():
        target = (snapshot.root / relative).resolve()
        if snapshot.root not in target.parents:
            raise WorkspacePlanError(f"candidate path escapes project root: {relative}")
        target.write_text(content, encoding="utf-8", newline="\n")
