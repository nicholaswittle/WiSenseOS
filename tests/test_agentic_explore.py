from __future__ import annotations

from pathlib import Path

from wisense_os.agentic_explore import (
    answer_with_exploration,
    is_cloud_model,
    locate_target_with_exploration,
)
from wisense_os.exploration_tools import dispatch_tool_call, grep_files, read_file


def test_is_cloud_model_detects_cloud_suffix() -> None:
    assert is_cloud_model("gemma4:31b-cloud")
    assert not is_cloud_model("qwen2.5-coder:7b")


def test_read_and_grep_tools_are_read_only(tmp_path: Path) -> None:
    (tmp_path / "billing.py").write_text(
        "def totals(items):\n    return sum(items)\n", encoding="utf-8",
    )
    read = read_file(tmp_path, "billing.py")
    assert "sum(items)" in read["content"]
    hits = grep_files(tmp_path, r"def totals")
    assert hits["matches"][0]["file"] == "billing.py"
    assert dispatch_tool_call(tmp_path, "read_file", {"path": "../secret"}) == {
        "error": "unsafe_path",
    }


def test_locate_refuses_cloud_models(tmp_path: Path) -> None:
    result = locate_target_with_exploration(
        "fix totals",
        tmp_path,
        "gemma4:31b-cloud",
        chat_resp_fn=lambda *a, **k: {"content": "{}"},
    )
    assert result.ok is False
    assert result.problem == "cloud_model_refused"


def test_locate_accepts_existing_file_from_tool_loop(tmp_path: Path) -> None:
    (tmp_path / "billing.py").write_text("def totals(items):\n    return 0\n", encoding="utf-8")

    calls = {"n": 0}

    def scripted(messages, *, model, tools=None):
        del messages, model, tools
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": "grep_files",
                        "arguments": {"pattern": "def totals"},
                    },
                }],
            }
        return {
            "role": "assistant",
            "content": '{"target_file": "billing.py", "reason": "defines totals"}',
        }

    result = locate_target_with_exploration(
        "fix totals to sum the list",
        tmp_path,
        "local-coder:7b",
        chat_resp_fn=scripted,
    )
    assert result.ok is True
    assert result.target_file == "billing.py"
    assert "grep_files" in result.tool_trace[0]


def test_answer_uses_tool_evidence(tmp_path: Path) -> None:
    (tmp_path / "greeting.py").write_text(
        "def greet(name):\n    return f'Hello, {name}!'\n", encoding="utf-8",
    )
    calls = {"n": 0}

    def scripted(messages, *, model, tools=None):
        del messages, model, tools
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": "read_file",
                        "arguments": {"path": "greeting.py"},
                    },
                }],
            }
        return {
            "role": "assistant",
            "content": "greet in greeting.py returns Hello, <name>!",
        }

    result = answer_with_exploration(
        "What does greet return?",
        tmp_path,
        "local-coder:7b",
        chat_resp_fn=scripted,
    )
    assert result.ok is True
    assert "greeting.py" in result.answer
    assert result.tool_trace == ("read_file(greeting.py)",)
