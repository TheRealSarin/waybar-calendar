import calendar
from datetime import date

GRID_COLUMNS = 7
GRID_ROWS = 6
CELL_COUNT = GRID_COLUMNS * GRID_ROWS


def weekday_labels(first_weekday):
    names = list(calendar.day_abbr)
    rotated = names[first_weekday:] + names[:first_weekday]
    return [name[:2] for name in rotated]


def month_cells(month_start, first_weekday, count=CELL_COUNT):
    offset = (month_start.weekday() - first_weekday) % GRID_COLUMNS
    first_cell = month_start.toordinal() - offset
    return [date.fromordinal(first_cell + index) for index in range(count)]


def shift_month(month_start, delta):
    index = month_start.year * 12 + month_start.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)
