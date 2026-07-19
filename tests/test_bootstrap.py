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


def test_ask_before_changes_waits_for_api_approval_before_execution(monkeypatch, tmp_path: Path) -> None:
    def no_network(*_args, **_kwargs):
        raise RuntimeError("test bridge must not contact Local Agent Work Center")

    monkeypatch.setattr(HttpWorkCenterBridge, "run", no_network)
    app = create_default_app(tmp_path / "state")
    client = app.test_client()
    root = tmp_path / "project"
    root.mkdir()
    payload = {
        "request": "Fix a test", "project_root": str(root),
        "mode": "ask_before_changes", "chat_model": "glm-5.2:cloud",
        "builder_model": "gemma4:31b-cloud",
    }

    waiting = client.post("/api/v1/tasks", json=payload)
    task_id = waiting.get_json()["task_id"]
    approved = client.post(f"/api/v1/tasks/{task_id}/approve")

    assert waiting.status_code == 202
    assert waiting.get_json()["status"] == "waiting_for_approval"
    assert approved.status_code == 202
    assert approved.get_json()["status"] == "accepted"


def test_waiting_task_can_persist_an_evidence_backed_plan_before_handoff(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    client = app.test_client()
    api_file = tmp_path / "project" / "wisense_os" / "api.py"
    api_file.parent.mkdir(parents=True)
    api_file.write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    fixture = tmp_path / "project" / "tests" / "test_bootstrap.py"
    fixture.parent.mkdir()
    fixture.write_text("def test_api(test_client): pass\n", encoding="utf-8")
    created = client.post("/api/v1/tasks", json={
        "request": "Add a GET /api/v1/version endpoint that returns JSON.",
        "project_root": str(tmp_path / "project"),
        "mode": "ask_before_changes",
        "chat_model": "glm-5.2:cloud",
        "builder_model": "gemma4:31b-cloud",
    }).get_json()

    response = client.post(f"/api/v1/tasks/{created['task_id']}/plan-draft")
    saved = client.get(f"/api/v1/tasks/{created['task_id']}").get_json()

    assert response.status_code == 200
    assert response.get_json()["plan"]["files"] == ["wisense_os/api.py", "tests/test_bootstrap.py"]
    assert saved["plan"] == response.get_json()["plan"]


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
