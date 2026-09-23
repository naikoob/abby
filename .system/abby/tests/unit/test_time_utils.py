"""Unit tests for centralized time utilities (abby.utils.time)."""

import unittest
from datetime import date, datetime, timezone

from abby.utils.time import (
    is_timestamp_stale,
    now_iso,
    now_utc_iso,
    parse_iso_timestamp,
)


class TestTimeUtils(unittest.TestCase):
    def test_now_iso_format(self) -> None:
        val = now_iso()
        self.assertRegex(val, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

    def test_now_utc_iso_format(self) -> None:
        val = now_utc_iso()
        self.assertRegex(val, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_parse_iso_timestamp(self) -> None:
        self.assertIsNone(parse_iso_timestamp(None))
        self.assertIsNone(parse_iso_timestamp(""))
        self.assertIsNone(parse_iso_timestamp("   "))
        self.assertIsNone(parse_iso_timestamp("not-a-date"))

        # Datetime and date pass-through
        dt = datetime(2026, 9, 18, 12, 0, 0)
        self.assertEqual(parse_iso_timestamp(dt), dt)
        d = date(2026, 9, 18)
        self.assertEqual(parse_iso_timestamp(d), datetime(2026, 9, 18, 0, 0, 0))

        # YYYY-MM-DD
        parsed_date = parse_iso_timestamp("2026-09-18")
        self.assertIsNotNone(parsed_date)
        self.assertEqual(parsed_date, datetime(2026, 9, 18, 0, 0, 0))

        # Quoted string
        parsed_quoted = parse_iso_timestamp('"2026-09-18"')
        self.assertEqual(parsed_quoted, datetime(2026, 9, 18, 0, 0, 0))

        # ISO naive
        parsed_naive = parse_iso_timestamp("2026-09-18T14:30:00")
        self.assertEqual(parsed_naive, datetime(2026, 9, 18, 14, 30, 0))

        # ISO with Z
        parsed_utc = parse_iso_timestamp("2026-09-18T14:30:00Z")
        self.assertIsNotNone(parsed_utc)
        self.assertEqual(parsed_utc.tzinfo, timezone.utc)

        # ISO with offset
        parsed_offset = parse_iso_timestamp("2026-09-18T14:30:00+08:00")
        self.assertIsNotNone(parsed_offset)

    def test_is_timestamp_stale(self) -> None:
        self.assertFalse(is_timestamp_stale(None))
        self.assertFalse(is_timestamp_stale(""))
        self.assertFalse(is_timestamp_stale("invalid-date"))

        ref = datetime(2026, 9, 18, 12, 0, 0)

        # Past timestamp is stale
        self.assertTrue(is_timestamp_stale("2026-09-17T12:00:00", reference_dt=ref))

        # Future timestamp is not stale
        self.assertFalse(is_timestamp_stale("2026-09-19T12:00:00", reference_dt=ref))

        # Timezone aware comparison
        ref_utc = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(is_timestamp_stale("2026-09-17T12:00:00Z", reference_dt=ref_utc))
        self.assertFalse(is_timestamp_stale("2026-09-19T12:00:00Z", reference_dt=ref_utc))


if __name__ == "__main__":
    unittest.main()

