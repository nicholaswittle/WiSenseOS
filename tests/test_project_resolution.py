"""Advisory project-nickname resolution: decisive vs. ambiguous vs.
unknown, dead paths never offered, and the API endpoint."""

from __future__ import annotations

from pathlib import Path

from wisense_os.bootstrap import create_default_app
from wisense_os.contracts import ProjectRecord
from wisense_os.project_resolution import resolve_project_reference


def _record(project_id: str, name: str, root: Path) -> ProjectRecord:
    return ProjectRecord(project_id, name, str(root), False)


def test_decisive_ambiguous_and_unknown(tmp_path: Path) -> None:
    billing = tmp_path / "billing_service"
    horizon_a = tmp_path / "wisense_horizon_v2"
    horizon_b = tmp_path / "wisense_new_horizon"
    for path in (billing, horizon_a, horizon_b):
        path.mkdir()
    projects = [
        _record("1", "Billing Service", billing),
        _record("2", "Horizon V2", horizon_a),
        _record("3", "New Horizon", horizon_b),
    ]

    decisive = resolve_project_reference("the billing project", projects)
    assert len(decisive) == 1 and decisive[0].project_id == "1"

    close = resolve_project_reference("horizon", projects)
    assert {m.project_id for m in close} == {"2", "3"}

    assert resolve_project_reference("nonexistent thing", projects) == []


def test_dead_paths_are_never_offered(tmp_path: Path) -> None:
    alive = tmp_path / "billing_service"
    alive.mkdir()
    dead = tmp_path / "removed_project"  # never created
    projects = [
        _record("1", "Billing Service", alive),
        _record("2", "Removed Project", dead),
    ]
    assert resolve_project_reference("removed project", projects) == []
    assert len(resolve_project_reference("billing", projects)) == 1


def test_resolve_endpoint_returns_ranked_matches(tmp_path: Path) -> None:
    project_dir = tmp_path / "billing_service"
    project_dir.mkdir()
    app = create_default_app(tmp_path / "state")
    client = app.test_client()
    client.post("/api/v1/projects", json={
        "display_name": "Billing Service", "root": str(project_dir)})

    missing = client.post("/api/v1/projects/resolve", json={"phrase": "  "})
    assert missing.status_code == 400

    body = client.post(
        "/api/v1/projects/resolve", json={"phrase": "the billing project"}
    ).get_json()
    assert body["decisive"] is True
    assert body["matches"][0]["root"] == str(project_dir.resolve())
