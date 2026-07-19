"""Advisory model routing — recommend only from configured available profiles.

Never invent model names. Cost is not estimated here (budget ledger owns spend).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .model_policy import ModelProfile


@dataclass(frozen=True)
class RouteRecommendation:
    chat_model: str
    builder_model: str
    complexity: str
    reason: str
    estimated_cost: float

    def to_json(self) -> dict:
        return {
            "chat_model": self.chat_model,
            "builder_model": self.builder_model,
            "complexity": self.complexity,
            "reason": self.reason,
            "estimated_cost": self.estimated_cost,
        }


def assess_task_complexity(request: str) -> str:
    """Assess request complexity based on length, architectural keywords, and scope."""
    low_keywords = {"format", "fix typo", "comment", "lint", "rename", "clean"}
    high_keywords = {"refactor", "architect", "rewrite", "migrate", "design", "security audit"}

    req_lower = request.lower()
    words = req_lower.split()

    if any(kw in req_lower for kw in high_keywords) or len(words) > 50:
        return "high"
    if any(kw in req_lower for kw in low_keywords) and len(words) < 20:
        return "low"
    return "medium"


def recommend_route(
    request: str,
    available_profiles: Sequence[ModelProfile],
) -> RouteRecommendation:
    """Recommend chat/builder pairing strictly from available configured profiles."""
    complexity = assess_task_complexity(request)
    profiles = [p for p in available_profiles if p.available]

    local_chat = next(
        (p for p in profiles if not p.is_cloud and "chat" in p.roles), None,
    )
    local_builder = next(
        (p for p in profiles if not p.is_cloud and "builder" in p.roles), None,
    )
    cloud_chat = next(
        (p for p in profiles if p.is_cloud and "chat" in p.roles), None,
    )
    cloud_builder = next(
        (p for p in profiles if p.is_cloud and "builder" in p.roles), None,
    )

    chat = local_chat or cloud_chat
    if complexity == "high" and cloud_builder is not None:
        builder = cloud_builder
        reason = (
            "High-complexity task — recommended cloud builder with Ask Before Changes "
            "(supervised testing). Cost is tracked by the budget ledger, not invented here."
        )
    elif local_builder is not None:
        builder = local_builder
        reason = "Local builder available — preferred for zero cloud spend."
    elif cloud_builder is not None:
        builder = cloud_builder
        reason = (
            "No local builder configured — cloud builder recommended for Ask Before Changes "
            "(supervised testing). Cost is tracked by the budget ledger, not invented here."
        )
    else:
        builder = None
        reason = "No available builder profile is configured."

    return RouteRecommendation(
        chat_model=chat.name if chat else "",
        builder_model=builder.name if builder else "",
        complexity=complexity,
        reason=reason,
        estimated_cost=0.0,
    )
