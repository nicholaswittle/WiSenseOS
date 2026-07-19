"""Read-only ContextEnvelope builder — no writes, no model required.

Uses the file-finder ladder plus bounded snippet extraction so plan drafting
and talk-only answers can cite verified files before any mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from .file_finder import (
    ResolveResult,
    extract_identifiers,
    resolve_target_file,
    _iter_source,
    _safe_rel,
)


@dataclass(frozen=True)
class FileSnippet:
    path: str
    start_line: int
    text: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextEnvelope:
    """Verified read-only exploration result for one task request."""

    project_root: str
    target: str | None
    resolve_status: str
    resolve_reason: str
    candidates: tuple[str, ...]
    snippets: tuple[FileSnippet, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "target": self.target,
            "resolve_status": self.resolve_status,
            "resolve_reason": self.resolve_reason,
            "candidates": list(self.candidates),
            "snippets": [snippet.to_json() for snippet in self.snippets],
        }


def _snippet_for(path: Path, relative: str, identifiers: set[str], *, max_chars: int = 1200) -> FileSnippet | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not lines:
        return None
    hit_line = 0
    for index, line in enumerate(lines):
        if any(ident in line for ident in identifiers):
            hit_line = index
            break
    start = max(0, hit_line - 3)
    end = min(len(lines), hit_line + 12)
    text = "\n".join(lines[start:end])
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…"
    return FileSnippet(path=relative, start_line=start + 1, text=text)


def explore_project(project_root: Path, request: str) -> ContextEnvelope:
    """Build a ContextEnvelope from deterministic search only."""
    root = project_root.resolve()
    resolved: ResolveResult = resolve_target_file(root, request)
    identifiers = extract_identifiers(request)
    snippets: list[FileSnippet] = []

    paths: list[str] = []
    if resolved.status == "resolved" and resolved.file:
        paths = [resolved.file]
    elif resolved.status == "ambiguous":
        paths = list(resolved.candidates[:3])

    for relative in paths:
        absolute = root / relative
        snippet = _snippet_for(absolute, relative, identifiers)
        if snippet is not None:
            snippets.append(snippet)

    # If nothing resolved, still surface up to two lightly matching files.
    if not snippets and identifiers:
        scored: list[tuple[int, str, Path]] = []
        for path in _iter_source(root):
            rel = _safe_rel(root, path)
            if rel is None:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            score = sum(1 for ident in identifiers if ident in content or ident.lower() in path.stem.lower())
            if score:
                scored.append((score, rel, path))
        scored.sort(key=lambda item: (-item[0], item[1]))
        for _, rel, path in scored[:2]:
            snippet = _snippet_for(path, rel, identifiers)
            if snippet is not None:
                snippets.append(snippet)

    return ContextEnvelope(
        project_root=str(root),
        target=resolved.file,
        resolve_status=resolved.status,
        resolve_reason=resolved.reason,
        candidates=resolved.candidates,
        snippets=tuple(snippets),
    )
