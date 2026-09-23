"""Pure cognitive ranking and multi-factor graph centrality scoring for Abby."""

from __future__ import annotations

import math
from typing import Any, Optional

from abby.models.trust import evaluate_staleness

# Lifecycle domain weights (PARA+ hierarchy)
DOMAIN_WEIGHTS: dict[str, float] = {
    "03 - Resources": 1.20,
    "01 - Projects": 1.00,
    "02 - Areas": 1.00,
    "00 - Inbox": 0.80,
    "04 - Archives": 0.35,
}

DEFAULT_DOMAIN_WEIGHT: float = 1.00

# OKF trust tier authority multipliers
TRUST_MULTIPLIERS: dict[str, float] = {
    "human-reviewed": 1.25,
    "machine-confirmed": 1.00,
    "unverified": 0.90,
}

DEFAULT_TRUST_MULTIPLIER: float = 0.90

# Staleness decay
STALENESS_PENALTY: float = 0.60
STALENESS_FRESH: float = 1.00

# Graph centrality parameters
GRAPH_BASE: float = 1.00
GRAPH_COEFFICIENT: float = 0.15
GRAPH_MAX_BACKLINKS: int = 31
GRAPH_MAX_MULTIPLIER: float = 1.75


def compute_domain_multiplier(domain: Optional[str]) -> float:
    """Return the domain relevance multiplier based on PARA+ lifecycle position."""
    if not domain:
        return DEFAULT_DOMAIN_WEIGHT
    return DOMAIN_WEIGHTS.get(domain, DEFAULT_DOMAIN_WEIGHT)


def compute_trust_multiplier(trust_tier: Optional[str]) -> float:
    """Return the trust multiplier based on OKF epistemic authority."""
    if not trust_tier:
        return DEFAULT_TRUST_MULTIPLIER
    return TRUST_MULTIPLIERS.get(trust_tier, DEFAULT_TRUST_MULTIPLIER)


def compute_staleness_multiplier(stale_after: Optional[str]) -> float:
    """Return the freshness multiplier, applying decay if the note has expired."""
    if not stale_after:
        return STALENESS_FRESH
    return STALENESS_PENALTY if evaluate_staleness(stale_after) else STALENESS_FRESH


def compute_graph_multiplier(active_backlinks: Any) -> float:
    """Compute bounded logarithmic inbound link centrality multiplier.

    Formula: 1.0 + 0.15 * log2(1 + min(active_backlinks, 31)), capped at 1.75.
    """
    try:
        b = int(active_backlinks or 0)
    except (ValueError, TypeError):
        b = 0

    if b <= 0:
        return GRAPH_BASE

    capped_b = min(b, GRAPH_MAX_BACKLINKS)
    score = GRAPH_BASE + GRAPH_COEFFICIENT * math.log2(1.0 + capped_b)
    return min(score, GRAPH_MAX_MULTIPLIER)


def compute_cognitive_multiplier(
    domain: Optional[str],
    trust_tier: Optional[str],
    stale_after: Optional[str],
    active_backlinks: Any,
) -> float:
    """Compute the composite cognitive ranking multiplier across all four signals."""
    m_dom = compute_domain_multiplier(domain)
    m_trust = compute_trust_multiplier(trust_tier)
    m_fresh = compute_staleness_multiplier(stale_after)
    m_graph = compute_graph_multiplier(active_backlinks)
    return m_dom * m_trust * m_fresh * m_graph

