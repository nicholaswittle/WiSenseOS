"""Truthful model availability and run-mode policy.

Profiles are data, not guesses from a model name.  A cloud profile can be
available for supervised testing without being represented as local.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from .contracts import ModelProfile, ProviderKind, RunMode, TaskRequest


class ModelPolicyError(ValueError):
    pass


class ModelRegistry:
    def __init__(self, profiles: dict[str, ModelProfile]) -> None:
        self._profiles = profiles

    @classmethod
    def from_file(cls, path: Path) -> "ModelRegistry":
        rows = json.loads(path.read_text(encoding="utf-8"))
        profiles = {
            row["name"]: ModelProfile(
                name=row["name"],
                provider=ProviderKind(row["provider"]),
                roles=tuple(row["roles"]),
                available=bool(row["available"]),
                supervised_testing_only=bool(row["supervised_testing_only"]),
                future_local_target=bool(row.get("future_local_target", False)),
            )
            for row in rows
        }
        return cls(profiles)

    def get(self, name: str) -> ModelProfile:
        try:
            return self._profiles[name]
        except KeyError as exc:
            raise ModelPolicyError(f"model is not configured: {name}") from exc

    def profiles(self) -> tuple[ModelProfile, ...]:
        return tuple(self._profiles[name] for name in sorted(self._profiles))

    def with_runtime_availability(self, runtime_models: set[str]) -> "ModelRegistry":
        """Return configured profiles filtered by the names Ollama can currently see."""
        return ModelRegistry({
            name: replace(profile, available=profile.available and name in runtime_models)
            for name, profile in self._profiles.items()
        })

    def validate(self, request: TaskRequest) -> None:
        chat = self.get(request.chat_model)
        builder = self.get(request.builder_model)
        for profile, role in ((chat, "chat"), (builder, "builder")):
            if not profile.available:
                raise ModelPolicyError(f"model is unavailable: {profile.name}")
            if role not in profile.roles:
                raise ModelPolicyError(f"model cannot serve {role}: {profile.name}")

        if request.mode is RunMode.LOCAL_AUTOPILOT:
            if builder.provider is not ProviderKind.LOCAL:
                raise ModelPolicyError(
                    "local_autopilot is unavailable: no qualified local builder is configured"
                )
        if request.mode is RunMode.TALK_ONLY and builder.provider is ProviderKind.CLOUD:
            # A builder is not used in this mode; allow the configured profile but
            # make no provider call through the coordinator.
            return
