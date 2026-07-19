"""Versioned local API for the future Flutter EngineClient."""

from __future__ import annotations

from threading import Thread
from pathlib import Path

from flask import Flask, jsonify, request

from .contracts import RunMode, TaskRequest, TaskStatus
from .plan import draft_evidence_plan
from .service import TaskCoordinator


def create_app(coordinator: TaskCoordinator) -> Flask:
    app = Flask(__name__)

    @app.get("/api/v1/health")
    def health():
        return jsonify({"engine": "wisense-os", "version": "0.1.0", "status": "ready"})

    @app.get("/api/v1/models")
    def models():
        return jsonify({"models": [profile.to_json() for profile in coordinator.models.profiles()]})

    @app.get("/api/v1/projects")
    def projects():
        return jsonify({"projects": [project.to_json() for project in coordinator.store.list_projects()]})

    @app.post("/api/v1/projects")
    def register_project():
        data = request.get_json(force=True)
        try:
            project = coordinator.store.register_project(
                display_name=str(data.get("display_name", "")),
                root=str(data.get("root", "")),
                local_autopilot_trusted=data.get("local_autopilot_trusted") is True,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(project.to_json()), 201

    @app.get("/api/v1/tasks")
    def task_history():
        raw_limit = request.args.get("limit", "50")
        try:
            limit = int(raw_limit)
            records = coordinator.store.list_tasks(limit)
        except ValueError:
            return jsonify({"error": "limit must be an integer from 1 to 200"}), 400
        return jsonify({"tasks": [record.to_json() for record in records]})

    @app.post("/api/v1/tasks")
    def submit_task():
        data = request.get_json(force=True)
        try:
            task_request = TaskRequest(
                request=str(data.get("request", "")).strip(),
                project_root=str(data.get("project_root", "")).strip(),
                mode=RunMode(data.get("mode", RunMode.ASK_BEFORE_CHANGES.value)),
                chat_model=str(data.get("chat_model", "")),
                builder_model=str(data.get("builder_model", "")),
            )
        except ValueError:
            return jsonify({"error": "unknown run mode"}), 400
        if not task_request.request or not task_request.project_root:
            return jsonify({"error": "request and project_root are required"}), 400
        record = coordinator.submit(task_request)
        if record.status.value == "blocked":
            return jsonify(record.to_json()), 409
        if record.status.value == "accepted":
            Thread(target=coordinator.execute, args=(record.task_id,), daemon=True).start()
        return jsonify(record.to_json()), 202

    @app.post("/api/v1/tasks/<task_id>/approve")
    def approve_task(task_id: str):
        try:
            record = coordinator.approve(task_id)
        except KeyError:
            return jsonify({"error": "task not found"}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        Thread(target=coordinator.execute, args=(record.task_id,), daemon=True).start()
        return jsonify(record.to_json()), 202

    @app.post("/api/v1/tasks/<task_id>/provider-input")
    def provider_input(task_id: str):
        data = request.get_json(force=True)
        message = str(data.get("message", ""))
        try:
            record = coordinator.store.get(task_id)
            if record is None:
                raise KeyError(task_id)
            if record.status != TaskStatus.WAITING_FOR_PROVIDER_INPUT:
                raise ValueError(f"task is not awaiting provider input: {record.status.value}")
            if not message.strip():
                raise ValueError("provider input is required")
        except KeyError:
            return jsonify({"error": "task not found"}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        Thread(target=coordinator.continue_with_provider_input, args=(task_id, message), daemon=True).start()
        return jsonify({**record.to_json(), "status": TaskStatus.RUNNING.value}), 202

    @app.post("/api/v1/tasks/<task_id>/plan-draft")
    def draft_task_plan(task_id: str):
        record = coordinator.store.get(task_id)
        if record is None:
            return jsonify({"error": "task not found"}), 404
        if record.status != TaskStatus.WAITING_FOR_APPROVAL:
            return jsonify({"error": "plan drafting is available only before Engine handoff"}), 409
        result = draft_evidence_plan(record.request.request, Path(record.request.project_root))
        if not result.ok or result.plan is None:
            return jsonify({"ok": False, "reason": result.reason}), 422
        coordinator.store.save_plan(task_id, result.plan)
        return jsonify({"ok": True, "task_id": task_id, "plan": result.plan.to_json()})

    @app.get("/api/v1/tasks/<task_id>")
    def task_status(task_id: str):
        record = coordinator.store.get(task_id)
        if record is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify({
            **record.to_json(),
            "events": [event.to_json() for event in coordinator.store.events(task_id)],
            "plan": coordinator.store.plan(task_id),
        })

    return app
