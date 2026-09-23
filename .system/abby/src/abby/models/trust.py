"""Open Knowledge Format (OKF v0.2) Trust, Provenance, and Freshness models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from abby.utils.time import is_timestamp_stale
from abby.utils.yaml import unescape_yaml_string

__all__ = [
    "GenerationRecord",
    "ProvenanceSource",
    "TrustTier",
    "VerificationEvent",
    "VerifyResult",
    "evaluate_staleness",
    "parse_actor",
    "resolve_trust_tier",
]


class TrustTier:
    """OKF v0.2 Trust Tier enumeration constants."""

    UNVERIFIED = "unverified"
    MACHINE_CONFIRMED = "machine-confirmed"
    HUMAN_REVIEWED = "human-reviewed"

    ALL = (UNVERIFIED, MACHINE_CONFIRMED, HUMAN_REVIEWED)


def parse_actor(actor: str) -> Optional[tuple[str, str]]:
    """Parse OKF v0.2 actor string into (actor_type, actor_id).

    Supports:
      - human:<id>
      - agent:<id>
      - tool:<id>
      - process:<id>
      - <producer>/<id>
    """
    if not actor or not isinstance(actor, str):
        return None
    clean = actor.strip()
    if any(c in clean for c in " \t\r\n"):
        return None
    for prefix in ("human:", "agent:", "tool:", "process:"):
        if clean.startswith(prefix) and len(clean) > len(prefix):
            return prefix[:-1], clean[len(prefix):]
    if "/" in clean:
        parts = clean.split("/", 1)
        if parts[0] and parts[1]:
            return parts[0], parts[1]
    return None


def resolve_trust_tier(verified: Optional[list[dict[str, str]]]) -> str:
    """Dynamically resolve OKF v0.2 trust tier from verified records."""
    if not verified:
        return TrustTier.UNVERIFIED
    for entry in verified:
        actor = str(entry.get("by", "")).strip()
        if actor.startswith("human:"):
            return TrustTier.HUMAN_REVIEWED
    return TrustTier.MACHINE_CONFIRMED


def evaluate_staleness(stale_after: Optional[str]) -> bool:
    """Dynamically compute whether the note has passed its stale_after instant."""
    if not stale_after or not str(stale_after).strip():
        return False
    cleaned = unescape_yaml_string(str(stale_after)).strip()
    return is_timestamp_stale(cleaned)


@dataclass
class VerificationEvent:
    """Represents an attestation confirming note contents against its sources."""

    by: str
    at: str


@dataclass
class GenerationRecord:
    """Represents the origin of the note's creation or last major revision."""

    by: str
    at: Optional[str] = None


@dataclass
class ProvenanceSource:
    """Represents an attributed external or internal source."""

    resource: str
    id: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    usage_count: Optional[int] = None
    last_modified: Optional[str] = None


@dataclass
class VerifyResult:
    """Represents the outcome of recording a verification event on a note."""

    path: str
    actor: str
    timestamp: str
    trust_tier: str
    old_trust_tier: str = "unverified"
    dry_run: bool = False
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "trust_tier": self.trust_tier,
            "dry_run": self.dry_run,
        }
