from __future__ import annotations

from pathlib import Path

from wisense_os.bootstrap import create_default_app


def test_delete_refuses_active_tasks(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "engine")
    client = app.test_client()
    submit = client.post(
        "/api/v1/tasks",
        json={
            "request": "fix billing.py",
            "project_root": str(tmp_path),
            "mode": "ask_before_changes",
            "builder_model": "gemma4:31b-cloud",
            "chat_model": "glm-5.2:cloud",
        },
    )
    assert submit.status_code in {200, 202}
    task_id = submit.get_json()["task_id"]

    refused = client.delete(f"/api/v1/tasks/{task_id}")
    assert refused.status_code == 409
    assert "active state" in refused.get_json()["error"]


def test_delete_allows_canceled_tasks(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "engine")
    client = app.test_client()
    submit = client.post(
        "/api/v1/tasks",
        json={
            "request": "fix billing.py",
            "project_root": str(tmp_path),
            "mode": "ask_before_changes",
            "builder_model": "gemma4:31b-cloud",
            "chat_model": "glm-5.2:cloud",
        },
    )
    task_id = submit.get_json()["task_id"]
    assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 200

    deleted = client.delete(f"/api/v1/tasks/{task_id}")
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True
    assert client.get(f"/api/v1/tasks/{task_id}").status_code == 404
