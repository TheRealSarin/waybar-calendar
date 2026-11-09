import os
import tempfile
import unittest
from datetime import date, datetime

from waybar_calendar import clock
from waybar_calendar.config import Config
from waybar_calendar.holidays import HolidayStore, parse_feed
from waybar_calendar.storage import Store

FEED = {
    "england-and-wales": {
        "events": [{"title": "Christmas Day", "date": "2026-12-25"}],
    },
    "scotland": {
        "events": [{"title": "St Andrew's Day", "date": "2026-11-30"}],
    },
}


class StateTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "nested", "clock-state")

    def tearDown(self):
        self.directory.cleanup()

    def test_missing_state_is_time_only(self):
        self.assertEqual(clock.read_state(self.path), clock.STATE_TIME)

    def test_round_trip(self):
        clock.write_state(self.path, clock.STATE_FULL)
        self.assertEqual(clock.read_state(self.path), clock.STATE_FULL)

    def test_unknown_state_falls_back_to_time_only(self):
        clock.write_state(self.path, clock.STATE_FULL)
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("sideways")
        self.assertEqual(clock.read_state(self.path), clock.STATE_TIME)

    def test_next_state_alternates(self):
        self.assertEqual(clock.next_state(clock.STATE_TIME), clock.STATE_FULL)
        self.assertEqual(clock.next_state(clock.STATE_FULL), clock.STATE_TIME)


class MarkupTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = Config()
        self.store = Store(os.path.join(self.directory.name, "events.json"))
        self.holidays = HolidayStore(
            os.path.join(self.directory.name, "holidays.json"), parse_feed(FEED)
        )

    def tearDown(self):
        self.directory.cleanup()

    def markup(self, today):
        return clock.calendar_markup(self.config, today, self.store, self.holidays)

    def test_header_names_the_month(self):
        self.assertIn("November 2026", self.markup(date(2026, 11, 9)))

    def test_today_is_highlighted(self):
        self.assertIn(f'<b><span color="{clock.TITLE_COLOUR}"> 9</span></b>', self.markup(date(2026, 11, 9)))

    def test_days_outside_the_month_are_dimmed(self):
        self.assertIn(f'<span color="{clock.OUTSIDE_COLOUR}">26</span>', self.markup(date(2026, 11, 9)))

    def test_holidays_in_the_chosen_region_are_marked(self):
        markup = self.markup(date(2026, 12, 1))
        self.assertIn(f'<span color="{clock.HOLIDAY_COLOUR}">25</span>', markup)

    def test_other_regions_holidays_are_not_marked(self):
        markup = self.markup(date(2026, 11, 9))
        self.assertNotIn(f'<span color="{clock.HOLIDAY_COLOUR}">30</span>', markup)

    def test_todays_holiday_is_named_underneath(self):
        self.assertIn("Christmas Day", self.markup(date(2026, 12, 25)))

    def test_days_with_entries_are_underlined(self):
        self.store.add_event(date(2026, 11, 12), "09:00", "Dentist")
        self.assertIn("<u>12</u>", self.markup(date(2026, 11, 9)))

    def test_every_week_has_seven_days(self):
        rows = self.markup(date(2026, 11, 9)).split("\n")
        self.assertEqual(len(rows), 8)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original = dict(os.environ)
        os.environ["XDG_RUNTIME_DIR"] = self.directory.name
        os.environ["XDG_DATA_HOME"] = self.directory.name
        os.environ["XDG_CACHE_HOME"] = self.directory.name
        self.config = Config()
        self.moment = datetime(2026, 11, 9, 20, 15)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original)
        self.directory.cleanup()

    def test_time_only_state_shows_the_calendar_preview(self):
        payload = clock.render(self.config, self.moment)
        self.assertEqual(payload["text"], "20:15")
        self.assertEqual(payload["class"], clock.STATE_TIME)
        self.assertIn("November 2026", payload["tooltip"])

    def test_date_state_drops_the_preview(self):
        clock.write_state(self.config.clock_state_file, clock.STATE_FULL)
        payload = clock.render(self.config, self.moment)
        self.assertEqual(payload["text"], "Mon 09 Nov  20:15")
        self.assertEqual(payload["class"], clock.STATE_FULL)
        self.assertEqual(payload["tooltip"], "")

    def test_toggle_reports_the_new_state(self):
        self.assertEqual(clock.run_toggle(self.config), clock.STATE_FULL)
        self.assertEqual(clock.run_toggle(self.config), clock.STATE_TIME)

    def test_panel_only_opens_from_the_date_state(self):
        self.assertFalse(clock.should_open_panel(self.config))
        clock.write_state(self.config.clock_state_file, clock.STATE_FULL)
        self.assertTrue(clock.should_open_panel(self.config))


if __name__ == "__main__":
    unittest.main()
