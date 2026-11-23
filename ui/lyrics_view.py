"""Finding the text of a song for the now-playing screen (ui/now_quick.py, ui/qml/NowPlaying.qml)."""
import threading

from PySide6.QtCore import QObject, Signal
from shiboken6 import isValid

import lyrics


class LyricsFinder(QObject):
    """Asks lyrics.py on a daemon thread, so a slow answer never blocks the window or its closing."""

    done = Signal(object, object, str)

    def __init__(self, cache, parent):
        super().__init__(parent)
        self.cache = cache

    def ask(self, track, duration_ms):
        def work():
            try:
                found, problem = lyrics.lyrics(track.artist, track.title, duration_ms or None, cache=self.cache), ""
            except lyrics.LyricsFailed as error:
                found, problem = None, str(error)
            except Exception:
                found, problem = None, "Не удалось получить текст песни."
            if isValid(self):
                self.done.emit(track, found, problem)
        threading.Thread(target=work, daemon=True).start()
