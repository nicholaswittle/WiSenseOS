from __future__ import annotations

from pathlib import Path

import pytest

from wisense_os.budget import BudgetExceededError, BudgetLedger, UnknownModelPricingError


def test_reserve_reconcile_tracks_exposure(tmp_path: Path) -> None:
    ledger = BudgetLedger(tmp_path / "budget.json", cap_usd=1.0)
    reservation = ledger.reserve(
        model="gemma4:31b-cloud", input_tokens=1000, output_tokens=1000, task_id="t1",
    )
    snap = ledger.snapshot()
    assert snap.reserved_usd > 0
    ledger.reconcile(reservation, actual_usd=0.01)
    done = ledger.snapshot()
    assert done.reserved_usd == 0
    assert done.confirmed_usd == 0.01


def test_unknown_model_pricing_fails_closed(tmp_path: Path) -> None:
    ledger = BudgetLedger(tmp_path / "budget.json")
    with pytest.raises(UnknownModelPricingError):
        ledger.reserve(model="mystery-cloud", input_tokens=10, output_tokens=10)


def test_cap_blocks_reservation(tmp_path: Path) -> None:
    ledger = BudgetLedger(tmp_path / "budget.json", cap_usd=0.0000001)
    with pytest.raises(BudgetExceededError):
        ledger.reserve(model="gemma4:31b-cloud", input_tokens=1_000_000, output_tokens=1_000_000)
