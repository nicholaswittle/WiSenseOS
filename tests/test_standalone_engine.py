from __future__ import annotations

from pathlib import Path


def test_native_engine_source_has_no_legacy_runtime_import_or_bridge_reference() -> None:
    package = Path(__file__).parents[1] / "wisense_os"
    forbidden = ("local_agent_work_center", "local-agent-work-center", "from my_ai", "import my_ai")

    for source in package.rglob("*.py"):
        contents = source.read_text(encoding="utf-8").lower()
        assert not any(term in contents for term in forbidden), source
