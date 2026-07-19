from __future__ import annotations

from pathlib import Path

from wisense_os.qualification import (
    CorpusTask,
    QualificationStore,
    run_offline_edit_corpus,
)


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
