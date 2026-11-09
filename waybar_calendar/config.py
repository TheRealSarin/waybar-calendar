import json
import logging
import os
from dataclasses import dataclass, replace

LOG = logging.getLogger(__name__)

APP_NAME = "waybar-calendar"
DEFAULT_HOLIDAY_URL = "https://www.gov.uk/bank-holidays.json"


def _app_dir(variable, fallback):
    root = os.environ.get(variable) or os.path.expanduser(fallback)
    return os.path.join(root, APP_NAME)


def config_dir():
    return _app_dir("XDG_CONFIG_HOME", "~/.config")


def data_dir():
    return _app_dir("XDG_DATA_HOME", "~/.local/share")


def cache_dir():
    return _app_dir("XDG_CACHE_HOME", "~/.cache")


def runtime_dir():
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", APP_NAME)


@dataclass(frozen=True)
class Config:
    region: str = "england-and-wales"
    monitor: str = ""
    monitor_index: int = -1
    margin_top: int = 46
    first_weekday: int = 0
    holiday_url: str = DEFAULT_HOLIDAY_URL
    holiday_max_age_days: int = 7
    holiday_timeout: float = 10.0

    @property
    def events_file(self):
        return os.path.join(data_dir(), "events.json")

    @property
    def holiday_cache_file(self):
        return os.path.join(cache_dir(), "holidays.json")

    @property
    def lock_file(self):
        return os.path.join(runtime_dir(), "panel.lock")

    @property
    def holiday_max_age_seconds(self):
        return self.holiday_max_age_days * 86400


_FIELD_TYPES = {
    "region": str,
    "monitor": str,
    "monitor_index": int,
    "margin_top": int,
    "first_weekday": int,
    "holiday_url": str,
    "holiday_max_age_days": int,
    "holiday_timeout": float,
}


def _coerce(key, value):
    expected = _FIELD_TYPES[key]
    if isinstance(value, bool):
        return None
    if expected is float and isinstance(value, int):
        value = float(value)
    if not isinstance(value, expected):
        return None
    if key == "first_weekday" and not 0 <= value <= 6:
        return None
    if key in ("margin_top", "holiday_max_age_days") and value < 0:
        return None
    if key == "monitor_index" and value < -1:
        return None
    if key == "holiday_timeout" and not 0 < value <= 120:
        return None
    if key == "region" and not value:
        return None
    return value


def apply_overrides(base, raw):
    if not isinstance(raw, dict):
        LOG.warning("config root is not an object, using defaults")
        return base
    accepted = {}
    for key, value in raw.items():
        if key not in _FIELD_TYPES:
            LOG.warning("ignoring unknown config key %r", key)
            continue
        coerced = _coerce(key, value)
        if coerced is None:
            LOG.warning("ignoring invalid value for config key %r", key)
            continue
        accepted[key] = coerced
    return replace(base, **accepted)


def load_config(path=None):
    target = path or os.path.join(config_dir(), "config.json")
    try:
        with open(target, encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return Config()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        LOG.warning("ignoring unreadable config %s: %s", target, error)
        return Config()
    return apply_overrides(Config(), raw)
