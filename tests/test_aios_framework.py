"""Tests for AIOS framework components: context, router, and skills."""

from pathlib import Path
import tempfile

from wisense_os.context import generate_project_context, read_project_context, write_project_context_file
from wisense_os.contracts import ProviderKind
from wisense_os.model_policy import ModelProfile
from wisense_os.router import assess_task_complexity, recommend_route
from wisense_os.skills import list_builtin_sops, get_sop_by_id


def test_context_generation_and_reading():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "pubspec.yaml").write_text("name: test_app", encoding="utf-8")
        (root / "lib").mkdir()

        ctx_str = generate_project_context(root)
        assert isinstance(ctx_str, str)
        assert "Flutter / Dart" in ctx_str

        ctx_file = write_project_context_file(root)
        assert ctx_file.exists()
        assert ctx_file.name == "CONTEXT.md"

        content = read_project_context(root)
        assert "Flutter / Dart" in content
        assert "Project Topology & Memory Context" in content


def test_task_complexity_assessment():
    assert assess_task_complexity("fix typo in readme") == "low"
    assert assess_task_complexity("refactor architectural layout for security audit across all packages") == "high"
    assert assess_task_complexity("add tests for user login feature") == "medium"


def test_recommend_route():
    profiles = [
        ModelProfile(
            name="qwen2.5-coder:7b",
            provider=ProviderKind.LOCAL,
            roles=("chat", "builder"),
            available=True,
            supervised_testing_only=False,
            future_local_target=False,
        ),
        ModelProfile(
            name="claude-3-7-sonnet",
            provider=ProviderKind.CLOUD,
            roles=("builder",),
            available=True,
            supervised_testing_only=True,
            future_local_target=False,
        ),
    ]

    rec_low = recommend_route("fix typo in README", profiles)
    assert rec_low.complexity == "low"
    assert rec_low.builder_model == "qwen2.5-coder:7b"
    assert rec_low.estimated_cost == 0.0

    rec_high = recommend_route("architect complete security audit and refactor module", profiles)
    assert rec_high.complexity == "high"
    assert rec_high.builder_model == "claude-3-7-sonnet"
    assert rec_high.estimated_cost == 0.15


def test_sop_workflow_list():
    sops = list_builtin_sops()
    assert len(sops) >= 4
    audit_sop = get_sop_by_id("code_audit")
    assert audit_sop is not None
    assert audit_sop.name == "Security & Quality Audit"
