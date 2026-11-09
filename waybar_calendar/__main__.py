import argparse
import logging
import sys

from .config import load_config
from .lock import InstanceLock

LOG = logging.getLogger("waybar-calendar")

OPEN_TIMEOUT_SECONDS = 1.0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="waybar-calendar",
        description="Drop-down calendar panel with per-day entries, notes and UK bank holidays",
    )
    parser.add_argument(
        "--toggle",
        action="store_true",
        help="close the panel instead of reporting an error when one is already open",
    )
    parser.add_argument("--config", help="path to a config file")
    parser.add_argument(
        "--list-monitors",
        action="store_true",
        help="print the monitors GTK can see and exit",
    )
    parser.add_argument("--verbose", action="store_true", help="log debug output")

    commands = parser.add_subparsers(dest="command")
    clock = commands.add_parser(
        "clock", help="waybar clock module that gates the panel behind its own state"
    )
    clock.add_argument(
        "action",
        choices=("render", "toggle", "open", "close"),
        help="render prints the module JSON, toggle swaps time and date view, "
        "open shows the panel only while the date view is showing, close hides it",
    )
    return parser


def _print_monitors():
    try:
        from .panel import describe_monitors
    except ImportError as error:
        LOG.error("GTK 3 and gtk-layer-shell GObject bindings are required: %s", error)
        return 1
    for monitor in describe_monitors():
        left, top, width, height = monitor["geometry"]
        print(
            f"{monitor['index']}  {monitor['model']!r}  {monitor['manufacturer']!r}  "
            f"{width}x{height}+{left}+{top}"
        )
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)
    if args.list_monitors:
        return _print_monitors()

    if args.command == "clock":
        return _run_clock(config, args.action)
    if args.toggle and _close_panel(config):
        return 0
    return _open_panel(config)


def _run_clock(config, action):
    from . import clock

    if action == "render":
        return clock.run_render(config)
    if action == "toggle":
        if clock.run_toggle(config) == clock.STATE_TIME:
            _close_panel(config)
        return 0
    if action == "close":
        _close_panel(config)
        return 0
    if not clock.should_open_panel(config):
        return 0
    return _open_panel(config)


def _close_panel(config):
    return InstanceLock(config.lock_file).terminate_running()


def _open_panel(config):
    lock = InstanceLock(config.lock_file)
    if not lock.acquire(timeout=OPEN_TIMEOUT_SECONDS):
        LOG.info("the panel is already open")
        return 0
    try:
        from .panel import run
    except ImportError as error:
        LOG.error("GTK 3 and gtk-layer-shell GObject bindings are required: %s", error)
        return 1
    try:
        return run(config)
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
