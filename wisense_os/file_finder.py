"""Deterministic target-file resolution ladder (ported from LAWC principles).

Order: explicit path → unique basename → identifier match → fuzzy stem.
Refuses rather than guesses when ambiguous. No model call.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

_EXCLUDED = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".wisense_pytest"}
_SOURCE_EXT = {".py", ".dart", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
_FILENAME = re.compile(r"\b[\w./\\-]+\.[a-zA-Z]{1,5}\b")
_IDENTIFIER = re.compile(
    r"[`'\"]([A-Za-z_][A-Za-z0-9_]*)[`'\"]|\b([A-Za-z_][A-Za-z0-9_]{2,})\s*\("
)
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "file", "test",
    "fix", "edit", "add", "update", "change", "please", "project", "module",
}


@dataclass(frozen=True)
class ResolveResult:
    status: str  # resolved | ambiguous | not_found
    file: str | None = None
    candidates: tuple[str, ...] = ()
    reason: str = ""


def _iter_source(root: Path):
    root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _SOURCE_EXT:
            continue
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        # Only inspect path parts under the project root — parent dirs like
        # `.pytest_tmp` must not exclude every file in a temp workspace.
        if any(part in _EXCLUDED or part.startswith(".") for part in rel_parts):
            continue
        yield path


def _safe_rel(root: Path, path: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def find_explicit_filename(root: Path, text: str) -> Path | None:
    for match in _FILENAME.finditer(text):
        mentioned = match.group(0).replace("\\", "/")
        candidate = (root / mentioned)
        if candidate.is_file():
            rel = _safe_rel(root, candidate)
            if rel is not None:
                return candidate
        basename = Path(mentioned).name
        hits = [p for p in _iter_source(root) if p.name == basename]
        if len(hits) == 1:
            return hits[0]
    return None


def extract_identifiers(text: str) -> set[str]:
    found: set[str] = set()
    for match in _IDENTIFIER.finditer(text):
        token = match.group(1) or match.group(2)
        if token and token.lower() not in _STOP and len(token) >= 3:
            found.add(token)
    # Also pull meaningful words from the request for fuzzy stems.
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", text):
        if word.lower() not in _STOP:
            found.add(word)
    return found


def find_by_identifiers(root: Path, text: str) -> list[str]:
    ids = extract_identifiers(text)
    if not ids:
        return []
    scores: dict[str, int] = {}
    for path in _iter_source(root):
        rel = _safe_rel(root, path)
        if rel is None:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = 0
        for ident in ids:
            if re.search(rf"\b(def|class)\s+{re.escape(ident)}\b", content):
                score += 3
            elif ident in content:
                score += 1
            if ident.lower() in path.stem.lower():
                score += 2
        if score:
            scores[rel] = score
    if not scores:
        return []
    best = max(scores.values())
    return sorted(rel for rel, score in scores.items() if score == best)


def decisive_fuzzy_stem(root: Path, text: str) -> str | None:
    tokens = {t.lower() for t in extract_identifiers(text)}
    if not tokens:
        return None
    hits: list[str] = []
    for path in _iter_source(root):
        stem = path.stem.lower()
        if any(token in stem or stem in token for token in tokens if len(token) >= 4):
            rel = _safe_rel(root, path)
            if rel is not None:
                hits.append(rel)
    return hits[0] if len(hits) == 1 else None


def resolve_target_file(project_root: Path, task_description: str) -> ResolveResult:
    root = project_root
    if not root.is_dir():
        return ResolveResult("not_found", reason="project_root_missing")

    explicit = find_explicit_filename(root, task_description)
    if explicit is not None:
        rel = _safe_rel(root, explicit)
        if rel is not None:
            return ResolveResult("resolved", rel, reason="explicit filename found on disk")

    by_id = find_by_identifiers(root, task_description)
    if len(by_id) == 1:
        return ResolveResult("resolved", by_id[0], reason="only file matching identifiers")
    if len(by_id) > 1:
        return ResolveResult(
            "ambiguous", candidates=tuple(by_id[:8]),
            reason="multiple files match identifiers mentioned in the task",
        )

    if _FILENAME.search(task_description):
        return ResolveResult("not_found", reason="filename mention was not uniquely resolvable")

    fuzzy = decisive_fuzzy_stem(root, task_description)
    if fuzzy:
        return ResolveResult("resolved", fuzzy, reason="uniquely decisive fuzzy stem match")

    return ResolveResult("not_found", reason="no existing file uniquely matches the request")
