from __future__ import annotations

import json
from pathlib import Path

import pytest

from wisense_os.patch_protocol import PatchProtocolError, apply_candidate, parse_patch_candidate
from wisense_os.plan import TaskPlan
from wisense_os.workspace import snapshot_reviewed_files


def plan() -> TaskPlan:
    return TaskPlan("Edit", "test", ("app.py", "test_app.py"), ("contract",), ("acceptance",))


def proposal(*entries: dict[str, str]) -> str:
    return json.dumps({"files": list(entries)})


def test_candidate_requires_exactly_the_reviewed_file_set(tmp_path: Path) -> None:
    for name in plan().files:
        (tmp_path / name).write_text("before", encoding="utf-8")

    candidate = parse_patch_candidate(proposal(
        {"path": "app.py", "content": "after app"},
        {"path": "test_app.py", "content": "after test"},
    ), plan())
    apply_candidate(snapshot_reviewed_files(tmp_path, plan()), candidate)

    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "after app"
    assert (tmp_path / "test_app.py").read_text(encoding="utf-8") == "after test"


def test_candidate_accepts_a_single_whole_response_json_fence() -> None:
    raw = "```json\n" + proposal(
        {"path": "app.py", "content": "after app"},
        {"path": "test_app.py", "content": "after test"},
    ) + "\n```"

    candidate = parse_patch_candidate(raw, plan())

    assert dict(candidate.files) == {
        "app.py": "after app",
        "test_app.py": "after test",
    }


def test_candidate_accepts_one_final_json_object_after_a_model_lead_in() -> None:
    raw = "I prepared the requested patch:\n" + proposal(
        {"path": "app.py", "content": "after app"},
        {"path": "test_app.py", "content": "after test"},
    )

    candidate = parse_patch_candidate(raw, plan())

    assert dict(candidate.files)["app.py"] == "after app"


def test_candidate_accepts_exactly_labeled_source_blocks_for_reviewed_paths() -> None:
    raw = """### `app.py`
```python
def app():
    return 1
```

### `test_app.py`
```python
def test_app():
    assert True
```
"""

    candidate = parse_patch_candidate(raw, plan())

    assert dict(candidate.files) == {
        "app.py": "def app():\n    return 1",
        "test_app.py": "def test_app():\n    assert True",
    }


@pytest.mark.parametrize("raw, error", [
    ("not json", "not valid JSON"),
    ("Here is the result:\n```json\n{}\n```", "not valid JSON"),
    (proposal({"path": "app.py", "content": "x"}, {"path": "test_app.py", "content": "x"}) + "\nextra prose", "not valid JSON"),
    ("### `app.py`\n```python\nx\n```", "not valid JSON"),
    ("### `app.py`\n```python\nx\n```\n### `test_app.py`\n```python\ny\n```\n```python\nz\n```", "not valid JSON"),
    (json.dumps({"files": [{"path": "app.py", "content": "x"}]}), "omits reviewed"),
    (json.dumps({"files": [{"path": "app.py", "content": "x"}, {"path": "test_app.py", "content": "x"}, {"path": "other.py", "content": "x"}]}), "unreviewed"),
    (json.dumps({"files": [{"path": "app.py", "content": "x"}, {"path": "app.py", "content": "x"}]}), "repeats"),
])
def test_candidate_rejects_malformed_or_scope_widening_output(raw: str, error: str) -> None:
    with pytest.raises(PatchProtocolError, match=error):
        parse_patch_candidate(raw, plan())
