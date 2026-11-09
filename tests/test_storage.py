import json
import os
import tempfile
import unittest
from datetime import date

from waybar_calendar.storage import Event, Store, normalise_time


class NormaliseTimeTest(unittest.TestCase):
    def test_pads_single_digit_hours(self):
        self.assertEqual(normalise_time("9:05"), "09:05")

    def test_keeps_full_times(self):
        self.assertEqual(normalise_time("23:59"), "23:59")

    def test_blank_means_all_day(self):
        self.assertEqual(normalise_time("  "), "")
        self.assertEqual(normalise_time(None), "")

    def test_rejects_nonsense(self):
        for value in ("tomorrow", "9", "9:5", "24:00", "12:60", "-1:00"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalise_time(value)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "nested", "events.json")
        self.store = Store.load(self.path)
        self.day = date(2026, 11, 9)

    def tearDown(self):
        self.directory.cleanup()

    def test_missing_file_starts_empty(self):
        self.assertEqual(self.store.events(self.day), [])
        self.assertEqual(self.store.note(self.day), "")
        self.assertFalse(self.store.has_content(self.day))

    def test_add_event_persists_and_survives_reload(self):
        self.store.add_event(self.day, "9:30", "  Dentist  ")
        reloaded = Store.load(self.path)
        self.assertEqual(reloaded.events(self.day), [Event(time="09:30", title="Dentist")])
        self.assertTrue(reloaded.has_content(self.day))

    def test_events_sort_all_day_first_then_by_clock(self):
        self.store.add_event(self.day, "18:00", "Gym")
        self.store.add_event(self.day, "", "Bin day")
        self.store.add_event(self.day, "08:15", "Standup")
        self.assertEqual(
            [event.title for event in self.store.events(self.day)],
            ["Bin day", "Standup", "Gym"],
        )

    def test_add_event_rejects_blank_title(self):
        with self.assertRaises(ValueError):
            self.store.add_event(self.day, "09:00", "   ")
        self.assertEqual(self.store.events(self.day), [])

    def test_add_event_rejects_bad_time_without_storing(self):
        with self.assertRaises(ValueError):
            self.store.add_event(self.day, "half nine", "Dentist")
        self.assertEqual(self.store.events(self.day), [])

    def test_remove_event(self):
        event = self.store.add_event(self.day, "09:00", "Dentist")
        self.assertTrue(self.store.remove_event(self.day, event))
        self.assertFalse(self.store.remove_event(self.day, event))
        self.assertEqual(Store.load(self.path).events(self.day), [])

    def test_notes_round_trip(self):
        self.store.set_note(self.day, "ring the garage")
        self.assertEqual(Store.load(self.path).note(self.day), "ring the garage")

    def test_empty_days_are_pruned_from_disk(self):
        self.store.set_note(self.day, "temporary")
        self.store.set_note(self.day, "   ")
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {})

    def test_corrupt_file_is_reported_and_ignored(self):
        broken = os.path.join(self.directory.name, "broken.json")
        with open(broken, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        with self.assertLogs("waybar_calendar.jsonfile", level="WARNING"):
            store = Store.load(broken)
        self.assertEqual(store.events(self.day), [])

    def test_unusable_entries_are_dropped_on_load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "2026-11-09": {
                        "events": [
                            {"title": "Keep me", "time": "7:00"},
                            {"title": "", "time": "08:00"},
                            {"time": "09:00"},
                            "nonsense",
                            {"title": "Bad time", "time": "late"},
                        ],
                        "note": 5,
                    },
                    "2026-11-10": {"events": [], "note": ""},
                    "broken": "not an object",
                },
                handle,
            )
        store = Store.load(self.path)
        self.assertEqual(
            store.events(self.day),
            [Event(time="", title="Bad time"), Event(time="07:00", title="Keep me")],
        )
        self.assertEqual(store.note(self.day), "")
        self.assertFalse(store.has_content(date(2026, 11, 10)))


if __name__ == "__main__":
    unittest.main()
