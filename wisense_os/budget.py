"""Cloud spend ledger with reserve-then-reconcile accounting.

Local models are free. Cloud models must reserve estimated cost before a
call and reconcile to actual (or release) afterward. Unknown pricing fails
closed rather than silently under-estimating.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from uuid import uuid4
from typing import Any


class BudgetExceededError(RuntimeError):
    pass


class UnknownModelPricingError(ValueError):
    pass


# USD per 1M tokens (input, output). Supervised testing placeholders —
# replace with billed rates when available; never invent a cheaper substitute.
DEFAULT_CLOUD_PRICING: dict[str, tuple[float, float]] = {
    "gemma4:31b-cloud": (0.20, 0.80),
    "glm-5.2:cloud": (0.20, 0.80),
}

DEFAULT_CAP_USD = 20.0


def estimate_tokens(text: str) -> int:
    # Rough 4 chars/token heuristic for pre-call reservations.
    return max(1, (len(text) + 3) // 4)


def estimate_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, tuple[float, float]] | None = None,
) -> float:
    table = pricing or DEFAULT_CLOUD_PRICING
    if model not in table:
        raise UnknownModelPricingError(
            f"No pricing configured for model {model!r} — refusing to estimate"
        )
    input_price, output_price = table[model]
    return (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)


@dataclass(frozen=True)
class BudgetSnapshot:
    cap_usd: float
    confirmed_usd: float
    reserved_usd: float

    @property
    def exposure_usd(self) -> float:
        return self.confirmed_usd + self.reserved_usd

    def to_json(self) -> dict[str, Any]:
        return {
            "cap_usd": self.cap_usd,
            "confirmed_usd": round(self.confirmed_usd, 6),
            "reserved_usd": round(self.reserved_usd, 6),
            "exposure_usd": round(self.exposure_usd, 6),
        }


class BudgetLedger:
    def __init__(
        self,
        path: Path,
        *,
        cap_usd: float = DEFAULT_CAP_USD,
        pricing: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self.path = path
        self.cap_usd = cap_usd
        self.pricing = pricing or dict(DEFAULT_CLOUD_PRICING)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self._write({"confirmed": [], "pending": {}})

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def snapshot(self) -> BudgetSnapshot:
        data = self._read()
        confirmed = sum(float(item["usd"]) for item in data.get("confirmed", []))
        reserved = sum(float(item["usd"]) for item in data.get("pending", {}).values())
        return BudgetSnapshot(self.cap_usd, confirmed, reserved)

    def reserve(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        task_id: str = "",
    ) -> str:
        estimated = estimate_cost_usd(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            pricing=self.pricing,
        )
        snap = self.snapshot()
        if snap.exposure_usd + estimated > self.cap_usd:
            raise BudgetExceededError(
                f"Projected spend ${snap.exposure_usd + estimated:.4f} would exceed "
                f"cap ${self.cap_usd:.4f}"
            )
        reservation_id = str(uuid4())
        data = self._read()
        data.setdefault("pending", {})[reservation_id] = {
            "usd": estimated,
            "model": model,
            "task_id": task_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        self._write(data)
        return reservation_id

    def reconcile(self, reservation_id: str, *, actual_usd: float | None = None) -> None:
        data = self._read()
        pending = data.get("pending", {})
        entry = pending.pop(reservation_id, None)
        if entry is None:
            return
        usd = float(actual_usd) if actual_usd is not None else float(entry["usd"])
        data.setdefault("confirmed", []).append({
            "usd": usd,
            "model": entry.get("model"),
            "task_id": entry.get("task_id"),
            "reservation_id": reservation_id,
        })
        data["pending"] = pending
        self._write(data)

    def release(self, reservation_id: str) -> None:
        data = self._read()
        pending = data.get("pending", {})
        pending.pop(reservation_id, None)
        data["pending"] = pending
        self._write(data)
