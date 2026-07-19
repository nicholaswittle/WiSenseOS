"""Deterministic project-nickname resolution over registered projects.

Advisory only: returns ranked candidates for a phrase ("the billing
project" -> a registered root); the caller confirms before a task binds
to a root. No model call. Projects whose root no longer exists are never
offered. Implements the nickname-resolution behavior named in the master
plan port manifest, as native standalone engine code.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from .contracts import ProjectRecord

_WORD = re.compile(r"[A-Za-z][a-z0-9]*|[A-Z]+(?![a-z])|[0-9]+")
_MIN_SCORE = 0.3
_DECISIVE_SCORE = 0.5
_DECISIVE_MARGIN = 0.2
_MAX_OFFERED = 5


def name_tokens(text: str) -> set[str]:
    """Lowercased word tokens, splitting underscores/hyphens/camelCase."""
    return {m.group(0).lower() for m in _WORD.finditer(text)}


@dataclass(frozen=True)
class ProjectMatch:
    project_id: str
    display_name: str
    root: str
    score: float


def _score(phrase_tokens: set[str], record: ProjectRecord) -> float:
    best = 0.0
    for name in (record.display_name, Path(record.root).name):
        tokens = name_tokens(name)
        if not tokens:
            continue
        overlap = len(phrase_tokens & tokens) / len(phrase_tokens | tokens)
        ratio = difflib.SequenceMatcher(
            None, " ".join(sorted(phrase_tokens)), name.lower()
        ).ratio()
        best = max(best, 0.6 * overlap + 0.4 * ratio)
    return best


def resolve_project_reference(
    phrase: str, projects: list[ProjectRecord]
) -> list[ProjectMatch]:
    """Ranked candidate projects for a phrase. Empty = unknown. ONE entry
    = uniquely decisive (still confirmed by the caller). Several = too
    close to choose; the caller must ask."""
    phrase_tokens = name_tokens(phrase)
    if not phrase_tokens:
        return []
    scored: list[ProjectMatch] = []
    for record in projects:
        if not Path(record.root).is_dir():
            continue  # dead path -- never offered
        value = _score(phrase_tokens, record)
        if value >= _MIN_SCORE:
            scored.append(ProjectMatch(
                record.project_id, record.display_name, record.root, round(value, 3)))
    scored.sort(key=lambda m: (-m.score, m.display_name.lower()))
    if not scored:
        return []
    top = scored[0]
    if top.score >= _DECISIVE_SCORE and (
            len(scored) == 1 or top.score - scored[1].score >= _DECISIVE_MARGIN):
        return [top]
    return scored[:_MAX_OFFERED]
