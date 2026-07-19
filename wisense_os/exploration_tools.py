"""Bounded read-only project tools for agentic explore (no writes)."""

from __future__ import annotations

from pathlib import Path
import re

from .file_finder import is_safe_project_relative_file

DEFAULT_MAX_READ_BYTES = 262144
DEFAULT_MAX_MATCHES = 50
DEFAULT_MAX_GLOB_MATCHES = 200


def _normalize(rel_path: str) -> str:
    return rel_path.replace("\\", "/")


def _pattern_is_safe(pattern: str) -> bool:
    return not Path(pattern).is_absolute() and ".." not in Path(pattern).parts


_SECRET_PATTERNS = re.compile(
    r"(sk-[a-zA-Z0-9]{32,}|AIzaSy[a-zA-Z0-9_-]{33}|ghp_[a-zA-Z0-9]{36}|bearer\s+[a-zA-Z0-9._-]+)",
    re.IGNORECASE,
)


def read_file(
    project_root: Path,
    path: str,
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
) -> dict:
    if not is_safe_project_relative_file(project_root, path):
        return {"error": "unsafe_path"}
    file_path = project_root / path
    if not file_path.is_file():
        return {"error": "not_found"}
    try:
        with open(file_path, "rb") as handle:
            data = handle.read(max_bytes + 1)
        original_size = file_path.stat().st_size
    except OSError:
        return {"error": "read_error"}
    truncated = len(data) > max_bytes
    content = data[:max_bytes].decode("utf-8", errors="replace")
    content = _SECRET_PATTERNS.sub("[REDACTED_SECRET]", content)
    return {
        "path": _normalize(path),
        "content": content,
        "bytes": original_size,
        "truncated": truncated,
    }


def glob_files(
    project_root: Path,
    pattern: str,
    max_matches: int = DEFAULT_MAX_GLOB_MATCHES,
) -> dict:
    if not _pattern_is_safe(pattern):
        return {"error": "unsafe_pattern"}
    matches: list[str] = []
    truncated = False
    for candidate in sorted(project_root.glob(pattern)):
        if len(matches) >= max_matches:
            truncated = True
            break
        try:
            rel_path = str(candidate.relative_to(project_root))
        except ValueError:
            continue
        if candidate.is_file() and is_safe_project_relative_file(project_root, rel_path):
            matches.append(_normalize(rel_path))
    return {"matches": matches[:max_matches], "truncated": truncated}


def grep_files(
    project_root: Path,
    pattern: str,
    path_glob: str = "**/*",
    max_matches: int = DEFAULT_MAX_MATCHES,
) -> dict:
    try:
        regex = re.compile(pattern)
    except re.error:
        return {"error": "invalid_regex"}

    files_result = glob_files(project_root, path_glob, max_matches=10_000)
    if "error" in files_result:
        return files_result

    matches: list[dict] = []
    truncated = False
    for rel_path in files_result["matches"]:
        if len(matches) >= max_matches:
            truncated = True
            break
        file_path = project_root / rel_path
        try:
            with open(file_path, encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle, 1):
                    if regex.search(line):
                        matches.append({
                            "file": rel_path,
                            "line": line_number,
                            "text": line.rstrip("\n\r"),
                        })
                        if len(matches) >= max_matches:
                            truncated = True
                            break
        except OSError:
            continue
    return {"matches": matches, "truncated": truncated}


TOOL_SCHEMAS = (
    {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": "List project-relative files matching a glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_files",
            "description": "Search file contents with a regex.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path_glob": {"type": "string"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read one project-relative file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
)


def dispatch_tool_call(project_root: Path, name: str, args: dict | str) -> dict:
    if isinstance(args, str):
        import json
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    if not isinstance(args, dict):
        args = {}
    if name == "glob_files":
        return glob_files(project_root, str(args.get("pattern", "")))
    if name == "grep_files":
        return grep_files(
            project_root,
            str(args.get("pattern", "")),
            path_glob=str(args.get("path_glob", "**/*")),
        )
    if name == "read_file":
        return read_file(project_root, str(args.get("path", "")))
    return {"error": f"unknown_tool:{name}"}
