import json
import logging
import os
import time
import urllib.parse
import urllib.request

from .jsonfile import read_json, write_atomic

LOG = logging.getLogger(__name__)

_ALLOWED_SCHEMES = ("http", "https")


def parse_feed(payload):
    if not isinstance(payload, dict):
        raise ValueError("holiday feed must be a JSON object")
    days = {}
    for region, block in payload.items():
        if not isinstance(region, str) or not isinstance(block, dict):
            continue
        for event in block.get("events") or []:
            if not isinstance(event, dict):
                continue
            day = event.get("date")
            title = event.get("title")
            if isinstance(day, str) and isinstance(title, str) and day and title:
                days.setdefault(day, {})[region] = title
    return days


def parse_cache(raw):
    if not isinstance(raw, dict):
        raise ValueError("holiday cache must be a JSON object")
    days = {}
    for day, titles in raw.items():
        if not isinstance(day, str) or not isinstance(titles, dict):
            continue
        usable = {
            region: title
            for region, title in titles.items()
            if isinstance(region, str) and isinstance(title, str) and title
        }
        if usable:
            days[day] = usable
    return days


def fetch_feed(url, timeout):
    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"holiday url must use http or https, got {scheme!r}")
    request = urllib.request.Request(url, headers={"User-Agent": "waybar-calendar"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return parse_feed(payload)


class HolidayStore:
    def __init__(self, path, days=None):
        self.path = path
        self.days = days or {}

    @classmethod
    def load(cls, path):
        raw = read_json(path, "holiday cache")
        if raw is None:
            return cls(path)
        try:
            return cls(path, parse_cache(raw))
        except ValueError as error:
            LOG.warning("ignoring malformed holiday cache %s: %s", path, error)
            return cls(path)

    def is_stale(self, max_age_seconds, now=None):
        if not self.days:
            return True
        try:
            age = (now or time.time()) - os.path.getmtime(self.path)
        except OSError:
            return True
        return age > max_age_seconds

    def title_for(self, day, region):
        titles = self.days.get(day.isoformat())
        if not titles:
            return None
        return titles.get(region)

    def knows_region(self, region):
        return any(region in titles for titles in self.days.values())

    def replace(self, days):
        self.days = days
        write_atomic(self.path, days)
