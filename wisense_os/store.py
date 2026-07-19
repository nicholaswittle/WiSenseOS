"""SQLite-backed task and event ledger.  Each operation gets its own connection
so the API worker and future UI event reader do not share thread-bound state."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .contracts import RunMode, TaskEvent, TaskRecord, TaskRequest, TaskStatus


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

    def events(self, task_id: str) -> list[TaskEvent]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM task_events WHERE task_id = ? ORDER BY sequence", (task_id,)).fetchall()
        return [TaskEvent(task_id=row["task_id"], sequence=row["sequence"], kind=row["kind"], detail=row["detail"]) for row in rows]
