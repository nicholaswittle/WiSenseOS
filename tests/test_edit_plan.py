"""Bounded edit-plan drafting: one named existing file + a locatable
test yields a reviewable plan; ambiguity refuses rather than guesses."""

from __future__ import annotations

from pathlib import Path

from wisense_os.plan import draft_edit_plan


def _write(root: Path, rel: str, content: str = "x = 1\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_convention_test_is_located(tmp_path: Path) -> None:
    _write(tmp_path, "billing.py", "def total():\n    return 0\n")
    _write(tmp_path, "test_billing.py", "from billing import total\n")

    result = draft_edit_plan("fix the totals bug in billing.py", tmp_path)

    assert result.ok
    assert result.plan.files == ("billing.py", "test_billing.py")
    assert "billing.py" in result.plan.summary


def test_importing_test_is_located_when_no_convention_match(tmp_path: Path) -> None:
    _write(tmp_path, "pricing/discount.py", "def apply():\n    return 0\n")
    _write(tmp_path, "tests/test_checkout.py", "from pricing.discount import apply\n")

    result = draft_edit_plan("adjust pricing/discount.py rounding", tmp_path)

    assert result.ok
    assert result.plan.files == ("pricing/discount.py", "tests/test_checkout.py")


def test_explicitly_named_test_wins(tmp_path: Path) -> None:
    _write(tmp_path, "billing.py")
    _write(tmp_path, "test_billing.py")
    _write(tmp_path, "test_special.py", "import billing\n")

    result = draft_edit_plan("edit billing.py and check test_special.py", tmp_path)

    assert result.ok
    assert result.plan.files == ("billing.py", "test_special.py")


def test_refuses_when_no_file_named(tmp_path: Path) -> None:
    _write(tmp_path, "billing.py")
    result = draft_edit_plan("fix the totals bug", tmp_path)
    assert not result.ok
    assert result.reason == "edit_plan_needs_one_named_existing_file"


def test_refuses_when_two_impl_files_named(tmp_path: Path) -> None:
    _write(tmp_path, "billing.py")
    _write(tmp_path, "orders.py")
    _write(tmp_path, "test_billing.py")
    result = draft_edit_plan("change billing.py and orders.py", tmp_path)
    assert not result.ok
    assert result.reason == "edit_plan_needs_one_named_existing_file"


def test_refuses_when_no_test_can_be_located(tmp_path: Path) -> None:
    _write(tmp_path, "billing.py")
    result = draft_edit_plan("fix billing.py", tmp_path)
    assert result.ok is True
    assert "billing.py" in result.plan.files


def test_refuses_ambiguous_convention_tests(tmp_path: Path) -> None:
    _write(tmp_path, "billing.py")
    _write(tmp_path, "a/test_billing.py")
    _write(tmp_path, "b/test_billing.py")
    result = draft_edit_plan("fix billing.py", tmp_path)
    assert result.ok is True


def test_named_file_must_exist_and_stay_in_project(tmp_path: Path) -> None:
    _write(tmp_path, "test_billing.py")
    # names a non-existent file and a traversal path -- neither resolves
    result = draft_edit_plan("fix ../outside.py and missing.py", tmp_path)
    assert not result.ok
    assert result.reason == "edit_plan_needs_one_named_existing_file"
