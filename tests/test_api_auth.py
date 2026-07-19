"""Loopback token gate: enforced when a token is issued, health exempt,
open for in-process tests that construct the app without a token."""

from __future__ import annotations

from pathlib import Path

from wisense_os.bootstrap import create_default_app, issue_launch_token


def test_requests_without_a_valid_token_are_rejected(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state", auth_token="s3cret-token")
    client = app.test_client()

    # health is exempt so a client can probe readiness first
    assert client.get("/api/v1/health").status_code == 200

    # every other route requires the token
    assert client.get("/api/v1/tasks").status_code == 401
    assert client.get("/api/v1/models").status_code == 401
    assert client.get(
        "/api/v1/tasks", headers={"X-WiSense-Token": "wrong"}
    ).status_code == 401


def test_correct_token_is_accepted_via_either_header(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state", auth_token="s3cret-token")
    client = app.test_client()

    assert client.get(
        "/api/v1/tasks", headers={"X-WiSense-Token": "s3cret-token"}
    ).status_code == 200
    assert client.get(
        "/api/v1/tasks", headers={"Authorization": "Bearer s3cret-token"}
    ).status_code == 200


def test_app_without_a_token_stays_open_for_in_process_tests(tmp_path: Path) -> None:
    app = create_default_app(tmp_path / "state")  # no token
    assert app.test_client().get("/api/v1/tasks").status_code == 200


def test_issue_launch_token_persists_a_readable_token(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    token = issue_launch_token(state_dir)
    assert token and len(token) >= 32
    assert (state_dir / "engine_token").read_text(encoding="utf-8") == token
