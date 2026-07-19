"""Builder qualification evidence store (recommend only; never auto-switch).

Statuses distinguish real failures from expected/not-applicable baselines.
Includes a small offline edit corpus that never touches production trees.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Literal


QualificationStatus = Literal["qualified", "failed", "not_applicable", "unevaluated"]


@dataclass(frozen=True)
class QualificationEvidence:
    model: str
    status: QualificationStatus
    score: float | None
    lane: str
    detail: str
    recorded_at: str
    max_rewrite_bytes_seen: int | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class QualificationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self._write({"results": []})

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_results(self) -> list[QualificationEvidence]:
        rows = self._read().get("results", [])
        out: list[QualificationEvidence] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(QualificationEvidence(
                model=str(row.get("model", "")),
                status=row.get("status", "unevaluated"),  # type: ignore[arg-type]
                score=(float(row["score"]) if row.get("score") is not None else None),
                lane=str(row.get("lane", "")),
                detail=str(row.get("detail", "")),
                recorded_at=str(row.get("recorded_at", "")),
                max_rewrite_bytes_seen=(
                    int(row["max_rewrite_bytes_seen"])
                    if row.get("max_rewrite_bytes_seen") is not None else None
                ),
            ))
        return out

    def record(self, evidence: QualificationEvidence) -> None:
        data = self._read()
        results = [row for row in data.get("results", []) if row.get("model") != evidence.model or row.get("lane") != evidence.lane]
        results.append(evidence.to_json())
        data["results"] = results
        self._write(data)


def record_offline_baseline(
    store: QualificationStore,
    *,
    configured_models: list[tuple[str, str]],
) -> list[QualificationEvidence]:
    """Mark cloud-only / missing local builders as not_applicable, not failed.

    configured_models: list of (name, provider)
    """
    now = datetime.now(timezone.utc).isoformat()
    recorded: list[QualificationEvidence] = []
    for name, provider in configured_models:
        if provider == "cloud":
            evidence = QualificationEvidence(
                model=name,
                status="not_applicable",
                score=None,
                lane="offline_builder",
                detail="cloud profile — offline qualification corpus does not apply",
                recorded_at=now,
            )
        else:
            evidence = QualificationEvidence(
                model=name,
                status="unevaluated",
                score=None,
                lane="offline_builder",
                detail="local builder present in config but corpus has not been run yet",
                recorded_at=now,
            )
        store.record(evidence)
        recorded.append(evidence)
    return recorded


@dataclass(frozen=True)
class CorpusTask:
    task_id: str
    lane: str
    description: str
    target_file: str
    seed_files: dict[str, str]
    expected_pass: bool = True


# Tiny fixed corpus. Candidate code is never persisted into evidence —
# only pass/fail, digests of outcomes, and timing.
EDIT_CORPUS: tuple[CorpusTask, ...] = (
    CorpusTask(
        task_id="greeting_edit",
        lane="edit",
        description="Make greet return Hello, <name>!",
        target_file="greeting.py",
        seed_files={
            "greeting.py": "def greet(name):\n    return name\n",
            "test_greeting.py": (
                "from greeting import greet\n\n"
                "def test_greet():\n"
                "    assert greet('Ada') == 'Hello, Ada!'\n"
            ),
        },
    ),
    CorpusTask(
        task_id="totals_edit",
        lane="edit",
        description="Fix totals to sum the list",
        target_file="billing.py",
        seed_files={
            "billing.py": "def totals(items):\n    return 0\n",
            "test_billing.py": (
                "from billing import totals\n\n"
                "def test_totals():\n"
                "    assert totals([1, 2, 3]) == 6\n"
            ),
        },
    ),
)


EditRunner = Callable[[CorpusTask, Path, str], bool]


def _default_edit_runner(task: CorpusTask, scratch: Path, model: str) -> bool:
    """Placeholder runner used only when no executor is injected.

    Real qualification injects a build_fn that calls the native propose/apply
    path against the scratch tree. This default always fails closed so an
    accidental live run without injection cannot invent a pass.
    """
    del scratch, model
    return False


def run_offline_edit_corpus(
    model: str,
    *,
    provider: str,
    store: QualificationStore,
    edit_runner: EditRunner | None = None,
    corpus: tuple[CorpusTask, ...] = EDIT_CORPUS,
) -> QualificationEvidence:
    """Run the offline edit corpus for one model and persist evidence."""
    now = datetime.now(timezone.utc).isoformat()
    if provider == "cloud" or model.endswith(":cloud") or "-cloud" in model:
        evidence = QualificationEvidence(
            model=model,
            status="not_applicable",
            score=None,
            lane="edit",
            detail="cloud_model_refused: qualification is offline-only",
            recorded_at=now,
        )
        store.record(evidence)
        return evidence

    runner = edit_runner or _default_edit_runner
    passed = 0
    details: list[str] = []
    for task in corpus:
        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="wisense_qual_") as tmp:
                scratch = Path(tmp)
                for rel, content in task.seed_files.items():
                    path = scratch / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
                ok = bool(runner(task, scratch, model))
        except Exception as exc:  # noqa: BLE001 — task failure is evidence
            ok = False
            details.append(f"{task.task_id}=harness_error:{type(exc).__name__}")
        else:
            details.append(f"{task.task_id}={'pass' if ok else 'fail'}")
        elapsed = round(time.perf_counter() - started, 3)
        details[-1] = f"{details[-1]}({elapsed}s)"
        if ok:
            passed += 1

    total = len(corpus)
    score = round(100.0 * passed / total, 1) if total else None
    if total == 0:
        status: QualificationStatus = "not_applicable"
    elif passed == total:
        status = "qualified"
    else:
        status = "failed"
    evidence = QualificationEvidence(
        model=model,
        status=status,
        score=score,
        lane="edit",
        detail="; ".join(details),
        recorded_at=now,
    )
    store.record(evidence)
    return evidence
