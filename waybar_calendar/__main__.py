import argparse
import logging
import sys

from .config import load_config
from .lock import InstanceLock

LOG = logging.getLogger("waybar-calendar")


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
    lock = InstanceLock(config.lock_file)
    if not lock.acquire():
        if args.toggle and lock.terminate_running():
            return 0
        LOG.error("a panel is already running and could not be stopped")
        return 1
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
