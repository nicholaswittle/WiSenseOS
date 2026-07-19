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
    """Recommend the optimal chat and builder model pairing based on complexity and local availability."""
    complexity = assess_task_complexity(request)

    local_chat = next((p for p in available_profiles if p.available and p.provider != ProviderKind.CLOUD and "chat" in p.roles), None)
    local_builder = next((p for p in available_profiles if p.available and p.provider != ProviderKind.CLOUD and "builder" in p.roles), None)
    cloud_builder = next((p for p in available_profiles if p.provider == ProviderKind.CLOUD and "builder" in p.roles), None)

    default_chat = local_chat.name if local_chat else "qwen2.5-coder:7b"
    default_local_builder = local_builder.name if local_builder else "qwen2.5-coder:7b"
    default_cloud_builder = cloud_builder.name if cloud_builder else "gemma4:31b-cloud"

    if complexity == "high" and cloud_builder:
        return RouteRecommendation(
            chat_model=default_chat,
            builder_model=default_cloud_builder,
            complexity=complexity,
            reason="Task requires high architectural reasoning. Cloud builder recommended (supervised testing).",
            estimated_cost=0.15,
        )

    return RouteRecommendation(
        chat_model=default_chat,
        builder_model=default_local_builder,
        complexity=complexity,
        reason="Task is suitable for local execution without external API usage.",
        estimated_cost=0.00,
    )
