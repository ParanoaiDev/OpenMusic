"""The listener's settings: what the settings screen changes, kept in settings.json next to the
library. Unknown or broken values fall back to the defaults, so an old file never breaks the start."""
import json
from pathlib import Path

DEFAULTS = dict(
    island=True,          # the island at the top of the screen
    islandPop=True,       # it opens for a moment when a new track starts
    islandLyrics=True,    # the line of the text being sung, in the open island
    islandOverWindows=False,  # off: the island lives on the desktop, under the windows of other apps
    tray=True,            # the icon in the system tray
    closeToTray=False,    # closing the window leaves the music playing in the tray
    resume=True,          # the next start continues the queue where it stopped
    intro=True,           # the start screen
    calm=False,           # backgrounds stand still: less work for the computer
    cacheMb=1500,         # how much sound the audio folder keeps
    volume=0.75,
    islandHinted=False,   # the island has once said what it is
)
CACHE_CHOICES = (500, 1500, 3000, 6000)


class Settings:
    def __init__(self, path):
        self.path = Path(path)
        self.values = dict(DEFAULTS)
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored = {}
        if isinstance(stored, dict):
            for name, value in stored.items():
                if name in DEFAULTS and type(value) is type(DEFAULTS[name]):
                    self.values[name] = value
                elif name in DEFAULTS and isinstance(DEFAULTS[name], float) and isinstance(value, int):
                    self.values[name] = float(value)

    def __getitem__(self, name):
        return self.values[name]

    def set(self, name, value):
        """Changes one setting; False when the name or the kind of value is wrong."""
        if name not in DEFAULTS:
            return False
        wanted = type(DEFAULTS[name])
        if wanted is float and isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value)
        elif wanted is int and isinstance(value, float) and value.is_integer():
            value = int(value)
        if type(value) is not wanted:
            return False
        if self.values[name] != value:
            self.values[name] = value
            self.save()
        return True

    def save(self):
        try:
            self.path.write_text(json.dumps(self.values, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass
