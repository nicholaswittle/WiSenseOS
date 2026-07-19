from __future__ import annotations

from pathlib import Path

from wisense_os.bootstrap import create_default_app
from wisense_os.bridge import HttpWorkCenterBridge


def test_supplied_state_directory_creates_sqlite_state(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")

    assert app is not None
    assert (tmp_path / "state" / "engine_state.db").is_file()


def test_unknown_task_is_a_real_404_from_live_flask_app(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")

    response = app.test_client().get("/api/v1/tasks/not-real")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_construction_never_invokes_bridge(monkeypatch, tmp_path: Path) -> None:
    def bomb(*_args, **_kwargs):
        raise AssertionError("app construction must not invoke the Work Center bridge")

    monkeypatch.setattr(HttpWorkCenterBridge, "run", bomb)

    create_default_app(tmp_path / "state")


def test_live_api_refuses_cloud_builder_for_local_autopilot(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")

    response = app.test_client().post(
        "/api/v1/tasks",
        json={
            "request": "Fix a small test issue",
            "project_root": r"C:\development\projects\wisense-os",
            "mode": "local_autopilot",
            "chat_model": "glm-5.2:cloud",
            "builder_model": "gemma4:31b-cloud",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["status"] == "blocked"
    assert "no qualified local builder" in response.get_json()["reason"]
