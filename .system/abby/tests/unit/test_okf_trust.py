"""Unit tests for OKF 0.2 Trust Model, Provenance, and Freshness."""

import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.models.okf import OKFFrontmatter
from abby.models.trust import (
    GenerationRecord,
    ProvenanceSource,
    TrustTier,
    VerificationEvent,
    evaluate_staleness,
    resolve_trust_tier,
)
from abby.services.okf_parser import parse_okf_frontmatter, tokenize_frontmatter


class TestOKFTrustModel(unittest.TestCase):
    """Test suite verifying OKF v0.2 trust tier resolution, staleness, and metadata."""

    def test_trust_tier_constants(self):
        self.assertEqual(TrustTier.UNVERIFIED, "unverified")
        self.assertEqual(TrustTier.MACHINE_CONFIRMED, "machine-confirmed")
        self.assertEqual(TrustTier.HUMAN_REVIEWED, "human-reviewed")
        self.assertEqual(
            TrustTier.ALL,
            ("unverified", "machine-confirmed", "human-reviewed"),
        )

    def test_resolve_trust_tier(self):
        # Empty or absent
        self.assertEqual(resolve_trust_tier([]), TrustTier.UNVERIFIED)
        self.assertEqual(resolve_trust_tier(None), TrustTier.UNVERIFIED)

        # Machine / Agent actors
        self.assertEqual(
            resolve_trust_tier([{"by": "agent:synthesizer", "at": "2026-09-18T10:00:00Z"}]),
            TrustTier.MACHINE_CONFIRMED,
        )
        self.assertEqual(
            resolve_trust_tier([{"by": "process:nightly-sync", "at": "2026-09-18T10:00:00Z"}]),
            TrustTier.MACHINE_CONFIRMED,
        )
        self.assertEqual(
            resolve_trust_tier([{"by": "abby/agent:synthesizer", "at": "2026-09-18T10:00:00Z"}]),
            TrustTier.MACHINE_CONFIRMED,
        )

        # Human actor
        self.assertEqual(
            resolve_trust_tier([{"by": "human:bookian", "at": "2026-09-18T10:00:00Z"}]),
            TrustTier.HUMAN_REVIEWED,
        )

        # Mixed actors (human takes precedence)
        mixed = [
            {"by": "agent:synthesizer", "at": "2026-09-18T10:00:00Z"},
            {"by": "process:ingest", "at": "2026-09-18T11:00:00Z"},
            {"by": "human:alice", "at": "2026-09-18T12:00:00Z"},
        ]
        self.assertEqual(resolve_trust_tier(mixed), TrustTier.HUMAN_REVIEWED)

    def test_evaluate_staleness(self):
        # Absent or empty
        self.assertFalse(evaluate_staleness(None))
        self.assertFalse(evaluate_staleness(""))

        # Future date -> fresh
        future_dt = datetime.now(timezone.utc) + timedelta(days=30)
        self.assertFalse(evaluate_staleness(future_dt.isoformat()))

        # Past date -> stale
        past_dt = datetime.now(timezone.utc) - timedelta(days=30)
        self.assertTrue(evaluate_staleness(past_dt.isoformat()))
        self.assertTrue(evaluate_staleness("2020-01-01T00:00:00Z"))

        # Invalid date format -> fallback False
        self.assertFalse(evaluate_staleness("invalid-date-format"))

    def test_dataclasses_instantiation(self):
        ve = VerificationEvent(by="human:bookian", at="2026-09-18T12:00:00Z")
        self.assertEqual(ve.by, "human:bookian")
        self.assertEqual(ve.at, "2026-09-18T12:00:00Z")

        gr = GenerationRecord(by="abby/agent:synthesizer", at="2026-09-18T10:00:00Z")
        self.assertEqual(gr.by, "abby/agent:synthesizer")
        self.assertEqual(gr.at, "2026-09-18T10:00:00Z")

        src = ProvenanceSource(
            resource="https://example.com/paper.pdf",
            id="paper-1",
            title="A Paper",
            author="Author",
            usage_count=3,
            last_modified="2026-01-01",
        )
        self.assertEqual(src.resource, "https://example.com/paper.pdf")
        self.assertEqual(src.id, "paper-1")

    def test_bare_mapping_normalization_in_tokenizer(self):
        text = (
            "---\n"
            'title: "Bare Mapping Note"\n'
            'verified: { by: "human:alice", at: "2026-06-25T09:00:00Z" }\n'
            "---\n"
            "# Body\n"
        )
        parsed = tokenize_frontmatter(text)
        fm = OKFFrontmatter.from_markdown(text)
        self.assertEqual(len(fm.verified), 1)
        self.assertEqual(fm.verified[0]["by"], "human:alice")
        self.assertEqual(fm.verified[0]["at"], "2026-06-25T09:00:00Z")
        self.assertEqual(fm.trust_tier, TrustTier.HUMAN_REVIEWED)

    def test_block_mapping_parsing(self):
        text = (
            "---\n"
            'title: "Block Verified Note"\n'
            "verified:\n"
            "  - by: agent:synthesizer\n"
            '    at: "2026-09-18T10:00:00Z"\n'
            "  - by: human:bookian\n"
            '    at: "2026-09-18T14:30:00Z"\n'
            "generated:\n"
            "  by: abby/agent:synthesizer\n"
            '  at: "2026-09-18T10:00:00Z"\n'
            'stale_after: "2025-01-01T00:00:00Z"\n'
            "sources:\n"
            "  - id: ong-raft\n"
            '    resource: "https://raft.github.io/raft.pdf"\n'
            '    title: "Raft Paper"\n'
            "---\n"
            "# Content\n"
        )
        fm = OKFFrontmatter.from_markdown(text)
        self.assertEqual(len(fm.verified), 2)
        self.assertEqual(fm.verified[0]["by"], "agent:synthesizer")
        self.assertEqual(fm.verified[1]["by"], "human:bookian")
        self.assertEqual(fm.trust_tier, TrustTier.HUMAN_REVIEWED)
        self.assertTrue(fm.is_stale)
        self.assertIsNotNone(fm.generated)
        self.assertEqual(fm.generated["by"], "abby/agent:synthesizer")
        self.assertEqual(len(fm.sources), 1)
        self.assertEqual(fm.sources[0]["id"], "ong-raft")
        self.assertEqual(fm.sources[0]["resource"], "https://raft.github.io/raft.pdf")

    def test_parse_okf_frontmatter_dict(self):
        text = (
            "---\n"
            'title: "Dict Note"\n'
            'stale_after: "2030-01-01T00:00:00Z"\n'
            "verified:\n"
            "  - by: agent:curator\n"
            '    at: "2026-09-18T10:00:00Z"\n'
            "---\n"
            "# Dict Note\n"
        )
        meta = parse_okf_frontmatter(text, default_title="Dict Note")
        self.assertEqual(meta["title"], "Dict Note")
        self.assertEqual(meta["stale_after"], "2030-01-01T00:00:00Z")
        self.assertEqual(meta["trust_tier"], TrustTier.MACHINE_CONFIRMED)
        self.assertFalse(meta["is_stale"])
        self.assertEqual(len(meta["verified"]), 1)


    def test_inline_yaml_list_with_braces_in_strings(self):
        text = (
            "---\n"
            'title: "Braces Note"\n'
            'sources: [ { resource: "https://example.com/items/{id}", title: "API {Spec}" } ]\n'
            "---\n"
            "# Content\n"
        )
        parsed = tokenize_frontmatter(text)
        self.assertEqual(len(parsed.sources), 1)
        self.assertEqual(parsed.sources[0]["resource"], "https://example.com/items/{id}")
        self.assertEqual(parsed.sources[0]["title"], "API {Spec}")


if __name__ == "__main__":
    unittest.main()
