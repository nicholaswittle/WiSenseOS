"""Versioned local API for the future Flutter EngineClient."""

from __future__ import annotations

from threading import Thread

from flask import Flask, jsonify, request

from .contracts import RunMode, TaskRequest
from .service import TaskCoordinator


def create_app(coordinator: TaskCoordinator) -> Flask:
    app = Flask(__name__)

    @app.post("/api/v1/tasks")
    def submit_task():
        data = request.get_json(force=True)
        task_request = TaskRequest(
            request=str(data.get("request", "")).strip(),
            project_root=str(data.get("project_root", "")).strip(),
            mode=RunMode(data.get("mode", RunMode.ASK_BEFORE_CHANGES.value)),
            chat_model=str(data.get("chat_model", "")),
            builder_model=str(data.get("builder_model", "")),
        )
        if not task_request.request or not task_request.project_root:
            return jsonify({"error": "request and project_root are required"}), 400
        record = coordinator.submit(task_request)
        if record.status.value == "blocked":
            return jsonify(record.to_json()), 409
        Thread(target=coordinator.execute, args=(record.task_id,), daemon=True).start()
        return jsonify(record.to_json()), 202

    @app.get("/api/v1/tasks/<task_id>")
    def task_status(task_id: str):
        record = coordinator.store.get(task_id)
        if record is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify({**record.to_json(), "events": [event.to_json() for event in coordinator.store.events(task_id)]})

    return app

