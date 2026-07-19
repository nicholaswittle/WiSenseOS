"""Prompt-template SOPs for Companion — not an orchestration engine.

Selecting an SOP only fills the request box and suggests a mode. It does not
bypass Ask Before Changes, digests, budget, or Autopilot policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SOPWorkflow:
    id: str
    name: str
    category: str
    description: str
    default_request: str
    recommended_mode: str

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "default_request": self.default_request,
            "recommended_mode": self.recommended_mode,
        }


BUILTIN_SOPS: List[SOPWorkflow] = [
    SOPWorkflow(
        id="code_audit",
        name="Security & Quality Audit",
        category="Audit",
        description="Prompt template for a read-focused audit request (Talk Only or Ask Before Changes).",
        default_request="Perform a security and quality audit across all source files, report issues, and add missing error handlers.",
        recommended_mode="ask_before_changes",
    ),
    SOPWorkflow(
        id="unit_test_expansion",
        name="Unit Test Suite Boost",
        category="Testing",
        description="Prompt template for expanding unit tests under Ask Before Changes.",
        default_request="Scan project source files and generate comprehensive unit tests to achieve high test coverage.",
        recommended_mode="ask_before_changes",
    ),
    SOPWorkflow(
        id="refactor_module",
        name="Module Optimization & Cleanup",
        category="Refactoring",
        description="Prompt template for a bounded refactor under Ask Before Changes.",
        default_request="Refactor module structure, clean up oversized functions, and enforce strict type annotations.",
        recommended_mode="ask_before_changes",
    ),
    SOPWorkflow(
        id="doc_generation",
        name="API Documentation Generator",
        category="Documentation",
        description="Prompt template for docstring/README updates. Uses Ask Before Changes (not Autopilot) until a local builder exists.",
        default_request="Generate standard docstrings for all exported functions and update README.md.",
        recommended_mode="ask_before_changes",
    ),
    SOPWorkflow(
        id="karpathy_refactor",
        name="Karpathy Surgical Refactor",
        category="Principles",
        description="Prompt template encouraging surgical diffs and test verification — does not enforce rules by itself.",
        default_request="Perform a surgical refactor: state assumptions first, use simplest code, limit diffs to the target file, and verify tests pass.",
        recommended_mode="ask_before_changes",
    ),
]


def list_builtin_sops() -> List[SOPWorkflow]:
    return BUILTIN_SOPS


def get_sop_by_id(sop_id: str) -> SOPWorkflow | None:
    return next((sop for sop in BUILTIN_SOPS if sop.id == sop_id), None)
