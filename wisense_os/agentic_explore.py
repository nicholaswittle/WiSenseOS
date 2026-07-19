"""Agentic read-only explore: local model + bounded glob/grep/read tools.

Writing remains outside this module. Cloud models are refused by default
so raw repository content does not transit a cloud boundary wholesale;
plan-draft may opt in with ``allow_cloud=True`` (tighter caps + redaction).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any, Callable

from .exploration_tools import TOOL_SCHEMAS, dispatch_tool_call
from .file_finder import is_safe_project_relative_file


_MAX_TURNS = 6
_MAX_TOOL_RESULT_CHARS = 6000
_CLOUD_MAX_TURNS = 4
_CLOUD_MAX_TOOL_RESULT_CHARS = 1500
_MAX_ANSWER_CHARS = 4000
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

ChatRespFn = Callable[..., dict[str, Any]]


def is_cloud_model(model: str) -> bool:
    name = model.lower()
    return name.endswith(":cloud") or "-cloud" in name or name.startswith("gpt-")


@dataclass(frozen=True)
class ExplorationAnswer:
    ok: bool
    answer: str = ""
    reason: str = ""
    tool_trace: tuple[str, ...] = ()
    turns: int = 0


@dataclass(frozen=True)
class LocatedTarget:
    ok: bool
    target_file: str = ""
    reason: str = ""
    problem: str = ""
    tool_trace: tuple[str, ...] = ()


def _trace_entry(name: str, args: Any) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    if not isinstance(args, dict):
        args = {}
    key = args.get("path") or args.get("pattern") or ""
    return f"{name}({key})" if key else f"{name}()"


def _bounded_result(result: dict, *, max_chars: int = _MAX_TOOL_RESULT_CHARS) -> dict:
    content = result.get("content")
    if isinstance(content, str) and len(content) > max_chars:
        return {
            **result,
            "content": content[:max_chars],
            "truncated": True,
        }
    # Also bound grep match text bundles that pack into JSON later.
    matches = result.get("matches")
    if isinstance(matches, list) and matches:
        packed = json.dumps(matches)
        if len(packed) > max_chars:
            return {
                **result,
                "matches": matches[: max(1, len(matches) // 2)],
                "truncated": True,
            }
    return result


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


_ANSWER_SYSTEM = (
    "You are a local coding assistant answering a question about the "
    "user's project. Use tools (glob_files, grep_files, read_file) to LOOK "
    "at real files before answering. Never claim to have read a file you "
    "did not read via a tool. You are read-only. When done, answer plainly "
    "and cite paths you actually looked at."
)

_LOCATE_SYSTEM = (
    "You are a local coding assistant. The user described a change but "
    "may not have named a file. Use tools to find the ONE existing file "
    "where that change belongs. You are read-only. When confident, respond "
    'with ONLY JSON: {"target_file": "<project-relative path>", "reason": "..."}. '
    'If unclear: {"target_file": null, "reason": "..."}.'
)


def answer_with_exploration(
    question: str,
    project_root: Path,
    model: str,
    *,
    chat_resp_fn: ChatRespFn,
    max_turns: int = _MAX_TURNS,
) -> ExplorationAnswer:
    # Cloud is refused: tool loops stream raw repo content. Use deterministic
    # explore + redacted complete_text for cloud Talk Only instead.
    if is_cloud_model(model):
        return ExplorationAnswer(ok=False, reason="cloud_model_refused")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _ANSWER_SYSTEM},
        {"role": "user", "content": question},
    ]
    trace: list[str] = []
    turns = 0
    try:
        for _ in range(max_turns):
            turns += 1
            response = chat_resp_fn(messages, model=model, tools=TOOL_SCHEMAS)
            tool_calls = response.get("tool_calls")
            messages.append(response)
            if not tool_calls:
                answer = (response.get("content") or "").strip()
                if not answer:
                    return ExplorationAnswer(
                        ok=False,
                        reason="no_answer",
                        tool_trace=tuple(trace),
                        turns=turns,
                    )
                return ExplorationAnswer(
                    ok=True,
                    answer=answer[:_MAX_ANSWER_CHARS],
                    tool_trace=tuple(trace),
                    turns=turns,
                )
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})
                trace.append(_trace_entry(name, args))
                result = _bounded_result(dispatch_tool_call(project_root, name, args))
                messages.append({
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(result),
                })
        messages.append({
            "role": "user",
            "content": (
                "Exploration limit reached. Answer now from what you already "
                "read; if evidence is insufficient, say so plainly."
            ),
        })
        response = chat_resp_fn(messages, model=model)
        answer = (response.get("content") or "").strip()
        if not answer:
            return ExplorationAnswer(
                ok=False, reason="no_answer", tool_trace=tuple(trace), turns=turns,
            )
        return ExplorationAnswer(
            ok=True,
            answer=answer[:_MAX_ANSWER_CHARS],
            tool_trace=tuple(trace),
            turns=turns,
        )
    except Exception as exc:  # noqa: BLE001 — fail closed into caller fallback
        return ExplorationAnswer(
            ok=False,
            reason=f"model_error: {type(exc).__name__}: {exc}",
            tool_trace=tuple(trace),
            turns=turns,
        )


def locate_target_with_exploration(
    description: str,
    project_root: Path,
    model: str,
    *,
    chat_resp_fn: ChatRespFn,
    max_turns: int | None = None,
    allow_cloud: bool = False,
) -> LocatedTarget:
    """Locate one existing file via read-only tools.

    Cloud is refused unless ``allow_cloud=True``. Cloud mode uses tighter
    turn/result caps; tool content is redacted by exploration_tools.
    """
    cloud = is_cloud_model(model)
    if cloud and not allow_cloud:
        return LocatedTarget(ok=False, problem="cloud_model_refused")

    turns_limit = max_turns if max_turns is not None else (
        _CLOUD_MAX_TURNS if cloud else _MAX_TURNS
    )
    result_cap = _CLOUD_MAX_TOOL_RESULT_CHARS if cloud else _MAX_TOOL_RESULT_CHARS

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _LOCATE_SYSTEM},
        {"role": "user", "content": f"Change request: {description}"},
    ]
    trace: list[str] = []
    response: dict[str, Any] = {}
    try:
        for _ in range(turns_limit):
            response = chat_resp_fn(messages, model=model, tools=TOOL_SCHEMAS)
            tool_calls = response.get("tool_calls")
            messages.append(response)
            if not tool_calls:
                break
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})
                trace.append(_trace_entry(name, args))
                result = _bounded_result(
                    dispatch_tool_call(project_root, name, args),
                    max_chars=result_cap,
                )
                messages.append({
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(result),
                })
        else:
            messages.append({
                "role": "user",
                "content": "Exploration limit reached. Give your JSON answer now.",
            })
            response = chat_resp_fn(messages, model=model)
    except Exception as exc:  # noqa: BLE001
        return LocatedTarget(
            ok=False,
            problem=f"model_error: {type(exc).__name__}: {exc}",
            tool_trace=tuple(trace),
        )

    parsed = _extract_json(response.get("content") or "")
    if not isinstance(parsed, dict):
        return LocatedTarget(ok=False, problem="not_located", tool_trace=tuple(trace))
    target = parsed.get("target_file")
    if not isinstance(target, str) or not target.strip():
        return LocatedTarget(ok=False, problem="not_located", tool_trace=tuple(trace))
    target = target.strip().replace("\\", "/")
    if not is_safe_project_relative_file(project_root, target):
        return LocatedTarget(ok=False, problem="not_located", tool_trace=tuple(trace))
    reason = parsed.get("reason")
    reason = reason[:300] if isinstance(reason, str) else ""
    return LocatedTarget(
        ok=True,
        target_file=target,
        reason=reason,
        tool_trace=tuple(trace),
    )
