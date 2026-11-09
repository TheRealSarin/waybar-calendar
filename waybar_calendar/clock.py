import json
import logging
import os
import signal
from datetime import date, datetime
from html import escape

from .grid import GRID_COLUMNS, month_cells, weekday_labels
from .holidays import HolidayStore
from .storage import Store

LOG = logging.getLogger(__name__)

STATE_TIME = "time"
STATE_FULL = "full"
STATES = (STATE_TIME, STATE_FULL)

TITLE_COLOUR = "#58a6ff"
WEEKDAY_COLOUR = "#7d8590"
OUTSIDE_COLOUR = "#484f58"
HOLIDAY_COLOUR = "#d29922"


def read_state(path):
    try:
        with open(path, encoding="utf-8") as handle:
            state = handle.read().strip()
    except OSError:
        return STATE_TIME
    return state if state in STATES else STATE_TIME


def write_state(path, state):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(state)


def next_state(state):
    return STATE_FULL if state == STATE_TIME else STATE_TIME


def waybar_pids():
    pids = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/comm", encoding="utf-8") as handle:
                if handle.read().strip() == "waybar":
                    pids.append(int(name))
        except OSError:
            continue
    return pids


def signal_waybar(number):
    sent = 0
    for pid in waybar_pids():
        try:
            os.kill(pid, signal.SIGRTMIN + number)
        except OSError as error:
            LOG.warning("could not signal waybar %s: %s", pid, error)
            continue
        sent += 1
    if not sent:
        LOG.warning("no running waybar found to refresh")
    return sent


def _cell_markup(day, month, today, holiday, busy):
    text = f"{day.day:2d}"
    if day.month != month:
        return f'<span color="{OUTSIDE_COLOUR}">{text}</span>'
    if busy:
        text = f"<u>{text}</u>"
    if day == today:
        return f'<b><span color="{TITLE_COLOUR}">{text}</span></b>'
    if holiday:
        return f'<span color="{HOLIDAY_COLOUR}">{text}</span>'
    return text


def calendar_markup(config, today, store, holidays):
    month_start = today.replace(day=1)
    lines = [
        f'<b><span color="{TITLE_COLOUR}">{escape(month_start.strftime("%B %Y"))}</span></b>',
        '<span color="{}">{}</span>'.format(
            WEEKDAY_COLOUR, " ".join(weekday_labels(config.first_weekday))
        ),
    ]
    cells = month_cells(month_start, config.first_weekday)
    for start in range(0, len(cells), GRID_COLUMNS):
        week = cells[start : start + GRID_COLUMNS]
        lines.append(
            " ".join(
                _cell_markup(
                    day,
                    month_start.month,
                    today,
                    holidays.title_for(day, config.region),
                    store.has_content(day),
                )
                for day in week
            )
        )
    holiday = holidays.title_for(today, config.region)
    if holiday:
        lines.append("")
        lines.append(f'<span color="{HOLIDAY_COLOUR}">{escape(holiday)}</span>')
    return "<tt>" + "\n".join(lines) + "</tt>"


def render(config, now=None):
    moment = now or datetime.now()
    state = read_state(config.clock_state_file)
    if state == STATE_FULL:
        return {
            "text": moment.strftime(config.clock_alt_format),
            "tooltip": "",
            "class": STATE_FULL,
            "alt": STATE_FULL,
        }
    store = Store.load(config.events_file)
    holidays = HolidayStore.load(config.holiday_cache_file)
    return {
        "text": moment.strftime(config.clock_format),
        "tooltip": calendar_markup(config, moment.date(), store, holidays),
        "class": STATE_TIME,
        "alt": STATE_TIME,
    }


def run_render(config):
    print(json.dumps(render(config)), flush=True)
    return 0


def run_toggle(config):
    state = next_state(read_state(config.clock_state_file))
    write_state(config.clock_state_file, state)
    signal_waybar(config.clock_signal)
    return state


def should_open_panel(config):
    return read_state(config.clock_state_file) == STATE_FULL
