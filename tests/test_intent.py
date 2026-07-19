from __future__ import annotations

from pathlib import Path

from wisense_os.intent import ParsedIntent, classify_intent, classify_intent_floor, merge_intent


def test_floor_detects_edit_without_literal_fix_verb(tmp_path: Path) -> None:
    (tmp_path / "billing.py").write_text("def totals():\n    return 0\n", encoding="utf-8")
    intent = classify_intent_floor("the tests are broken in billing.py", tmp_path)
    assert intent.kind == "edit"
    assert intent.target_file == "billing.py"


def test_floor_detects_question(tmp_path: Path) -> None:
    intent = classify_intent_floor("What does the billing module do?", tmp_path)
    assert intent.kind == "question"


def test_model_cannot_demote_floor_edit_to_chat(tmp_path: Path) -> None:
    floor = ParsedIntent("edit", "billing.py", "floor", "floor")
    model = ParsedIntent("chat", None, "model guess", "model")
    assert merge_intent(floor, model).kind == "edit"


def test_model_can_widen_chat_to_edit(tmp_path: Path) -> None:
    floor = ParsedIntent("chat", None, "floor", "floor")
    model = ParsedIntent("edit", "billing.py", "model", "model")
    assert merge_intent(floor, model).kind == "edit"


def test_classify_falls_back_when_model_returns_garbage(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("x=1\n", encoding="utf-8")

    def bad_chat(messages, *, model, timeout_seconds=30):
        return "not json at all"

    intent = classify_intent(
        "fix the bug in app.py",
        tmp_path,
        model="glm-5.2:cloud",
        chat_fn=bad_chat,
    )
    assert intent.kind == "edit"
    assert intent.source == "floor"
