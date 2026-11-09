# waybar-calendar

A drop-down calendar panel for [Waybar](https://github.com/Alexays/Waybar) on
wlroots compositors. Scroll on the clock and a month grid slides down under the
bar, where you can book entries against a day, keep a free-text note per day,
and see UK bank holidays pulled from the official gov.uk feed.

Waybar's own clock tooltip can draw a calendar, but a tooltip cannot take
clicks or typing. This is a separate layer-shell window, so it can.

## Features

- Month grid with today, the selected day, weekends, holidays and days that
  have something on them all marked differently.
- Timed or all-day entries per day. The time is set by hovering the hour and
  minute fields and scrolling, not by typing.
- One free-text note per day, saved as you type.
- UK bank holidays from `https://www.gov.uk/bank-holidays.json`, fetched in the
  background, cached on disk and usable offline.
- A replacement clock module with two states: time only shows a calendar
  preview on hover, and time with date opens the panel on scroll. The preview
  and the panel never fight over the same gesture.
- Single instance with a toggle, so the same bar action opens and closes it.
- Styled in plain CSS in one file.

## Requirements

- Python 3.9 or newer
- GTK 3 with GObject introspection (`python-gobject`)
- `gtk-layer-shell` with its typelib
- A wlroots compositor supporting `wlr-layer-shell` (Hyprland, Sway, river)

On Arch:

```sh
sudo pacman -S python-gobject gtk3 gtk-layer-shell
```

## Install

```sh
git clone <this repo> ~/src/waybar-calendar
~/src/waybar-calendar/install.sh
```

`install.sh` symlinks `bin/waybar-calendar` into `~/.local/bin` (pass another
directory as the first argument). Nothing is copied, so `git pull` is enough to
update. You can also run it straight from a checkout with
`./bin/waybar-calendar`.

## Wiring it into Waybar

Replace the built-in clock with the module this ships, as in
[`examples/waybar-clock.jsonc`](examples/waybar-clock.jsonc):

```jsonc
"custom/clock": {
    "exec": "waybar-calendar clock render",
    "return-type": "json",
    "interval": 5,
    "signal": 9,
    "tooltip": true,
    "on-click": "waybar-calendar clock toggle",
    "on-scroll-down": "waybar-calendar clock open",
    "on-scroll-up": "waybar-calendar clock close"
}
```

The module has two states and clicking swaps them:

| State | Shows | Hover | Scroll down | Scroll up |
| --- | --- | --- | --- | --- |
| `time` | `20:15` | Calendar preview with today, holidays and busy days marked | Nothing | Nothing |
| `full` | `Mon 09 Nov  20:15` | Nothing, the date is already on the bar | Opens the panel | Closes it |

Clicking back to the time state also closes the panel. Clicking away from the
panel does not, so you can copy out of it.

Waybar sets the state as a CSS class, so `#custom-clock` and
`#custom-clock.full` can be styled differently.

If you would rather keep Waybar's own clock, bind the panel directly instead
and accept that the tooltip and the panel both answer to the clock:

```jsonc
"clock": {
    "format": "{:%H:%M}",
    "on-scroll-down": "waybar-calendar --toggle"
}
```

`--toggle` closes a panel that is already open, so one action does both.

### Hyprland

The window uses the layer namespace `calendar-panel`, so it can be animated and
blurred like any other layer. See
[`examples/hyprland-layer-rule.lua`](examples/hyprland-layer-rule.lua):

```lua
hl.layer_rule({
    match = { namespace = "calendar-panel" },
    animation = "slide top",
    blur = true,
    ignore_alpha = 0.5,
})
```

`ignore_alpha` matters: without it the compositor blurs the fully transparent
pixels outside the rounded corners and you get a square halo.

In `hyprland.conf` syntax that is:

```
layerrule = animation slide top, calendar-panel
layerrule = blur, calendar-panel
layerrule = ignorealpha 0.5, calendar-panel
```

## Configuration

Optional, at `~/.config/waybar-calendar/config.json`. Unknown keys and values
of the wrong type are logged and ignored, so a broken file cannot stop the
panel opening. See [`examples/config.json`](examples/config.json).

| Key | Default | Meaning |
| --- | --- | --- |
| `region` | `england-and-wales` | Which gov.uk division to read holidays from. Also accepts `scotland` and `northern-ireland`. Only that division's holidays are marked. |
| `monitor` | `""` | Monitor model to open on, for example `MSI MP275 E2`. Empty means the compositor decides. |
| `monitor_index` | `-1` | Monitor number to open on. Takes priority over `monitor`. `-1` means unset. |
| `margin_top` | `46` | Gap in pixels below the top edge, so the panel clears your bar. |
| `first_weekday` | `0` | `0` is Monday, `6` is Sunday. |
| `holiday_url` | gov.uk feed | Must be http or https. |
| `holiday_max_age_days` | `7` | How old the cache may get before a refresh is attempted. |
| `holiday_timeout` | `10.0` | Seconds to wait for the feed. |
| `clock_format` | `%H:%M` | `strftime` format for the clock module's time state. |
| `clock_alt_format` | `%a %d %b  %H:%M` | `strftime` format for its date state. |
| `clock_signal` | `9` | Real-time signal used to refresh Waybar when the state changes. Must match `signal` in the module. |

GTK 3 reports monitor *models*, not connector names, so `monitor` will not
match `HDMI-A-1`. Run `waybar-calendar --list-monitors` to see what it can
match, and use `monitor_index` when two screens share a model:

```
$ waybar-calendar --list-monitors
0  'MSI MP2412'  'Microstep'  1920x1080+1920+0
1  'MSI MP275 E2'  'Microstep'  1920x1080+0+0
2  'MSI MP2412'  'Microstep'  1920x1080+-1920+0
```

Styling lives in `waybar_calendar/style.css`. The defaults follow the GitHub
Dark palette.

## Where your data lives

| Path | Contents |
| --- | --- |
| `${XDG_DATA_HOME:-~/.local/share}/waybar-calendar/events.json` | Your entries and notes |
| `${XDG_CACHE_HOME:-~/.cache}/waybar-calendar/holidays.json` | Cached holiday feed |
| `${XDG_RUNTIME_DIR}/waybar-calendar/panel.lock` | Single-instance lock |
| `${XDG_RUNTIME_DIR}/waybar-calendar/clock-state` | Which state the clock module is in |

`events.json` is plain JSON keyed by ISO date, written atomically, and days
that end up with no entries and no note are dropped:

```json
{
  "2026-12-25": {
    "events": [{ "time": "13:00", "title": "Dinner at mum's" }],
    "note": "take the good knives"
  }
}
```

## Keys and mouse

| Action | Result |
| --- | --- |
| Click a day | Select it and show its entries and note |
| `‹` `›` `today` | Move between months |
| Scroll over the hour or minute | Change the time, wrapping at both ends |
| `all day` | Drop the time from the entry being added |
| Type a title, then Enter or `Add` | Add the entry to the selected day |
| `×` on an entry | Remove it |
| `Escape` | Close the panel |
| Scroll up on the clock, or click it back to time | Close the panel |

Minutes move in steps of five. An entry with no title is refused and the title
box turns red.

## Development

Tests are standard library `unittest`, no dependencies, and none of them need
GTK or a display:

```sh
python3 -m unittest discover -s tests -t .
```

## Licence

MIT. See [LICENSE](LICENSE).
