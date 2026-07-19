from __future__ import annotations

import pytest

from wisense_os.patch_limits import PatchSizeError, assert_rewrite_within_ceiling


def test_rewrite_ceiling_rejects_oversized_file() -> None:
    with pytest.raises(PatchSizeError, match="ceiling"):
        assert_rewrite_within_ceiling({"huge.py": "x" * 100}, max_bytes=50)


def test_rewrite_ceiling_allows_small_files() -> None:
    assert_rewrite_within_ceiling({"ok.py": "print(1)\n"}, max_bytes=50)
