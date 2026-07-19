from __future__ import annotations

from pathlib import Path

from wisense_os.plan import draft_evidence_plan


def test_endpoint_request_becomes_an_evidence_backed_existing_file_plan(tmp_path: Path) -> None:
    api = tmp_path / "wisense_os" / "api.py"
    api.parent.mkdir()
    api.write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    fixture = tmp_path / "tests" / "test_bootstrap.py"
    fixture.parent.mkdir()
    fixture.write_text("def test_api(test_client): pass\n", encoding="utf-8")
    scratch_api = tmp_path / ".pytest_tmp" / "copied" / "wisense_os" / "api.py"
    scratch_api.parent.mkdir(parents=True)
    scratch_api.write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")

    result = draft_evidence_plan(
        "Add a GET /api/v1/version endpoint that returns JSON.", tmp_path,
    )

    assert result.ok
    assert result.plan is not None
    assert result.plan.files == ("wisense_os/api.py", "tests/test_bootstrap.py")
    assert result.plan.source == "evidence"


def test_unknown_request_refuses_to_invent_a_plan(tmp_path: Path) -> None:
    assert draft_evidence_plan("make the app nicer", tmp_path).reason == "evidence_plan_unavailable"
