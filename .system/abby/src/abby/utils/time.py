"""Centralized date and time utilities for Abby Knowledge Vault."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional


def now_iso() -> str:
    """Return standard local ISO 8601 timestamp without timezone offset (YYYY-MM-DDTHH:MM:SS)."""
    return datetime.now().isoformat(timespec="seconds")


def now_utc_iso() -> str:
    """Return standard ISO 8601 UTC timestamp with trailing 'Z' (YYYY-MM-DDTHH:MM:SSZ)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_timestamp(val: Any) -> Optional[datetime]:
    """Resilient parser for ISO 8601 timestamps and dates.

    Supports:
    - datetime instances
    - date instances
    - YYYY-MM-DD strings
    - YYYY-MM-DDTHH:MM:SS strings (naive)
    - YYYY-MM-DDTHH:MM:SSZ strings (UTC)
    - ISO strings with +/-HH:MM offsets
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)

    cleaned = str(val).strip().strip("\"'")
    if not cleaned:
        return None

    # Handle YYYY-MM-DD
    if len(cleaned) == 10 and cleaned.count("-") == 2:
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d")
        except ValueError:
            return None

    try:
        iso_str = cleaned.replace("Z", "+00:00")
        return datetime.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return None


def is_timestamp_stale(
    stale_after: Optional[str | datetime | date],
    reference_dt: Optional[datetime] = None,
) -> bool:
    """Dynamically determine whether stale_after has passed relative to reference time."""
    if not stale_after:
        return False

    target = parse_iso_timestamp(stale_after)
    if target is None:
        return False

    if reference_dt is None:
        now = datetime.now(target.tzinfo) if target.tzinfo is not None else datetime.now()
    else:
        now = reference_dt
        if target.tzinfo is not None and now.tzinfo is None:
            now = now.astimezone(target.tzinfo)
        elif target.tzinfo is None and now.tzinfo is not None:
            target = target.replace(tzinfo=now.tzinfo)

    return now >= target

