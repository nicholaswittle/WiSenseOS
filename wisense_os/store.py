"""SQLite-backed task and event ledger.  Each operation gets its own connection
so the API worker and future UI event reader do not share thread-bound state."""

from __future__ import annotations

import json
import sqlite3
from uuid import uuid4
from pathlib import Path

from .contracts import ProjectRecord, RunMode, TaskEvent, TaskRecord, TaskRequest, TaskStatus
from .plan import TaskPlan


class TaskStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    request_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS task_events (
                    task_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    PRIMARY KEY (task_id, sequence)
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS task_plans (
                    task_id TEXT PRIMARY KEY,
                    plan_json TEXT NOT NULL
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    root TEXT NOT NULL UNIQUE,
                    local_autopilot_trusted INTEGER NOT NULL DEFAULT 0
                )"""
            )

    def register_project(
        self,
        *,
        display_name: str,
        root: str,
        local_autopilot_trusted: bool = False,
    ) -> ProjectRecord:
        clean_name = display_name.strip()
        if not clean_name:
            raise ValueError("display_name is required")
        candidate = Path(root).expanduser().resolve()
        if not candidate.is_dir():
            raise ValueError("root must be an existing directory")
        normalized_root = str(candidate)
        with self._connect() as db:
            existing = db.execute("SELECT * FROM projects WHERE root = ?", (normalized_root,)).fetchone()
            if existing is not None:
                return self._project_from_row(existing)
            record = ProjectRecord(
                project_id=str(uuid4()),
                display_name=clean_name,
                root=normalized_root,
                local_autopilot_trusted=local_autopilot_trusted,
            )
            db.execute(
                """INSERT INTO projects(project_id, display_name, root, local_autopilot_trusted)
                   VALUES (?, ?, ?, ?)""",
                (record.project_id, record.display_name, record.root, int(record.local_autopilot_trusted)),
            )
        return record

    def list_projects(self) -> list[ProjectRecord]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM projects ORDER BY display_name COLLATE NOCASE").fetchall()
        return [self._project_from_row(row) for row in rows]

    def create(self, record: TaskRecord) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO tasks(task_id, request_json, status, reason) VALUES (?, ?, ?, ?)",
                (record.task_id, json.dumps(record.to_json()["request"]), record.status.value, record.reason),
            )

    def update_status(self, task_id: str, status: TaskStatus, reason: str | None = None) -> None:
        with self._connect() as db:
            db.execute("UPDATE tasks SET status = ?, reason = ? WHERE task_id = ?", (status.value, reason, task_id))

    def append_event(self, task_id: str, kind: str, detail: str) -> TaskEvent:
        with self._connect() as db:
            sequence = db.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM task_events WHERE task_id = ?", (task_id,)
            ).fetchone()[0]
            db.execute(
                "INSERT INTO task_events(task_id, sequence, kind, detail) VALUES (?, ?, ?, ?)",
                (task_id, sequence, kind, detail),
            )
        return TaskEvent(task_id=task_id, sequence=sequence, kind=kind, detail=detail)

    def get(self, task_id: str) -> TaskRecord | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._record_from_row(row)

    def list_tasks(self, limit: int = 50) -> list[TaskRecord]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM tasks ORDER BY rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return [record for row in rows if (record := self._record_from_row(row)) is not None]

    def _record_from_row(self, row: sqlite3.Row | None) -> TaskRecord | None:
        if row is None:
            return None
        data = json.loads(row["request_json"])
        request = TaskRequest(
            request=data["request"], project_root=data["project_root"],
            mode=RunMode(data["mode"]), chat_model=data["chat_model"], builder_model=data["builder_model"],
        )
        return TaskRecord(task_id=row["task_id"], request=request, status=TaskStatus(row["status"]), reason=row["reason"])

    @staticmethod
    def _project_from_row(row: sqlite3.Row) -> ProjectRecord:
        return ProjectRecord(
            project_id=row["project_id"],
            display_name=row["display_name"],
            root=row["root"],
            local_autopilot_trusted=bool(row["local_autopilot_trusted"]),
        )

    def events(self, task_id: str) -> list[TaskEvent]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM task_events WHERE task_id = ? ORDER BY sequence", (task_id,)).fetchall()
        return [TaskEvent(task_id=row["task_id"], sequence=row["sequence"], kind=row["kind"], detail=row["detail"]) for row in rows]

    def provider_input_waiting_task(self, *, exclude_task_id: str = "") -> TaskRecord | None:
        """Return the one executor conversation that must be resumed first."""
        with self._connect() as db:
            row = db.execute(
                """SELECT * FROM tasks WHERE status = ? AND task_id != ?
                   ORDER BY rowid ASC LIMIT 1""",
                (TaskStatus.WAITING_FOR_PROVIDER_INPUT.value, exclude_task_id),
            ).fetchone()
        return self._record_from_row(row)

    def save_plan(self, task_id: str, plan: TaskPlan) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO task_plans(task_id, plan_json) VALUES (?, ?)",
                (task_id, json.dumps(plan.to_json())),
            )

    def plan(self, task_id: str) -> dict[str, object] | None:
        with self._connect() as db:
            row = db.execute("SELECT plan_json FROM task_plans WHERE task_id = ?", (task_id,)).fetchone()
        return json.loads(row["plan_json"]) if row is not None else None
