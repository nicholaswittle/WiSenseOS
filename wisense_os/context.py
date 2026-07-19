"""Persistent Project Context & Memory Engine for WiSense OS AIOS."""

from __future__ import annotations

from pathlib import Path


def build_project_context_string(project_root: Path) -> str:
    """Scan project structure and build memory context string in-memory without writing to disk."""
    if not project_root.is_dir():
        return ""
    subdirs = [p.name for p in project_root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    files = [p.name for p in project_root.iterdir() if p.is_file()]

    tech_stack = []
    if (project_root / "pubspec.yaml").exists():
        tech_stack.append("Flutter / Dart")
    if (project_root / "pyproject.toml").exists() or (project_root / "setup.py").exists() or any(f.endswith(".py") for f in files):
        tech_stack.append("Python")
    if (project_root / "package.json").exists():
        tech_stack.append("Node.js / JavaScript")

    tech_str = ", ".join(tech_stack) if tech_stack else "General / Polyglot"

    return f"""# Project Topology & Memory Context

**Project Name**: {project_root.name}
**Root Path**: {project_root.resolve()}
**Tech Stack**: {tech_str}

## Directory Map
- Subdirectories: {", ".join(sorted(subdirs)) if subdirs else "None"}
- Root Files: {", ".join(sorted(files[:15]))}

## AIOS Operating Guidelines (Andrej Karpathy 4 Core Principles)
1. **Think Before Coding**: State all assumptions explicitly. If requirements are ambiguous, ask for clarification instead of guessing.
2. **Simplicity First**: Implement the simplest possible solution. Avoid speculative abstractions, unused features, or unnecessary wrapper code.
3. **Surgical Changes**: Restrict modifications strictly to requested files. Never refactor, reformat, or "clean up" unrelated code outside the requested scope.
4. **Goal-Driven Execution**: Define explicit, test-verifiable acceptance criteria before writing code. Verify that unit tests pass before committing.
"""


def generate_project_context(project_root: Path) -> str:
    """Build memory context without writing to disk by default."""
    return build_project_context_string(project_root)


def write_project_context_file(project_root: Path) -> Path:
    """Write .wisense/CONTEXT.md to disk only on explicit approval."""
    wisense_dir = project_root / ".wisense"
    wisense_dir.mkdir(parents=True, exist_ok=True)
    context_file = wisense_dir / "CONTEXT.md"
    content = build_project_context_string(project_root)
    context_file.write_text(content, encoding="utf-8")
    return context_file


def read_project_context(project_root: Path) -> str:
    """Read project memory context if present on disk, otherwise build in-memory."""
    context_file = project_root / ".wisense" / "CONTEXT.md"
    if context_file.exists():
        try:
            return context_file.read_text(encoding="utf-8")
        except Exception:
            pass
    return build_project_context_string(project_root)
