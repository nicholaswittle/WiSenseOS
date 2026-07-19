"""Onboard diagnostics + light SSE task stream."""

from __future__ import annotations

from pathlib import Path

from wisense_os.bootstrap import create_default_app


def test_diagnostics_reports_truthful_onboard_snapshot(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    response = app.test_client().get("/api/v1/diagnostics")
    assert response.status_code == 200
    body = response.get_json()
    assert body["engine"]["status"] == "ready"
    assert "ollama_reachable" in body
    assert "git_available" in body
    assert "cloud_assisted_only" in body
    assert isinstance(body["notes"], list)
    assert body["recommended_daily_mode"] == "ask_before_changes"


def test_plan_draft_422_includes_hint_and_candidates(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    client = app.test_client()
    root = tmp_path / "project"
    root.mkdir()
    (root / "billing.py").write_text("def totals(items):\n    return 0\n", encoding="utf-8")
    (root / "invoicing.py").write_text("def totals(items):\n    return 1\n", encoding="utf-8")
    created = client.post("/api/v1/tasks", json={
        "request": "fix totals",
        "project_root": str(root),
        "mode": "ask_before_changes",
        "chat_model": "glm-5.2:cloud",
        "builder_model": "gemma4:31b-cloud",
    }).get_json()

    response = client.post(f"/api/v1/tasks/{created['task_id']}/plan-draft")
    assert response.status_code == 422
    body = response.get_json()
    assert body["ok"] is False
    assert "reason" in body
    assert "hint" in body
    assert isinstance(body.get("candidates"), list)


def test_task_stream_emits_sse_for_known_task(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    client = app.test_client()
    root = tmp_path / "project"
    root.mkdir()
    created = client.post("/api/v1/tasks", json={
        "request": "Talk about billing",
        "project_root": str(root),
        "mode": "talk_only",
        "chat_model": "glm-5.2:cloud",
        "builder_model": "gemma4:31b-cloud",
    }).get_json()
    task_id = created["task_id"]

    response = client.get(f"/api/v1/tasks/{task_id}/stream")
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    # First chunk should be an SSE event with task payload
    chunk = next(response.response)
    text = chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else str(chunk)
    assert "event: task" in text
    assert task_id in text


def test_task_stream_404_for_unknown_task(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    response = app.test_client().get("/api/v1/tasks/missing-task/stream")
    assert response.status_code == 404
