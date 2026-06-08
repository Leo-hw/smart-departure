"""Privacy helpers for public logs and persisted runtime state."""

from __future__ import annotations

import hashlib


def short_id(raw_value: str) -> str:
    """Return a stable, non-reversible identifier for logs and caches."""
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()[:8]


def safe_exception_label(exc: BaseException) -> str:
    """Describe an exception without exposing its potentially sensitive message."""
    return type(exc).__name__
