from __future__ import annotations

import json
from pathlib import Path

from wisense_os.patch_executor import PlanBoundPatchExecutor, PytestRunner
from wisense_os.qualification import (
    EDIT_CORPUS,
    CorpusTask,
    QualificationStore,
    build_native_edit_runner,
    run_offline_edit_corpus,
)


class _ScriptedModel:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)

    def complete(self, messages, *, model, timeout_seconds=120.0, structured_patch=True):
        del messages, model, timeout_seconds, structured_patch
        if not self._replies:
            raise RuntimeError("no scripted replies left")
        return self._replies.pop(0)


def test_cloud_model_corpus_is_not_applicable(tmp_path: Path) -> None:
    store = QualificationStore(tmp_path / "q.json")
    evidence = run_offline_edit_corpus(
        "gemma4:31b-cloud", provider="cloud", store=store,
    )
    assert evidence.status == "not_applicable"
    assert evidence.score is None
    assert "offline-only" in evidence.detail


def test_local_corpus_records_qualified_when_runner_passes(tmp_path: Path) -> None:
    store = QualificationStore(tmp_path / "q.json")

    def always_pass(task: CorpusTask, scratch: Path, model: str) -> bool:
        assert (scratch / task.target_file).is_file()
        assert model == "local-coder:7b"
        return True

    evidence = run_offline_edit_corpus(
        "local-coder:7b",
        provider="local",
        store=store,
        edit_runner=always_pass,
    )
    assert evidence.status == "qualified"
    assert evidence.score == 100.0
    assert "greeting_edit=pass" in evidence.detail


def test_local_corpus_records_failed_without_inventing_pass(tmp_path: Path) -> None:
    store = QualificationStore(tmp_path / "q.json")
    evidence = run_offline_edit_corpus(
        "local-coder:7b",
        provider="local",
        store=store,
        # default runner fails closed
    )
    assert evidence.status == "failed"
    assert evidence.score == 0.0


def test_native_edit_runner_passes_when_model_fixes_scratch_corpus(tmp_path: Path) -> None:
    greeting_fix = json.dumps({"files": [
        {"path": "greeting.py", "content": "def greet(name):\n    return f'Hello, {name}!'\n"},
        {"path": "test_greeting.py", "content": EDIT_CORPUS[0].seed_files["test_greeting.py"]},
    ]})
    totals_fix = json.dumps({"files": [
        {"path": "billing.py", "content": "def totals(items):\n    return sum(items)\n"},
        {"path": "test_billing.py", "content": EDIT_CORPUS[1].seed_files["test_billing.py"]},
    ]})
    executor = PlanBoundPatchExecutor(
        _ScriptedModel([greeting_fix, totals_fix]),
        PytestRunner(),
        commit_on_success=False,
    )
    store = QualificationStore(tmp_path / "q.json")
    evidence = run_offline_edit_corpus(
        "local-coder:7b",
        provider="local",
        store=store,
        edit_runner=build_native_edit_runner(executor),
    )
    assert evidence.status == "qualified"
    assert evidence.score == 100.0
    assert evidence.max_rewrite_bytes_seen is not None
    assert evidence.max_rewrite_bytes_seen > 0
