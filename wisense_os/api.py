"""Versioned local API for the future Flutter EngineClient."""

from __future__ import annotations

import hmac
from threading import Thread
from pathlib import Path

from flask import Flask, jsonify, request

from .agentic_explore import is_cloud_model, locate_target_with_exploration
from .context import generate_project_context, read_project_context
from .contracts import RunMode, TaskRequest, TaskStatus
from .explore import explore_project
from .intent import classify_intent
from .model_policy import ModelPolicyError
from .plan import draft_edit_plan, draft_evidence_plan
from .project_resolution import resolve_project_reference
from .qualification import build_native_edit_runner, run_offline_edit_corpus
from .router import recommend_route
from .service import TaskCoordinator
from .skills import list_builtin_sops


def create_app(coordinator: TaskCoordinator, *, auth_token: str | None = None) -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _require_loopback_token():
        # Loopback token gate. Enforced only when a token was issued (the
        # real launcher always issues one; in-process tests construct the
        # app without a token and stay open). This protects against other
        # local accounts and accidental callers, not malware running as
        # the same user. Health is exempt so a client can probe readiness
        # before it has read the token file.
        if auth_token is None:
            return None
        if request.path == "/api/v1/health":
            return None
        presented = request.headers.get("X-WiSense-Token", "")
        header = request.headers.get("Authorization", "")
        if not presented and header.startswith("Bearer "):
            presented = header[len("Bearer "):]
        if not presented or not hmac.compare_digest(presented, auth_token):
            return jsonify({"error": "unauthorized"}), 401
        return None

    @app.get("/api/v1/health")
    def health():
        return jsonify({"engine": "wisense-os", "version": "0.1.0", "status": "ready"})

    @app.get("/api/v1/telemetry")
    def telemetry():
        # Honest compute counters. Qualification comes only from stored evidence.
        active_local = 0
        active_cloud = 0
        for task in coordinator.store.list_tasks(limit=50):
            if task.status != TaskStatus.RUNNING:
                continue
            try:
                builder = coordinator.models.get(task.request.builder_model)
            except ModelPolicyError:
                continue
            if builder.provider.value == "cloud":
                active_cloud += 1
            else:
                active_local += 1
        qualification = []
        if coordinator.qualification is not None:
            qualification = [
                {
                    "name": item.model,
                    "score": item.score,
                    "status": item.status,
                    "lane": item.lane,
                    "detail": item.detail,
                }
                for item in coordinator.qualification.list_results()
            ]
        budget = None
        if coordinator.budget is not None:
            budget = coordinator.budget.snapshot().to_json()
        return jsonify({
            "compute": {
                "vram_used_mb": None,
                "vram_total_mb": None,
                "tokens_per_sec": None,
                "active_local_runs": active_local,
                "active_cloud_runs": active_cloud,
                "instrumented": False,
            },
            "qualification": qualification,
            "budget": budget,
        })

    @app.get("/api/v1/sops")
    def sops():
        return jsonify({"sops": [sop.to_json() for sop in list_builtin_sops()]})

    @app.post("/api/v1/router/recommend")
    def router_recommend():
        data = request.get_json(force=True) or {}
        req_text = data.get("request", "")
        recommendation = recommend_route(req_text, coordinator.models.profiles())
        return jsonify(recommendation.to_json())

    @app.post("/api/v1/projects/context")
    def project_context():
        data = request.get_json(force=True) or {}
        root = data.get("root", "")
        if not root:
            return jsonify({"error": "root is required"}), 400
        root_path = Path(root)
        if not root_path.is_dir():
            return jsonify({"error": "project root directory does not exist"}), 404
        content = read_project_context(root_path)
        return jsonify({"root": str(root_path.resolve()), "context": content})

    @app.get("/api/v1/budget")
    def budget():
        if coordinator.budget is None:
            return jsonify({"error": "budget ledger is not configured"}), 404
        return jsonify(coordinator.budget.snapshot().to_json())

    @app.get("/api/v1/qualification")
    def qualification():
        if coordinator.qualification is None:
            return jsonify({"qualification": []})
        return jsonify({
            "qualification": [item.to_json() for item in coordinator.qualification.list_results()],
        })

    @app.post("/api/v1/qualification/run")
    def qualification_run():
        if coordinator.qualification is None:
            return jsonify({"error": "qualification store is not configured"}), 404
        data = request.get_json(force=True) or {}
        model = str(data.get("model", "")).strip()
        if not model:
            return jsonify({"error": "model is required"}), 400
        try:
            profile = coordinator.models.get(model)
            provider = profile.provider.value
        except ModelPolicyError as exc:
            return jsonify({"error": str(exc)}), 400
        edit_runner = None
        if provider != "cloud" and hasattr(coordinator.executor, "run"):
            edit_runner = build_native_edit_runner(coordinator.executor)
        evidence = run_offline_edit_corpus(
            model,
            provider=provider,
            store=coordinator.qualification,
            edit_runner=edit_runner,
        )
        return jsonify(evidence.to_json())

    @app.post("/api/v1/intent")
    def classify_request_intent():
        data = request.get_json(force=True) or {}
        phrase = str(data.get("request", "")).strip()
        project_root = str(data.get("project_root", "")).strip()
        chat_model = str(data.get("chat_model", "")).strip()
        if not phrase or not project_root:
            return jsonify({"error": "request and project_root are required"}), 400
        root = Path(project_root)
        if not root.is_dir():
            return jsonify({"error": "project_root must be an existing directory"}), 400

        chat_fn = None
        model_name = None
        adapter = getattr(coordinator.executor, "model", None)
        complete_text = getattr(adapter, "complete_text", None) if adapter is not None else None
        if callable(complete_text) and chat_model:
            model_name = chat_model
            chat_fn = complete_text
        intent = classify_intent(phrase, root, model=model_name, chat_fn=chat_fn)
        return jsonify({"intent": intent.to_json()})

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

    @app.post("/api/v1/projects/resolve")
    def resolve_project():
        data = request.get_json(force=True)
        phrase = str(data.get("phrase", "")).strip()
        if not phrase:
            return jsonify({"error": "phrase is required"}), 400
        matches = resolve_project_reference(phrase, coordinator.store.list_projects())
        return jsonify({
            "phrase": phrase,
            "decisive": len(matches) == 1,
            "matches": [
                {"project_id": m.project_id, "display_name": m.display_name,
                 "root": m.root, "score": m.score}
                for m in matches
            ],
        })

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
                offline=data.get("offline") is True,
            )
        except ValueError:
            return jsonify({"error": "unknown run mode"}), 400
        if not task_request.request or not task_request.project_root:
            return jsonify({"error": "request and project_root are required"}), 400
        record = coordinator.submit(task_request)
        if record.status.value == "blocked":
            return jsonify(record.to_json()), 409
        # Talk-only can complete without a plan/proposal. Write modes wait.
        if record.status == TaskStatus.ACCEPTED and record.request.mode == RunMode.TALK_ONLY:
            Thread(target=coordinator.execute, args=(record.task_id,), daemon=True).start()
        return jsonify(record.to_json()), 202

    @app.post("/api/v1/tasks/<task_id>/propose")
    def propose_task(task_id: str):
        try:
            record = coordinator.prepare_proposal(task_id)
        except KeyError:
            return jsonify({"error": "task not found"}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        proposal = coordinator.store.proposal(task_id)
        payload = record.to_json()
        if proposal is not None:
            payload["proposal"] = proposal.to_json()
        status_code = 200 if record.status == TaskStatus.WAITING_FOR_APPROVAL else 409
        return jsonify(payload), status_code

    @app.post("/api/v1/tasks/<task_id>/approve")
    def approve_task(task_id: str):
        data = request.get_json(force=True) or {}
        digest = str(data.get("digest", "")).strip()
        try:
            record = coordinator.approve(task_id, digest=digest)
        except KeyError:
            return jsonify({"error": "task not found"}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        Thread(target=coordinator.execute, args=(record.task_id,), daemon=True).start()
        return jsonify(record.to_json()), 202

    @app.post("/api/v1/tasks/<task_id>/cancel")
    def cancel_task(task_id: str):
        try:
            record = coordinator.cancel(task_id)
        except KeyError:
            return jsonify({"error": "task not found"}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(record.to_json()), 200

    @app.delete("/api/v1/tasks/<task_id>")
    def delete_task_route(task_id: str):
        deleted = coordinator.delete_task(task_id)
        if not deleted:
            return jsonify({"error": "task not found"}), 404
        return jsonify({"ok": True, "deleted_task_id": task_id}), 200

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
        if record.status not in {TaskStatus.ACCEPTED, TaskStatus.EXPLORING}:
            return jsonify({
                "error": "plan drafting is available only before proposal preparation",
            }), 409
        project_root = Path(record.request.project_root)
        chat_fn = None
        adapter = getattr(coordinator.executor, "model", None)
        complete_text = getattr(adapter, "complete_text", None) if adapter is not None else None
        if callable(complete_text) and record.request.chat_model:
            chat_fn = complete_text
        intent = classify_intent(
            record.request.request,
            project_root,
            model=record.request.chat_model if chat_fn is not None else None,
            chat_fn=chat_fn,
        )
        result = draft_evidence_plan(record.request.request, project_root)
        if not result.ok or result.plan is None:
            # Fall back to a bounded edit plan for a request that names one
            # existing file whose test can be located. The user still
            # reviews these exact files before approval.
            result = draft_edit_plan(record.request.request, project_root)
        if (not result.ok or result.plan is None) and project_root.is_dir():
            # Optional local agentic locate when the deterministic ladder misses.
            adapter = getattr(coordinator.executor, "model", None)
            tool_fn = getattr(adapter, "complete_with_tools", None)
            chat_model = record.request.chat_model
            if callable(tool_fn) and not is_cloud_model(chat_model):
                located = locate_target_with_exploration(
                    record.request.request,
                    project_root,
                    chat_model,
                    chat_resp_fn=tool_fn,
                )
                if located.ok:
                    rewritten = (
                        f"{record.request.request} (target file: {located.target_file})"
                    )
                    result = draft_edit_plan(rewritten, project_root)
                    if result.ok and result.plan is not None:
                        coordinator.store.append_event(
                            task_id,
                            "target_located",
                            f"{located.target_file} ({located.reason or 'agentic locate'})",
                        )
        if not result.ok or result.plan is None:
            payload = {
                "ok": False,
                "reason": result.reason,
                "intent": intent.to_json(),
            }
            if intent.kind in {"question", "chat"}:
                payload["hint"] = (
                    "Use Talk Only for questions; Ask Before Changes is for write plans."
                )
            if intent.kind == "audit":
                payload["context"] = explore_project(
                    project_root, record.request.request,
                ).to_json()
                payload["hint"] = (
                    "Audit/explore is read-only; name a specific edit target to draft a write plan."
                )
            return jsonify(payload), 422
        coordinator.store.save_plan(task_id, result.plan)
        envelope = explore_project(project_root, record.request.request)
        return jsonify({
            "ok": True,
            "task_id": task_id,
            "plan": result.plan.to_json(),
            "context": envelope.to_json(),
            "intent": intent.to_json(),
        })

    @app.get("/api/v1/tasks/<task_id>")
    def task_status(task_id: str):
        record = coordinator.store.get(task_id)
        if record is None:
            return jsonify({"error": "task not found"}), 404
        proposal = coordinator.store.proposal(task_id)
        approval = coordinator.store.approval(task_id)
        payload = {
            **record.to_json(),
            "events": [event.to_json() for event in coordinator.store.events(task_id)],
            "plan": coordinator.store.plan(task_id),
        }
        if proposal is not None:
            # Omit full file contents from default status to keep payloads small;
            # diffs + digest are what the approval UI needs.
            payload["proposal"] = {
                "digest": proposal.digest,
                "summary": proposal.summary,
                "diffs": proposal.diffs,
                "files": sorted(proposal.files),
            }
        if approval is not None:
            payload["approval"] = approval
        return jsonify(payload)

    return app
