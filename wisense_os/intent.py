"""Intent classification: deterministic floor, optional model ceiling.

Rules from the LAWC audit this ports:
- Model only classifies; it gains no write authority.
- Deterministic task matches are never suppressed by a model "chat" guess
  (that silent no-op is exactly what this exists to kill).
- Model answers are validated; bad/unparseable output falls back to the floor.
- Cloud classification is allowed only through the same redacting chat path
  the engine already uses (complete_text).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from .file_finder import find_by_identifiers, resolve_target_file


INTENT_KINDS = frozenset({"edit", "create", "review", "question", "chat", "audit"})

_EDIT_FLOOR = re.compile(
    r"\b(fix|bug|broken|crash|failing|fails|error|repair|patch|update|change|refactor|implement)\b",
    re.IGNORECASE,
)
_CREATE_FLOOR = re.compile(
    r"\b(create|add|new file|scaffold|generate)\b.+\.\w+\b",
    re.IGNORECASE,
)
_QUESTION_FLOOR = re.compile(
    r"^\s*(what|why|how|where|when|who|which|explain|describe|tell me)\b|\?\s*$",
    re.IGNORECASE,
)
_AUDIT_FLOOR = re.compile(
    r"\b(audit|review)\b.+\b(project|codebase|everything|all files)\b",
    re.IGNORECASE,
)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class ParsedIntent:
    kind: str
    target_file: str | None
    reason: str
    source: str = "floor"

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


ChatFn = Callable[..., str]


def classify_intent_floor(message: str, project_root: Path) -> ParsedIntent:
    """Always-available deterministic classification."""
    text = message.strip()
    resolved = resolve_target_file(project_root, text)
    target = resolved.file if resolved.status == "resolved" else None

    if _AUDIT_FLOOR.search(text):
        return ParsedIntent("audit", None, "whole-project audit wording", "floor")
    if _CREATE_FLOOR.search(text):
        return ParsedIntent("create", target, "create/new-file wording", "floor")
    if _EDIT_FLOOR.search(text) or (target and not _QUESTION_FLOOR.search(text)):
        return ParsedIntent(
            "edit",
            target,
            "edit/fix wording" if _EDIT_FLOOR.search(text) else "resolved target implies edit",
            "floor",
        )
    if _QUESTION_FLOOR.search(text):
        return ParsedIntent("question", target, "question wording", "floor")
    return ParsedIntent("chat", target, "no task wording matched", "floor")


def _safe_existing_relative(project_root: Path, rel: str) -> bool:
    normalized = rel.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.name:
        return False
    candidate = project_root / normalized
    try:
        candidate.resolve().relative_to(project_root.resolve())
    except (OSError, ValueError):
        return False
    return candidate.is_file()


def _extract_json(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(raw)
        if match is None:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _validate_model_intent(parsed: dict[str, Any], project_root: Path) -> ParsedIntent | None:
    kind = parsed.get("kind")
    if kind not in INTENT_KINDS:
        return None
    target = parsed.get("target_file")
    if target is not None and not isinstance(target, str):
        return None
    if isinstance(target, str):
        target = target.strip().replace("\\", "/")
        if not target or target.lower() in {"null", "none"}:
            target = None
    if kind == "audit":
        target = None
    if target is not None and kind in {"edit", "review", "question"}:
        if not _safe_existing_relative(project_root, target):
            return None
    reason = parsed.get("reason")
    reason = reason[:200] if isinstance(reason, str) else ""
    return ParsedIntent(kind=kind, target_file=target, reason=reason, source="model")


def merge_intent(floor: ParsedIntent, model: ParsedIntent | None) -> ParsedIntent:
    """Widen task detection; never demote a floor task match to chat/question."""
    if model is None:
        return floor
    if floor.kind in {"edit", "create", "audit", "review"} and model.kind in {"chat", "question"}:
        return floor
    if floor.kind in {"chat", "question"} and model.kind in {"edit", "create", "audit", "review"}:
        return model
    # Prefer model target when floor had none and model target is trusted.
    if floor.kind == model.kind and floor.target_file is None and model.target_file:
        return model
    return floor if floor.kind in {"edit", "create"} else model


def classify_intent(
    message: str,
    project_root: Path,
    *,
    model: str | None = None,
    chat_fn: ChatFn | None = None,
) -> ParsedIntent:
    """Classify with floor + optional model widening."""
    floor = classify_intent_floor(message, project_root)
    if model is None or chat_fn is None:
        return floor

    candidates = list(find_by_identifiers(project_root, message)[:8])
    if floor.target_file and floor.target_file not in candidates:
        candidates.insert(0, floor.target_file)
    listing = "\n".join(f"- {c}" for c in candidates) or "(no candidate files found)"
    messages = [
        {
            "role": "system",
            "content": (
                "You route requests for a local coding assistant. Reply ONLY with JSON: "
                '{"kind":"edit|create|review|question|chat|audit","target_file":"...|null","reason":"..."}. '
                "Prefer candidate files. Never use absolute paths or '..'."
            ),
        },
        {
            "role": "user",
            "content": f"Candidate files:\n{listing}\n\nUser request: {message}",
        },
    ]
    try:
        raw = chat_fn(messages, model=model, timeout_seconds=30)
    except Exception:
        return floor
    parsed = _extract_json(raw or "")
    if parsed is None:
        return floor
    model_intent = _validate_model_intent(parsed, project_root)
    return merge_intent(floor, model_intent)
