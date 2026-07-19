"""Multi-Model Multiplexer & Router for WiSense OS AIOS."""

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


from .contracts import ProviderKind


def recommend_route(
    request: str,
    available_profiles: Sequence[ModelProfile],
) -> RouteRecommendation:
    """Recommend optimal chat and builder model pairing strictly from available profiles."""
    complexity = assess_task_complexity(request)

    local_chat = next((p for p in available_profiles if p.available and p.provider != ProviderKind.CLOUD and "chat" in p.roles), None)
    local_builder = next((p for p in available_profiles if p.available and p.provider != ProviderKind.CLOUD and "builder" in p.roles), None)
    cloud_chat = next((p for p in available_profiles if p.provider == ProviderKind.CLOUD and "chat" in p.roles), None)
    cloud_builder = next((p for p in available_profiles if p.provider == ProviderKind.CLOUD and "builder" in p.roles), None)

    chat_model = local_chat.name if local_chat else (cloud_chat.name if cloud_chat else "gemma4:31b-cloud")
    builder_model = (
        cloud_builder.name if (complexity == "high" and cloud_builder) or not local_builder
        else local_builder.name
    )

    if builder_model == (cloud_builder.name if cloud_builder else "gemma4:31b-cloud"):
        return RouteRecommendation(
            chat_model=chat_model,
            builder_model=builder_model,
            complexity=complexity,
            reason="Cloud Ask Before Changes route selected (supervised testing).",
            estimated_cost=0.05 if complexity != "high" else 0.15,
        )

    return RouteRecommendation(
        chat_model=chat_model,
        builder_model=builder_model,
        complexity=complexity,
        reason="Task is suitable for local model execution at zero cloud cost.",
        estimated_cost=0.00,
    )
