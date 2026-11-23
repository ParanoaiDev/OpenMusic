"""Searching the whole of SoundCloud on a daemon thread, for the search page."""
import threading

from PySide6.QtCore import QObject, Signal
from shiboken6 import isValid


class Online(QObject):
    found = Signal(str, object, str)

    def __init__(self, resolver, parent):
        super().__init__(parent)
        self.resolver = resolver

    def ask(self, query):
        def work():
            try:
                found, problem = self.resolver.search_online(query, 30), ""
            except Exception:
                found, problem = [], "SoundCloud не ответил. Проверьте интернет."
            if isValid(self):
                self.found.emit(query, found, problem)
        threading.Thread(target=work, daemon=True).start()
