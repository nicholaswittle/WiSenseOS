from __future__ import annotations

from pathlib import Path

from wisense_os.explore import explore_project


def test_explore_builds_context_envelope_with_snippet(tmp_path: Path) -> None:
    (tmp_path / "billing.py").write_text(
        "def totals(items):\n    return sum(items)\n",
        encoding="utf-8",
    )
    (tmp_path / "test_billing.py").write_text("def test_totals():\n    assert True\n", encoding="utf-8")

    envelope = explore_project(tmp_path, "fix totals() in billing.py")

    assert envelope.resolve_status == "resolved"
    assert envelope.target == "billing.py"
    assert envelope.snippets
    assert "totals" in envelope.snippets[0].text
