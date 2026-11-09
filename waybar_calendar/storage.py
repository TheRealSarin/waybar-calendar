import logging
import re
from dataclasses import dataclass

from .jsonfile import read_json, write_atomic

LOG = logging.getLogger(__name__)

_TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")


def normalise_time(raw):
    text = (raw or "").strip()
    if not text:
        return ""
    match = _TIME_PATTERN.match(text)
    if match is None:
        raise ValueError("time must be written as HH:MM")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError("time must be a real clock time")
    return f"{hour:02d}:{minute:02d}"


def day_key(day):
    return day.isoformat()


@dataclass
class Event:
    time: str
    title: str

    def as_dict(self):
        return {"time": self.time, "title": self.title}

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict):
            return None
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        time_value = raw.get("time")
        if not isinstance(time_value, str):
            time_value = ""
        try:
            time_value = normalise_time(time_value)
        except ValueError:
            time_value = ""
        return cls(time=time_value, title=title.strip())


@dataclass
class Day:
    events: list
    note: str

    def is_empty(self):
        return not self.events and not self.note.strip()


def _parse_days(raw):
    days = {}
    if not isinstance(raw, dict):
        LOG.warning("event store root is not an object, starting empty")
        return days
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        events = []
        for item in value.get("events") or []:
            event = Event.from_dict(item)
            if event is not None:
                events.append(event)
        note = value.get("note")
        day = Day(events=events, note=note if isinstance(note, str) else "")
        if not day.is_empty():
            days[key] = day
    return days


class Store:
    def __init__(self, path, days=None):
        self.path = path
        self._days = days or {}

    @classmethod
    def load(cls, path):
        raw = read_json(path, "event store")
        if raw is None:
            return cls(path)
        return cls(path, _parse_days(raw))

    def events(self, day):
        stored = self._days.get(day_key(day))
        if stored is None:
            return []
        return sorted(stored.events, key=lambda event: event.time)

    def note(self, day):
        stored = self._days.get(day_key(day))
        return stored.note if stored else ""

    def has_content(self, day):
        stored = self._days.get(day_key(day))
        return stored is not None and not stored.is_empty()

    def add_event(self, day, time_text, title):
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("an entry needs a title")
        event = Event(time=normalise_time(time_text), title=cleaned)
        self._entry(day).events.append(event)
        self.save()
        return event

    def remove_event(self, day, event):
        stored = self._days.get(day_key(day))
        if stored is None or event not in stored.events:
            return False
        stored.events.remove(event)
        self.save()
        return True

    def set_note(self, day, text):
        self._entry(day).note = text
        self.save()

    def save(self):
        self._prune()
        payload = {
            key: {"events": [event.as_dict() for event in day.events], "note": day.note}
            for key, day in self._days.items()
        }
        write_atomic(self.path, payload)

    def _entry(self, day):
        return self._days.setdefault(day_key(day), Day(events=[], note=""))

    def _prune(self):
        for key in [key for key, day in self._days.items() if day.is_empty()]:
            del self._days[key]
