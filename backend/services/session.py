"""Helpers for lightweight anonymous workspace isolation."""

from __future__ import annotations

import re


DEFAULT_USER_ID = "anonymous"
_SAFE_USER_ID = re.compile(r"[^a-zA-Z0-9_.:-]")


def normalize_user_id(user_id: str | None) -> str:
    """Return a safe, stable user/workspace id for database filtering."""
    cleaned = _SAFE_USER_ID.sub("", (user_id or "").strip())
    return cleaned[:80] or DEFAULT_USER_ID
