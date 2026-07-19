from __future__ import annotations

from pathlib import Path

from wisense_os.bootstrap import create_default_app


def test_intent_endpoint_uses_floor_without_chat_model(tmp_path: Path) -> None:
    (tmp_path / "billing.py").write_text("def totals():\n    return 0\n", encoding="utf-8")
    app = create_default_app(tmp_path / "engine")
    client = app.test_client()
    response = client.post(
        "/api/v1/intent",
        json={
            "request": "the tests are broken in billing.py",
            "project_root": str(tmp_path),
        },
    )
    assert response.status_code == 200
    intent = response.get_json()["intent"]
    assert intent["kind"] == "edit"
    assert intent["target_file"] == "billing.py"
    assert intent["source"] == "floor"


def test_qualification_run_marks_cloud_not_applicable(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "engine")
    client = app.test_client()
    models = client.get("/api/v1/models").get_json()["models"]
    cloud = next((m for m in models if m.get("provider") == "cloud"), None)
    assert cloud is not None
    response = client.post(
        "/api/v1/qualification/run",
        json={"model": cloud["name"]},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "not_applicable"
    assert body["score"] is None


def test_submit_records_intent_classified_event(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    app = create_default_app(tmp_path / "engine")
    client = app.test_client()
    submit = client.post(
        "/api/v1/tasks",
        json={
            "request": "fix the bug in app.py",
            "project_root": str(tmp_path),
            "mode": "ask_before_changes",
            "builder_model": "gemma4:31b-cloud",
            "chat_model": "glm-5.2:cloud",
        },
    )
    assert submit.status_code in (200, 202)
    task_id = submit.get_json()["task_id"]
    detail = client.get(f"/api/v1/tasks/{task_id}").get_json()
    kinds = [event["kind"] for event in detail["events"]]
    assert "intent_classified" in kinds
    intent_event = next(e for e in detail["events"] if e["kind"] == "intent_classified")
    assert "edit" in intent_event["detail"]
