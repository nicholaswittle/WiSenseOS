"""Construct the WiSense OS engine API without starting a server or model call."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from .api import create_app
from .bridge import HttpWorkCenterBridge
from .model_policy import ModelRegistry
from .service import TaskCoordinator
from .store import TaskStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _default_state_dir() -> Path:
    """Return the per-user state location without creating it yet."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return base / "WiSenseOS"


def create_default_app(state_dir: Path | None = None) -> Flask:
    """Build the local API using durable state, without touching a model.

    The bridge only describes how a later task reaches Local Agent Work Center;
    it performs no HTTP work until the coordinator executes an accepted task.
    """
    resolved_state_dir = state_dir or _default_state_dir()
    models = ModelRegistry.from_file(PROJECT_ROOT / "config" / "model_profiles.json")
    coordinator = TaskCoordinator(
        store=TaskStore(resolved_state_dir / "engine_state.db"),
        models=models,
        bridge=HttpWorkCenterBridge(),
    )
    return create_app(coordinator)
