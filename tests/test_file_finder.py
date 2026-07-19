from __future__ import annotations

from pathlib import Path

from wisense_os.file_finder import resolve_target_file


def test_resolve_explicit_basename_when_unique(tmp_path: Path) -> None:
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "billing.py").write_text("def totals():\n    return 1\n", encoding="utf-8")

    result = resolve_target_file(tmp_path, "fix the totals bug in billing.py")

    assert result.status == "resolved"
    assert result.file == "lib/billing.py"


def test_resolve_refuses_ambiguous_identifier_matches(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "pricing.py").write_text("def discount(): pass\n", encoding="utf-8")
    (tmp_path / "b" / "checkout.py").write_text("def discount(): pass\n", encoding="utf-8")

    result = resolve_target_file(tmp_path, "change the discount() behavior")

    assert result.status == "ambiguous"
    assert len(result.candidates) >= 2
