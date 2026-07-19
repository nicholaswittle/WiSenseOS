"""Construct the WiSense OS engine API without starting a server or model call."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import Flask

from .api import create_app
from .model_adapter import OllamaChatAdapter
from .model_policy import ModelRegistry
from .patch_executor import PlanBoundPatchExecutor, PytestRunner
from .service import TaskCoordinator
from .store import TaskStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _default_state_dir() -> Path:
    """Return the per-user state location without creating it yet."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return base / "WiSenseOS"


def issue_launch_token(state_dir: Path) -> str:
    """Generate a per-launch loopback token and persist it under the
    per-user state directory for the desktop client to read.

    The %LOCALAPPDATA% location is already per-user by Windows default
    ACLs, which is the intended protection boundary (other local
    accounts / accidental callers), not protection from malware running
    as the same user. DPAPI-at-rest hardening is a documented follow-up.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    (state_dir / "engine_token").write_text(token, encoding="utf-8")
    return token


def create_default_app(
    state_dir: Path | None = None,
    *,
    model_adapter: OllamaChatAdapter | None = None,
    runtime_model_names: set[str] | None = None,
    auth_token: str | None = None,
) -> Flask:
    """Build the local API using durable state, without touching a model.

    The native executor performs no provider or filesystem work at startup.
    auth_token is None for in-process tests (open) and set by the launcher
    (enforced loopback token) for real runs.
    """
    resolved_state_dir = state_dir or _default_state_dir()
    models = ModelRegistry.from_file(PROJECT_ROOT / "config" / "model_profiles.json")
    if runtime_model_names is not None:
        models = models.with_runtime_availability(runtime_model_names)
    store = TaskStore(resolved_state_dir / "engine_state.db")
    store.mark_interrupted_runs()
    coordinator = TaskCoordinator(
        store=store,
        models=models,
        executor=PlanBoundPatchExecutor(
            model_adapter or OllamaChatAdapter(), PytestRunner(), commit_on_success=True),
    )
    return create_app(coordinator, auth_token=auth_token)
