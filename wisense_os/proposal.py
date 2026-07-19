"""Digest and unified-diff helpers for write proposals."""

from __future__ import annotations

from difflib import unified_diff
import hashlib
import json
from pathlib import Path
from typing import Mapping


def proposal_digest(files: Mapping[str, str]) -> str:
    """Stable SHA-256 over the exact candidate contents awaiting approval."""
    canonical = json.dumps(
        {path: files[path] for path in sorted(files)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def unified_file_diff(*, path: str, before: str, after: str) -> str:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    return "\n".join(
        unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def diffs_against_workspace(project_root: Path, files: Mapping[str, str]) -> dict[str, str]:
    root = project_root.resolve()
    diffs: dict[str, str] = {}
    for relative, after in files.items():
        target = root / relative
        before = target.read_text(encoding="utf-8") if target.is_file() else ""
        diffs[relative] = unified_file_diff(path=relative, before=before, after=after)
    return diffs
