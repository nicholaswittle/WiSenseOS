"""Full-file rewrite ceilings — refuse truncated/oversized candidates."""

from __future__ import annotations

from typing import Mapping

# Default reliable rewrite ceiling for current supervised cloud builders.
# Qualification may override per model later; never present a truncated
# rewrite as a validated change.
DEFAULT_MAX_REWRITE_BYTES = 48_000


class PatchSizeError(ValueError):
    """A candidate exceeds the builder's reliable full-file rewrite ceiling."""


def assert_rewrite_within_ceiling(
    files: Mapping[str, str],
    *,
    max_bytes: int = DEFAULT_MAX_REWRITE_BYTES,
) -> None:
    for path, content in files.items():
        size = len(content.encode("utf-8"))
        if size > max_bytes:
            raise PatchSizeError(
                f"full-file rewrite for {path} is {size} bytes; "
                f"ceiling is {max_bytes} bytes — split the file or use a "
                "bounded-edit protocol instead of accepting a truncated rewrite"
            )
