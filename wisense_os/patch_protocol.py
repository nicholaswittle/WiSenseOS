"""Strict model-output contract for native plan-bound edits."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Mapping

from .plan import TaskPlan
from .workspace import WorkspacePlanError, WorkspaceSnapshot


class PatchProtocolError(ValueError):
    """Untrusted model output did not match the reviewed plan."""


@dataclass(frozen=True)
class PatchCandidate:
    files: Mapping[str, str]


_JSON_FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n(.*?)\r?\n```[ \t]*\Z", re.DOTALL | re.IGNORECASE)


def _unwrap_json_fence(raw: str) -> str:
    """Allow one whole-response JSON fence, but never prose around it."""
    if not isinstance(raw, str):
        return raw
    match = _JSON_FENCE.fullmatch(raw.strip())
    return match.group(1) if match else raw


def _decode_final_json_object(raw: str) -> object:
    """Decode exact JSON, or one final JSON object after a model lead-in.

    The lead-in is ignored only because the decoded object still goes through
    the exact reviewed-path and complete-content checks below. Any trailing
    prose remains a rejection, preventing ambiguous multiple proposals.
    """
    normalized = _unwrap_json_fence(raw)
    try:
        return json.loads(normalized)
    except json.JSONDecodeError as initial_error:
        if not isinstance(normalized, str):
            raise initial_error
        start = normalized.find("{")
        if start < 0:
            raise initial_error
        try:
            payload, end = json.JSONDecoder().raw_decode(normalized, start)
        except json.JSONDecodeError:
            raise initial_error
        if normalized[end:].strip():
            raise initial_error
        return payload


def _decode_exact_labeled_fences(raw: str, plan: TaskPlan) -> object | None:
    """Accept only one Markdown code block per exact reviewed path.

    Some hosted models emit ordinary labeled source blocks despite a structured
    response request. This fallback has no path discovery: every block must be
    labeled with a reviewed path, and every reviewed path must appear once.
    """
    if not isinstance(raw, str):
        return None
    lines = raw.splitlines()
    openings = [line for line in lines if re.fullmatch(r"[ \t]*```(?:python|py)[ \t]*", line, re.IGNORECASE)]
    if len(openings) != len(plan.files):
        return None
    blocks: dict[str, str] = {}
    for index, line in enumerate(lines):
        label = re.sub(r"^#+[ \t]*", "", line.strip()).strip("`* ")
        if label.lower().startswith("file:"):
            label = label[5:].strip().strip("`* ")
        if label not in plan.files or label in blocks:
            continue
        if index + 1 >= len(lines) or not re.fullmatch(r"[ \t]*```(?:python|py)?[ \t]*", lines[index + 1], re.IGNORECASE):
            return None
        closing = index + 2
        while closing < len(lines) and lines[closing].strip() != "```":
            closing += 1
        if closing == len(lines):
            return None
        blocks[label] = "\n".join(lines[index + 2:closing])
    if set(blocks) != set(plan.files):
        return None
    return {"files": [{"path": path, "content": blocks[path]} for path in plan.files]}


def parse_patch_candidate(raw: str, plan: TaskPlan) -> PatchCandidate:
    """Accept structured JSON or strictly labeled code blocks for reviewed paths."""
    try:
        payload = _decode_final_json_object(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        payload = _decode_exact_labeled_fences(raw, plan)
        if payload is None:
            raise PatchProtocolError("candidate is not valid JSON or exact labeled source blocks") from exc
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
    expected = set(snapshot.reviewed_paths)
    if set(candidate.files) != expected:
        raise WorkspacePlanError("candidate does not match snapshotted file scope")
    for relative, content in candidate.files.items():
        target = (snapshot.root / relative).resolve()
        if snapshot.root not in target.parents:
            raise WorkspacePlanError(f"candidate path escapes project root: {relative}")
        if not target.parent.is_dir():
            raise WorkspacePlanError(f"candidate parent does not exist: {relative}")
        target.write_text(content, encoding="utf-8", newline="\n")
