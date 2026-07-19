"""SOP & Skill Workflow Engine for WiSense OS AIOS."""

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
        description="Comprehensive analysis of project codebase for security risks, unhandled exceptions, and dead code.",
        default_request="Perform a security and quality audit across all source files, report issues, and add missing error handlers.",
        recommended_mode="ask_before_changes",
    ),
    SOPWorkflow(
        id="unit_test_expansion",
        name="Unit Test Suite Boost",
        category="Testing",
        description="Scans project modules and adds complete unit test coverage for untested classes and functions.",
        default_request="Scan project source files and generate comprehensive unit tests to achieve high test coverage.",
        recommended_mode="ask_before_changes",
    ),
    SOPWorkflow(
        id="refactor_module",
        name="Module Optimization & Cleanup",
        category="Refactoring",
        description="Refactors oversized functions, cleans up pathing, and standardizes type annotations.",
        default_request="Refactor module structure, clean up oversized functions, and enforce strict type annotations.",
        recommended_mode="ask_before_changes",
    ),
    SOPWorkflow(
        id="doc_generation",
        name="API Documentation Generator",
        category="Documentation",
        description="Generates clear, production-ready docstrings and updates technical documentation.",
        default_request="Generate standard docstrings for all exported functions and update README.md.",
        recommended_mode="local_autopilot",
    ),
]


def list_builtin_sops() -> List[SOPWorkflow]:
    return BUILTIN_SOPS


def get_sop_by_id(sop_id: str) -> SOPWorkflow | None:
    return next((sop for sop in BUILTIN_SOPS if sop.id == sop_id), None)
