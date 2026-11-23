"""Lists for the Qt Quick screens. Pictures of tracks are worked out only for the rows on screen."""
from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Property, Qt, Signal

from . import urls
from .widgets import listening

ROLES = ("title", "artist", "source", "cover", "colour", "detail", "current")


class TrackModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, app, name):
        super().__init__(app)
        self.app = app
        self.name = name
        self.tracks = []

    def replace(self, tracks):
        self.beginResetModel()
        self.tracks = list(tracks)
        self.endResetModel()
        self.countChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.tracks)

    def roleNames(self):
        return {Qt.ItemDataRole.UserRole + number: QByteArray(name.encode()) for number, name in enumerate(ROLES, start=1)}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.tracks):
            return None
        number = role - Qt.ItemDataRole.UserRole
        if not 1 <= number <= len(ROLES):
            return None
        track = self.tracks[index.row()]
        name = ROLES[number - 1]
        if name == "title":
            return track.title
        if name == "artist":
            return track.artist
        if name == "source":
            return track.source
        if name == "cover":
            return urls.cover(track)
        if name == "colour":
            return urls.colour(track)
        if name == "detail":
            parts = []
            if track.plays:
                parts.append(f"{track.plays} прослуш.")
            if track.milliseconds:
                parts.append(listening(track.milliseconds))
            return " · ".join(parts)
        if name == "current":
            return self.app.playback.is_current(track)
        return None

    def refresh(self, names):
        if self.tracks:
            roles = [Qt.ItemDataRole.UserRole + ROLES.index(name) + 1 for name in names]
            self.dataChanged.emit(self.index(0), self.index(len(self.tracks) - 1), roles)

    count = Property(int, lambda self: len(self.tracks), notify=countChanged)


class Items(QAbstractListModel):
    """A list of plain entries (each a dict or a string, read as "entry") for a row of tiles.
    Putting a new list in changes only the rows that differ, so the tiles stay where they are:
    a list handed over as a plain array is built anew on every change, which blinks every
    picture and winds a scrolled row back to its start."""
    countChanged = Signal()
    ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def roleNames(self):
        return {self.ROLE: QByteArray(b"entry")}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == self.ROLE and index.isValid() and 0 <= index.row() < len(self.entries):
            return self.entries[index.row()]
        return None

    def replace(self, entries):
        entries, before = list(entries), self.entries
        kept = min(len(before), len(entries))
        if len(entries) > len(before):
            self.beginInsertRows(QModelIndex(), len(before), len(entries) - 1)
            self.entries = before + entries[kept:]
            self.endInsertRows()
        elif len(entries) < len(before):
            self.beginRemoveRows(QModelIndex(), len(entries), len(before) - 1)
            self.entries = before[:kept]
            self.endRemoveRows()
        self.entries = entries
        for row in range(kept):
            if before[row] != entries[row]:
                self.dataChanged.emit(self.index(row), self.index(row), [self.ROLE])
        if len(entries) != len(before):
            self.countChanged.emit()

    count = Property(int, lambda self: len(self.entries), notify=countChanged)
