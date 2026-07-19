"""The REAL PytestRunner (not the fake) must isolate the target-project
subprocess: no stale bytecode, no cache, no basetemp litter -- so it can
never report a false pass on broken code and never leaves an untracked
directory behind. Ported from the LAWC check-runner audit (B1 + stale
bytecode)."""

from __future__ import annotations

from pathlib import Path

from wisense_os.patch_executor import PytestRunner


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _project(root: Path, impl: str) -> None:
    # pytest.ini pins rootdir to this throwaway project so the child run
    # is hermetic regardless of where tmp_path lives.
    _write(root, "pytest.ini", "[pytest]\n")
    _write(root, "sample.py", impl)
    _write(
        root, "test_sample.py",
        "from sample import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    )


def test_real_runner_passes_and_leaves_no_litter(tmp_path: Path) -> None:
    _project(tmp_path, "def add(a, b):\n    return a + b\n")

    passed, detail = PytestRunner(timeout_seconds=60.0).run(tmp_path, ("test_sample.py",))

    assert passed, detail
    assert list(tmp_path.glob(".wisense_pytest_*")) == []
    assert not (tmp_path / ".pytest_cache").exists()
    assert list(tmp_path.rglob("__pycache__")) == []


def test_real_runner_reports_a_genuine_failure(tmp_path: Path) -> None:
    _project(tmp_path, "def add(a, b):\n    return a - b\n")

    passed, detail = PytestRunner(timeout_seconds=60.0).run(tmp_path, ("test_sample.py",))

    assert passed is False
    assert "test_add" in detail
    assert list(tmp_path.glob(".wisense_pytest_*")) == []


def test_real_runner_cleans_basetemp_from_tmp_path_tests(tmp_path: Path) -> None:
    # A target test using tmp_path materializes the basetemp; it must be
    # removed so no untracked directory is left behind (LAWC bug B1).
    _write(tmp_path, "pytest.ini", "[pytest]\n")
    _write(
        tmp_path, "test_scratch.py",
        "def test_scratch(tmp_path):\n"
        "    (tmp_path / 'x.txt').write_text('y')\n"
        "    assert True\n",
    )

    passed, detail = PytestRunner(timeout_seconds=60.0).run(tmp_path, ("test_scratch.py",))

    assert passed, detail
    assert list(tmp_path.glob(".wisense_pytest_*")) == []
