import json
import os
import tempfile
import unittest

from waybar_calendar.config import Config, apply_overrides, load_config


class ApplyOverridesTest(unittest.TestCase):
    def test_accepts_known_keys(self):
        config = apply_overrides(Config(), {"region": "scotland", "margin_top": 60})
        self.assertEqual(config.region, "scotland")
        self.assertEqual(config.margin_top, 60)

    def test_ignores_unknown_keys(self):
        self.assertEqual(apply_overrides(Config(), {"colour": "red"}), Config())

    def test_ignores_wrong_types(self):
        self.assertEqual(apply_overrides(Config(), {"margin_top": "sixty"}), Config())

    def test_ignores_booleans_posing_as_numbers(self):
        self.assertEqual(apply_overrides(Config(), {"margin_top": True}), Config())

    def test_promotes_integers_to_floats(self):
        self.assertEqual(apply_overrides(Config(), {"holiday_timeout": 5}).holiday_timeout, 5.0)

    def test_rejects_out_of_range_values(self):
        self.assertEqual(apply_overrides(Config(), {"first_weekday": 7}), Config())
        self.assertEqual(apply_overrides(Config(), {"margin_top": -1}), Config())
        self.assertEqual(apply_overrides(Config(), {"holiday_timeout": 0}), Config())
        self.assertEqual(apply_overrides(Config(), {"region": ""}), Config())

    def test_non_object_root_falls_back_to_defaults(self):
        self.assertEqual(apply_overrides(Config(), ["region"]), Config())


class LoadConfigTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.directory.cleanup()

    def test_missing_file_gives_defaults(self):
        self.assertEqual(load_config(os.path.join(self.directory.name, "none.json")), Config())

    def test_broken_file_gives_defaults(self):
        path = os.path.join(self.directory.name, "config.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{oops")
        self.assertEqual(load_config(path), Config())

    def test_reads_values_from_disk(self):
        path = os.path.join(self.directory.name, "config.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"monitor": "DP-1", "first_weekday": 6}, handle)
        config = load_config(path)
        self.assertEqual(config.monitor, "DP-1")
        self.assertEqual(config.first_weekday, 6)


class PathsTest(unittest.TestCase):
    def test_paths_follow_xdg_overrides(self):
        original = dict(os.environ)
        try:
            os.environ["XDG_DATA_HOME"] = "/tmp/share"
            os.environ["XDG_CACHE_HOME"] = "/tmp/cache"
            os.environ["XDG_RUNTIME_DIR"] = "/tmp/run"
            config = Config()
            self.assertEqual(config.events_file, "/tmp/share/waybar-calendar/events.json")
            self.assertEqual(config.holiday_cache_file, "/tmp/cache/waybar-calendar/holidays.json")
            self.assertEqual(config.lock_file, "/tmp/run/waybar-calendar/panel.lock")
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_holiday_age_is_in_seconds(self):
        self.assertEqual(Config(holiday_max_age_days=2).holiday_max_age_seconds, 172800)
