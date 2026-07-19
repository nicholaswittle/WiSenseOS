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


def test_live_api_exposes_truthful_health_and_model_profiles(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    client = app.test_client()

    assert client.get("/api/v1/health").get_json() == {
        "engine": "wisense-os", "status": "ready", "version": "0.1.0"
    }
    models = client.get("/api/v1/models").get_json()["models"]
    assert models == [
        {
            "available": True,
            "future_local_target": True,
            "name": "gemma4:31b-cloud",
            "provider": "cloud",
            "roles": ["builder"],
            "supervised_testing_only": True,
        },
        {
            "available": True,
            "future_local_target": False,
            "name": "glm-5.2:cloud",
            "provider": "cloud",
            "roles": ["chat", "planner", "builder"],
            "supervised_testing_only": True,
        },
    ]


def test_unknown_mode_is_rejected_before_task_creation(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")

    response = app.test_client().post("/api/v1/tasks", json={"mode": "anything_goes"})

    assert response.status_code == 400
    assert response.get_json() == {"error": "unknown run mode"}


def test_task_history_is_durable_and_newest_first(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    client = app.test_client()
    payload = {
        "request": "Fix a test", "project_root": r"C:\demo",
        "mode": "local_autopilot", "chat_model": "glm-5.2:cloud",
        "builder_model": "gemma4:31b-cloud",
    }
    first = client.post("/api/v1/tasks", json=payload).get_json()
    second = client.post("/api/v1/tasks", json=payload).get_json()

    response = client.get("/api/v1/tasks?limit=2")

    assert response.status_code == 200
    assert [task["task_id"] for task in response.get_json()["tasks"]] == [
        second["task_id"], first["task_id"],
    ]


def test_task_history_rejects_invalid_limit(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")

    response = app.test_client().get("/api/v1/tasks?limit=0")

    assert response.status_code == 400
    assert response.get_json() == {"error": "limit must be an integer from 1 to 200"}


def test_project_registry_is_durable_and_deduplicates_root(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    client = app.test_client()
    root = tmp_path / "demo_project"
    root.mkdir()
    payload = {"display_name": "Demo", "root": str(root), "local_autopilot_trusted": False}

    first = client.post("/api/v1/projects", json=payload)
    second = client.post("/api/v1/projects", json=payload)
    listed = client.get("/api/v1/projects")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["project_id"] == second.get_json()["project_id"]
    assert listed.get_json()["projects"] == [first.get_json()]


def test_project_registry_rejects_missing_folder(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")

    response = app.test_client().post(
        "/api/v1/projects", json={"display_name": "Missing", "root": str(tmp_path / "missing")}
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "root must be an existing directory"}


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
