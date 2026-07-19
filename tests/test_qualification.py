from __future__ import annotations

from pathlib import Path

from wisense_os.bootstrap import create_default_app
from wisense_os.qualification import QualificationStore, record_offline_baseline


def test_offline_baseline_marks_cloud_as_not_applicable(tmp_path: Path) -> None:
    store = QualificationStore(tmp_path / "qualification.json")
    recorded = record_offline_baseline(
        store,
        configured_models=[("gemma4:31b-cloud", "cloud"), ("local-coder", "local")],
    )
    by_model = {item.model: item for item in recorded}
    assert by_model["gemma4:31b-cloud"].status == "not_applicable"
    assert by_model["local-coder"].status == "unevaluated"
    assert "failed" not in {item.status for item in recorded}


def test_live_api_surfaces_qualification_without_inventing_scores(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")
    payload = app.test_client().get("/api/v1/qualification").get_json()
    assert "qualification" in payload
    statuses = {row["status"] for row in payload["qualification"]}
    assert "not_applicable" in statuses
    for row in payload["qualification"]:
        if row["status"] == "not_applicable":
            assert row.get("score") is None
