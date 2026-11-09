import logging
import os
import signal
import threading
from datetime import date

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gdk, GLib, Gtk, GtkLayerShell  # noqa: E402

from .grid import CELL_COUNT, GRID_COLUMNS, month_cells, shift_month, weekday_labels  # noqa: E402
from .holidays import HolidayStore, fetch_feed  # noqa: E402
from .storage import Store  # noqa: E402

LOG = logging.getLogger(__name__)

NAMESPACE = "calendar-panel"
NOTE_SAVE_DELAY_MS = 400
STYLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")


def describe_monitors():
    display = Gdk.Display.get_default()
    if display is None:
        return []
    described = []
    for index in range(display.get_n_monitors()):
        monitor = display.get_monitor(index)
        geometry = monitor.get_geometry()
        described.append(
            {
                "index": index,
                "model": monitor.get_model() or "",
                "manufacturer": monitor.get_manufacturer() or "",
                "geometry": (geometry.x, geometry.y, geometry.width, geometry.height),
            }
        )
    return described


def find_monitor(index, model):
    display = Gdk.Display.get_default()
    if display is None:
        return None
    count = display.get_n_monitors()
    if index >= 0:
        if index < count:
            return display.get_monitor(index)
        LOG.warning("monitor_index %s is out of range, using the compositor default", index)
        return None
    if not model:
        return None
    for position in range(count):
        monitor = display.get_monitor(position)
        if monitor.get_model() == model:
            return monitor
    LOG.warning(
        "no monitor reports the model %r, using the compositor default; "
        "run with --list-monitors to see the names GTK knows",
        model,
    )
    return None


class Panel(Gtk.Window):
    def __init__(self, config, store, holidays):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.config = config
        self.store = store
        self.holidays = holidays
        self.today = date.today()
        self.selected = self.today
        self.month_start = self.today.replace(day=1)
        self.note_timer = None
        self.cells = []

        self._init_layer_shell()
        self._load_style()
        self._build()
        self._refresh_month()
        self._refresh_day()
        self._refresh_holidays_if_stale()
        self._warn_about_unknown_region()

    def _init_layer_shell(self):
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, NAMESPACE)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, self.config.margin_top)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        monitor = find_monitor(self.config.monitor_index, self.config.monitor)
        if monitor is not None:
            GtkLayerShell.set_monitor(self, monitor)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.set_app_paintable(True)

    def _load_style(self):
        provider = Gtk.CssProvider()
        try:
            provider.load_from_path(STYLE_FILE)
        except GLib.Error as error:
            LOG.error("could not load %s: %s", STYLE_FILE, error.message)
            return
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build(self):
        self.connect("destroy", self._on_destroy)
        self.connect("key-press-event", self._on_key_press)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        root.get_style_context().add_class("panel")
        root.set_border_width(16)
        self.add(root)

        root.pack_start(self._build_month_side(), False, False, 0)
        root.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)
        root.pack_start(self._build_day_side(), True, True, 0)
        self.show_all()
        self.title_input.grab_focus()

    def _build_month_side(self):
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header.pack_start(self._nav_button("‹", self._on_previous_month), False, False, 0)
        self.month_label = Gtk.Label()
        self.month_label.get_style_context().add_class("title")
        header.pack_start(self.month_label, True, True, 0)
        header.pack_start(self._nav_button("›", self._on_next_month), False, False, 0)
        header.pack_start(self._nav_button("today", self._on_today), False, False, 0)
        side.pack_start(header, False, False, 0)

        grid = Gtk.Grid(column_homogeneous=True, row_spacing=2, column_spacing=2)
        for column, name in enumerate(weekday_labels(self.config.first_weekday)):
            label = Gtk.Label(label=name)
            label.get_style_context().add_class("dow")
            grid.attach(label, column, 0, 1, 1)

        for index in range(CELL_COUNT):
            button = Gtk.Button()
            button.get_style_context().add_class("day")
            button.connect("clicked", self._on_select_day, index)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            number = Gtk.Label()
            number.get_style_context().add_class("day-number")
            marker = Gtk.Label(label="•")
            box.pack_start(number, False, False, 0)
            box.pack_start(marker, False, False, 0)
            button.add(box)
            grid.attach(button, index % GRID_COLUMNS, index // GRID_COLUMNS + 1, 1, 1)
            self.cells.append({"button": button, "number": number, "marker": marker, "date": None})

        side.pack_start(grid, False, False, 0)
        return side

    def _build_day_side(self):
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        side.set_size_request(320, -1)

        self.day_label = Gtk.Label(xalign=0)
        self.day_label.get_style_context().add_class("title")
        side.pack_start(self.day_label, False, False, 0)

        self.holiday_label = Gtk.Label(xalign=0)
        self.holiday_label.get_style_context().add_class("holiday-chip")
        side.pack_start(self.holiday_label, False, False, 0)

        self.entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_size_request(-1, 120)
        scroller.add(self.entry_box)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.get_style_context().add_class("card")
        card.set_border_width(8)
        card.pack_start(scroller, True, True, 0)
        side.pack_start(card, False, False, 0)

        add_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.time_input = Gtk.Entry(placeholder_text="09:00")
        self.time_input.set_width_chars(5)
        self.time_input.set_max_width_chars(5)
        self.time_input.connect("activate", self._on_add_entry)
        self.title_input = Gtk.Entry(placeholder_text="Book something...")
        self.title_input.connect("activate", self._on_add_entry)
        add_button = Gtk.Button(label="+")
        add_button.get_style_context().add_class("add")
        add_button.connect("clicked", self._on_add_entry)
        add_row.pack_start(self.time_input, False, False, 0)
        add_row.pack_start(self.title_input, True, True, 0)
        add_row.pack_start(add_button, False, False, 0)
        side.pack_start(add_row, False, False, 0)

        notes_label = Gtk.Label(label="notes", xalign=0)
        notes_label.get_style_context().add_class("sub")
        side.pack_start(notes_label, False, False, 0)

        self.notes_view = Gtk.TextView()
        self.notes_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.notes_view.get_buffer().connect("changed", self._on_note_changed)
        notes_scroller = Gtk.ScrolledWindow()
        notes_scroller.get_style_context().add_class("notes")
        notes_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        notes_scroller.add(self.notes_view)
        side.pack_start(notes_scroller, True, True, 0)
        return side

    def _nav_button(self, label, handler):
        button = Gtk.Button(label=label)
        button.get_style_context().add_class("nav")
        button.connect("clicked", handler)
        return button

    def _refresh_month(self):
        self.month_label.set_text(self.month_start.strftime("%B %Y"))
        for cell, day in zip(self.cells, month_cells(self.month_start, self.config.first_weekday)):
            cell["date"] = day
            cell["number"].set_text(str(day.day))

            button_style = cell["button"].get_style_context()
            number_style = cell["number"].get_style_context()
            for name in ("outside", "today", "holiday"):
                number_style.remove_class(name)
            button_style.remove_class("selected")

            if day.month != self.month_start.month:
                number_style.add_class("outside")
            elif self.holidays.title_for(day, self.config.region):
                number_style.add_class("holiday")
            if day == self.today:
                number_style.add_class("today")
            if day == self.selected:
                button_style.add_class("selected")

            marker_style = cell["marker"].get_style_context()
            marker_style.remove_class("marker")
            marker_style.remove_class("marker-hidden")
            marker_style.add_class("marker" if self.store.has_content(day) else "marker-hidden")

    def _refresh_day(self):
        self.day_label.set_text(self.selected.strftime("%a %d %B"))
        holiday = self.holidays.title_for(self.selected, self.config.region)
        self.holiday_label.set_text(holiday or "")
        self.holiday_label.set_visible(bool(holiday))

        for child in self.entry_box.get_children():
            self.entry_box.remove(child)
        events = self.store.events(self.selected)
        if not events:
            placeholder = Gtk.Label(label="nothing booked", xalign=0)
            placeholder.get_style_context().add_class("placeholder")
            self.entry_box.pack_start(placeholder, False, False, 0)
        for event in events:
            self.entry_box.pack_start(self._build_entry_row(event), False, False, 0)
        self.entry_box.show_all()

        buffer = self.notes_view.get_buffer()
        buffer.handler_block_by_func(self._on_note_changed)
        buffer.set_text(self.store.note(self.selected))
        buffer.handler_unblock_by_func(self._on_note_changed)

    def _build_entry_row(self, event):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        time_label = Gtk.Label(label=event.time or "all day", xalign=0)
        time_label.get_style_context().add_class("entry-time")
        time_label.set_width_chars(7)
        title_label = Gtk.Label(label=event.title, xalign=0)
        title_label.get_style_context().add_class("entry-title")
        title_label.set_line_wrap(True)
        remove = Gtk.Button(label="×")
        remove.get_style_context().add_class("remove")
        remove.connect("clicked", self._on_remove_entry, event)
        row.pack_start(time_label, False, False, 0)
        row.pack_start(title_label, True, True, 0)
        row.pack_start(remove, False, False, 0)
        return row

    def _warn_about_unknown_region(self):
        if self.holidays.days and not self.holidays.knows_region(self.config.region):
            LOG.warning(
                "the holiday feed has no division called %r, so no holidays will be marked",
                self.config.region,
            )

    def _refresh_holidays_if_stale(self):
        if not self.holidays.is_stale(self.config.holiday_max_age_seconds):
            return
        worker = threading.Thread(target=self._holiday_worker, daemon=True)
        worker.start()

    def _holiday_worker(self):
        try:
            days = fetch_feed(self.config.holiday_url, self.config.holiday_timeout)
        except (OSError, ValueError) as error:
            LOG.warning("could not refresh holidays: %s", error)
            return
        GLib.idle_add(self._apply_holidays, days)

    def _apply_holidays(self, days):
        try:
            self.holidays.replace(days)
        except OSError as error:
            LOG.warning("could not cache holidays: %s", error)
        self._warn_about_unknown_region()
        self._refresh_month()
        self._refresh_day()
        return False

    def _on_previous_month(self, _button):
        self.month_start = shift_month(self.month_start, -1)
        self._refresh_month()

    def _on_next_month(self, _button):
        self.month_start = shift_month(self.month_start, 1)
        self._refresh_month()

    def _on_today(self, _button):
        self.today = date.today()
        self.selected = self.today
        self.month_start = self.today.replace(day=1)
        self._refresh_month()
        self._refresh_day()

    def _on_select_day(self, _button, index):
        day = self.cells[index]["date"]
        self.selected = day
        if day.month != self.month_start.month:
            self.month_start = day.replace(day=1)
        self._refresh_month()
        self._refresh_day()

    def _on_add_entry(self, _widget):
        style = self.time_input.get_style_context()
        style.remove_class("invalid")
        try:
            self.store.add_event(
                self.selected, self.time_input.get_text(), self.title_input.get_text()
            )
        except ValueError as error:
            LOG.info("rejected entry: %s", error)
            style.add_class("invalid")
            self.time_input.set_tooltip_text(str(error))
            return
        except OSError as error:
            LOG.error("could not save entry: %s", error)
            return
        self.time_input.set_text("")
        self.time_input.set_tooltip_text(None)
        self.title_input.set_text("")
        self._refresh_day()
        self._refresh_month()

    def _on_remove_entry(self, _button, event):
        try:
            self.store.remove_event(self.selected, event)
        except OSError as error:
            LOG.error("could not save after removing an entry: %s", error)
            return
        self._refresh_day()
        self._refresh_month()

    def _on_note_changed(self, _buffer):
        if self.note_timer is not None:
            GLib.source_remove(self.note_timer)
        self.note_timer = GLib.timeout_add(NOTE_SAVE_DELAY_MS, self._save_note)

    def _save_note(self):
        self.note_timer = None
        buffer = self.notes_view.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        try:
            self.store.set_note(self.selected, text)
        except OSError as error:
            LOG.error("could not save note: %s", error)
            return False
        self._refresh_month()
        return False

    def _on_key_press(self, _widget, event):
        if Gdk.keyval_name(event.keyval) == "Escape":
            self.destroy()
            return True
        return False

    def _on_destroy(self, _widget):
        if self.note_timer is not None:
            GLib.source_remove(self.note_timer)
            self.note_timer = None
            self._save_note()
        Gtk.main_quit()


def run(config):
    store = Store.load(config.events_file)
    holidays = HolidayStore.load(config.holiday_cache_file)
    panel = Panel(config, store, holidays)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, _quit, panel)
    Gtk.main()
    return 0


def _quit(panel):
    panel.destroy()
    return False
