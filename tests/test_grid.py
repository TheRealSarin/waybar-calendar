import unittest
from datetime import date

from waybar_calendar.grid import CELL_COUNT, month_cells, shift_month, weekday_labels


class WeekdayLabelsTest(unittest.TestCase):
    def test_monday_first(self):
        self.assertEqual(weekday_labels(0), ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"])

    def test_sunday_first(self):
        self.assertEqual(weekday_labels(6), ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"])


class MonthCellsTest(unittest.TestCase):
    def test_grid_is_always_full(self):
        self.assertEqual(len(month_cells(date(2026, 11, 1), 0)), CELL_COUNT)

    def test_month_starting_on_sunday_with_monday_first(self):
        cells = month_cells(date(2026, 11, 1), 0)
        self.assertEqual(cells[0], date(2026, 10, 26))
        self.assertEqual(cells[6], date(2026, 11, 1))

    def test_month_starting_on_sunday_with_sunday_first(self):
        cells = month_cells(date(2026, 11, 1), 6)
        self.assertEqual(cells[0], date(2026, 11, 1))

    def test_cells_are_consecutive_days(self):
        cells = month_cells(date(2026, 2, 1), 0)
        for earlier, later in zip(cells, cells[1:]):
            self.assertEqual((later - earlier).days, 1)

    def test_leap_year_february(self):
        cells = month_cells(date(2028, 2, 1), 0)
        self.assertIn(date(2028, 2, 29), cells)


class ShiftMonthTest(unittest.TestCase):
    def test_forward_over_year_boundary(self):
        self.assertEqual(shift_month(date(2026, 12, 1), 1), date(2027, 1, 1))

    def test_backward_over_year_boundary(self):
        self.assertEqual(shift_month(date(2026, 1, 1), -1), date(2025, 12, 1))

    def test_large_jumps(self):
        self.assertEqual(shift_month(date(2026, 6, 1), 18), date(2027, 12, 1))
        self.assertEqual(shift_month(date(2026, 6, 1), -18), date(2024, 12, 1))
