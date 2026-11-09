# waybar-calendar

A drop-down calendar panel for [Waybar](https://github.com/Alexays/Waybar) on
wlroots compositors. Scroll on the clock and a month grid slides down under the
bar, where you can book entries against a day, keep a free-text note per day,
and see UK bank holidays pulled from the official gov.uk feed.

Waybar's own clock tooltip can draw a calendar, but a tooltip cannot take
clicks or typing. This is a separate layer-shell window, so it can.

## Features

- Month grid with today, the selected day, holidays and days that have content
  all marked differently.
- Timed or all-day entries per day, added and removed in the panel.
- One free-text note per day, saved as you type.
- UK bank holidays from `https://www.gov.uk/bank-holidays.json`, fetched in the
  background, cached on disk and usable offline.
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

Add the scroll actions to your clock module, as in
[`examples/waybar-clock.jsonc`](examples/waybar-clock.jsonc):

```jsonc
"clock": {
    "format": "{:%H:%M}",
    "on-scroll-down": "waybar-calendar --toggle",
    "on-scroll-up": "waybar-calendar --toggle"
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
| Type a time and title, then Enter or `+` | Add an entry. A blank time means all day. |
| `×` on an entry | Remove it |
| `Escape` | Close the panel |

A time that is not `HH:MM` turns the time box red and nothing is saved.

## Development

Tests are standard library `unittest`, no dependencies, and none of them need
GTK or a display:

```sh
python3 -m unittest discover -s tests -t .
```

## Licence

MIT. See [LICENSE](LICENSE).
