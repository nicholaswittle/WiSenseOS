"""Builder qualification evidence store (recommend only; never auto-switch).

Statuses distinguish real failures from expected/not-applicable baselines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal


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
