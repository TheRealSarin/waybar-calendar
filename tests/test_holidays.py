import json
import os
import tempfile
import time
import unittest
from datetime import date

from waybar_calendar.holidays import HolidayStore, fetch_feed, parse_feed

FEED = {
    "england-and-wales": {
        "division": "england-and-wales",
        "events": [
            {"title": "Christmas Day", "date": "2026-12-25", "bunting": True},
            {"title": "Boxing Day", "date": "2026-12-28", "bunting": True},
        ],
    },
    "scotland": {
        "division": "scotland",
        "events": [
            {"title": "St Andrew's Day", "date": "2026-11-30", "bunting": True},
            {"title": "Christmas Day", "date": "2026-12-25", "bunting": True},
        ],
    },
}


class ParseFeedTest(unittest.TestCase):
    def test_groups_titles_by_date_and_region(self):
        parsed = parse_feed(FEED)
        self.assertEqual(
            parsed["2026-12-25"],
            {"england-and-wales": "Christmas Day", "scotland": "Christmas Day"},
        )
        self.assertEqual(parsed["2026-11-30"], {"scotland": "St Andrew's Day"})

    def test_rejects_non_object_payload(self):
        with self.assertRaises(ValueError):
            parse_feed([])

    def test_skips_malformed_events(self):
        parsed = parse_feed(
            {
                "england-and-wales": {
                    "events": [
                        {"title": "Good", "date": "2026-01-01"},
                        {"title": "No date"},
                        {"date": "2026-01-02"},
                        {"title": "", "date": "2026-01-03"},
                        "nonsense",
                    ]
                },
                "broken": "not an object",
            }
        )
        self.assertEqual(list(parsed), ["2026-01-01"])


class FetchFeedTest(unittest.TestCase):
    def test_rejects_non_http_urls(self):
        with self.assertRaises(ValueError):
            fetch_feed("file:///etc/passwd", 1)


class HolidayStoreTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "holidays.json")

    def tearDown(self):
        self.directory.cleanup()

    def test_missing_cache_is_stale(self):
        store = HolidayStore.load(self.path)
        self.assertTrue(store.is_stale(3600))
        self.assertIsNone(store.title_for(date(2026, 12, 25), "england-and-wales"))

    def test_replace_writes_cache_that_reloads(self):
        store = HolidayStore.load(self.path)
        store.replace(parse_feed(FEED))
        reloaded = HolidayStore.load(self.path)
        self.assertEqual(
            reloaded.title_for(date(2026, 12, 25), "england-and-wales"), "Christmas Day"
        )
        self.assertFalse(reloaded.is_stale(3600))

    def test_fresh_cache_goes_stale_once_old(self):
        store = HolidayStore.load(self.path)
        store.replace(parse_feed(FEED))
        self.assertTrue(store.is_stale(3600, now=time.time() + 7200))

    def test_other_regions_holidays_are_not_shown(self):
        store = HolidayStore(self.path, parse_feed(FEED))
        self.assertIsNone(store.title_for(date(2026, 11, 30), "england-and-wales"))
        self.assertEqual(store.title_for(date(2026, 11, 30), "scotland"), "St Andrew's Day")

    def test_knows_region(self):
        store = HolidayStore(self.path, parse_feed(FEED))
        self.assertTrue(store.knows_region("scotland"))
        self.assertFalse(store.knows_region("isle-of-man"))

    def test_corrupt_cache_is_reported_and_ignored(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{nope")
        with self.assertLogs("waybar_calendar.jsonfile", level="WARNING"):
            self.assertEqual(HolidayStore.load(self.path).days, {})

    def test_malformed_cache_is_reported_and_ignored(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump([1, 2, 3], handle)
        with self.assertLogs("waybar_calendar.holidays", level="WARNING"):
            self.assertEqual(HolidayStore.load(self.path).days, {})


if __name__ == "__main__":
    unittest.main()
