"""The page of an artist for the Qt Quick screen: a big photo with the name over it, the popular
tracks, the artist's tracks in the library, the releases (a release opens over the page with its
tracks) and similar artists. What Deezer knows comes in a thread; the page shows the library part
at once and fills in when the answer and then the pictures land."""
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor, QImage
from shiboken6 import isValid

import artists
from library import Track, key

from . import covers, urls
from .models import ROLES, Items, TrackModel
from .widgets import plural

FAN_FORMS = ("поклонник", "поклонника", "поклонников")
FILTERS = (("all", "Все релизы"), ("album", "Альбомы"), ("single", "Синглы и EP"), ("compile", "Сборники"))


def compact(count):
    """5 242 997 as "5,2 млн", 97 170 as "97 тыс."."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " млн"
    if count >= 10_000:
        return f"{count // 1000} тыс."
    return f"{count:,}".replace(",", " ")


def fans_text(count):
    if count >= 10_000:
        return f"{compact(count)} {FAN_FORMS[2]}"
    return plural(count, FAN_FORMS)


def clock(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}" if seconds else ""


def names_in(artist):
    """The keys of every artist named in a track's artist field ("A & B feat. C")."""
    return {key(part) for part in artists.JOINED.split(artist) if part.strip()}


def tone_of(path):
    """The colour of a photo, brightened enough to tint the page."""
    image = QImage(str(path))
    if image.isNull():
        return "#3a3040"
    colour = image.scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation).pixelColor(0, 0)
    hue, saturation, value, _ = colour.getHsvF()
    return QColor.fromHsvF(max(0.0, hue), min(1.0, saturation * 1.25 + 0.08), min(0.82, max(0.42, value * 1.4))).name()


class PageTracks(TrackModel):
    """Tracks of the page with their album and length in the quiet columns, in place of where they
    came from and how long they were listened to."""

    def __init__(self, app, name):
        super().__init__(app, name)
        self.notes = []

    def replace(self, tracks, notes=None):
        tracks = list(tracks)
        self.notes = list(notes) if notes is not None else [None] * len(tracks)
        super().replace(tracks)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        number = role - Qt.ItemDataRole.UserRole
        if index.isValid() and 0 <= index.row() < len(self.notes) and 1 <= number <= len(ROLES):
            note = self.notes[index.row()]
            name = ROLES[number - 1]
            if note is not None and name in ("source", "detail"):
                return note[0] if name == "source" else note[1]
        return super().data(index, role)


class ArtistPage(QObject):
    changed = Signal()
    leave = Signal()
    loaded = Signal(int, object, str)       # the number of the opening, the profile, the problem
    pictured = Signal(int, object)          # the number of the opening, {address: file}
    released = Signal(int, object, str)     # the number of the release opening, its tracks, the problem

    def __init__(self, app, folder):
        super().__init__(app)
        self.app = app
        self.store = artists.Artists(folder / "cache")
        self.top = PageTracks(app, "artist-top")
        self.mine = PageTracks(app, "artist-mine")
        self.album = PageTracks(app, "artist-album")
        self.releases = Items(self)
        self.related = Items(self)
        self.history = []
        self.serial = 0
        self.album_serial = 0
        self.profile = {}
        self.paths = {}
        self.kind = "all"
        self.album_cover_url = ""
        self.state = dict(name="", status="", picture="", tone="#3a3040", facts="", mineText="", link="", filters=[],
                          kind="all", canBack=False, opened=0, albumOpen=False, albumTitle="", albumCover="", albumFacts="",
                          albumStatus="", albumLink="")
        self.loaded.connect(self.arrived)
        self.pictured.connect(self.pictures_arrived)
        self.released.connect(self.release_arrived)

    page = Property("QVariantMap", lambda self: self.state, notify=changed)
    topModel = Property(QObject, lambda self: self.top, constant=True)
    mineModel = Property(QObject, lambda self: self.mine, constant=True)
    albumModel = Property(QObject, lambda self: self.album, constant=True)
    releaseItems = Property(QObject, lambda self: self.releases, constant=True)
    relatedItems = Property(QObject, lambda self: self.related, constant=True)

    def update(self, **values):
        self.state.update(values)
        self.changed.emit()

    def models(self):
        return self.top, self.mine, self.album

    def lists(self):
        return {"artist-top": self.top.tracks, "artist-mine": self.mine.tracks, "artist-album": self.album.tracks}

    # ---- opening ----

    def open(self, name, fresh=True):
        """Opens the page of an artist; `fresh` starts the way back anew (the page came from elsewhere)."""
        name = artists.main_artist(name)
        if not name:
            return
        if fresh:
            self.history = []
        if not self.history or key(self.history[-1]) != key(name):
            self.history.append(name)
        self.show(name)

    def show(self, name):
        self.serial += 1
        serial = self.serial
        self.profile = {}
        self.kind = "all"
        wanted = names_in(name)
        mine = sorted((track for track in self.app.tracks if names_in(track.artist) & wanted),
                      key=lambda track: (-track.plays, -track.milliseconds, key(track.title)))
        self.mine.replace(mine)
        self.top.replace([])
        self.releases.replace([])
        self.related.replace([])
        store = covers.STORE
        known = store.store.artist_path(name) if store else None
        self.update(name=name, status="loading", picture=urls.local(known) if known and known.exists() else "",
                    tone="#3a3040", facts="", mineText=self.mine_text(mine), link="", filters=[], kind="all",
                    canBack=len(self.history) > 1, opened=serial, albumOpen=False)
        if known and known.exists():
            self.update(tone=tone_of(known))

        def work():
            try:
                found, problem = self.store.profile(name), ""
            except artists.Unavailable:
                found, problem = {}, "Deezer не ответил. Проверьте интернет и попробуйте ещё раз."
            except Exception:
                found, problem = {}, "Не получилось открыть страницу артиста."
            if not isValid(self):
                return
            self.loaded.emit(serial, found, problem)
            if not found.get("found"):
                return
            # The photo first, it is the biggest thing on the page; then the rest, handed over a few at a
            # time as they land, so the tiles fill in one after another.
            first = found.get("picture")
            if first:
                path = self.store.picture(first)
                if path and isValid(self):
                    self.pictured.emit(serial, {first: path})
            rest = [row["cover"] for row in found.get("releases", []) if row.get("cover")]
            rest += [row["picture"] for row in found.get("related", []) if row.get("picture")]
            batch, lock, last = {}, threading.Lock(), [time.monotonic()]

            def landed(address, path):
                with lock:
                    batch[address] = path
                    if len(batch) < 8 and time.monotonic() - last[0] < 0.25:
                        return
                    ready = dict(batch)
                    batch.clear()
                    last[0] = time.monotonic()
                if isValid(self) and serial == self.serial:
                    self.pictured.emit(serial, ready)
            self.store.pictures_for(rest, landed)
            if batch and isValid(self):
                self.pictured.emit(serial, dict(batch))
        threading.Thread(target=work, daemon=True).start()

    def mine_text(self, mine):
        return f"В вашей медиатеке {plural(len(mine), ('трек', 'трека', 'треков'))}" if mine else ""

    def arrived(self, serial, found, problem):
        if serial != self.serial:
            return
        if problem:
            self.update(status="offline", facts=problem)
            return
        self.profile = found
        if not found.get("found"):
            self.update(status="missing",
                        facts="Deezer не знает этого артиста." + (" Вот что есть у вас." if self.mine.tracks else ""))
            return
        library = {(key(track.title), key(track.artist)): track for track in self.app.tracks}
        tracks, notes = [], []
        for row in found.get("top", []):
            track = library.get((key(row["title"]), key(row["artist"])))
            if track is None:
                track = Track(row["title"], row["artist"], "Deezer", row["link"])
                if row.get("cover") and covers.STORE:
                    covers.STORE.want([track], url=row["cover"])
            tracks.append(track)
            notes.append((row.get("album", ""), clock(row.get("seconds", 0))))
        self.top.replace(tracks, notes)
        facts = [fans_text(found.get("fans", 0)) + " на Deezer"]
        if found.get("albums"):
            facts.append(plural(found["albums"], ("релиз", "релиза", "релизов")))
        kinds = {self.kind_of(row) for row in found.get("releases", [])}
        filters = [dict(kind=kind, title=title) for kind, title in FILTERS if kind == "all" or kind in kinds]
        # The spelling of the library stays ("PHARAOH" does not turn into "Pharaoh" under the eyes).
        shown = self.state["name"] if key(found.get("name", "")) == key(self.state["name"]) else found.get("name") or self.state["name"]
        self.update(status="ready", name=shown, facts=" · ".join(facts),
                    link=found.get("link", ""), filters=filters if len(filters) > 2 else [])
        self.fill()

    def pictures_arrived(self, serial, got):
        if serial != self.serial:
            return
        if "album" in got:
            opening, path = got.pop("album")
            if opening == self.album_serial and self.state["albumOpen"]:
                self.update(albumCover=urls.local(path))
            if not got:
                return
        self.paths.update({address: urls.local(path) for address, path in got.items()})
        first = self.profile.get("picture")
        if first in got and (not self.state["picture"] or self.state["picture"] != self.paths[first]):
            self.update(picture=self.paths[first], tone=tone_of(got[first]))
        self.fill()

    @staticmethod
    def kind_of(row):
        return {"Альбом": "album", "Сингл": "single", "EP": "single", "Сборник": "compile"}.get(row.get("kind"), "album")

    def fill(self):
        found = self.profile
        rows = [row for row in found.get("releases", []) if self.kind == "all" or self.kind_of(row) == self.kind]
        self.releases.replace([dict(id=row["id"], title=row["title"], info=" · ".join(part for part in (row["year"], row["kind"]) if part),
                                    cover=self.paths.get(row.get("cover"), ""), link=row.get("link", "")) for row in rows])
        self.related.replace([dict(name=row["name"], fans=fans_text(row.get("fans", 0)), picture=self.paths.get(row.get("picture"), ""))
                              for row in found.get("related", [])])

    # ---- what the screen asks for ----

    @Slot(str)
    def showKind(self, kind):
        if kind != self.kind:
            self.kind = kind
            self.update(kind=kind)
            self.fill()

    @Slot()
    def retry(self):
        if self.history:
            self.show(self.history[-1])

    @Slot()
    def back(self):
        if self.state["albumOpen"]:
            self.closeRelease()
        elif len(self.history) > 1:
            self.history.pop()
            self.show(self.history[-1])
        else:
            self.leave.emit()

    @Slot(int)
    def openRelated(self, index):
        entries = self.related.entries
        if 0 <= index < len(entries):
            self.open(entries[index]["name"], fresh=False)

    @Slot(bool)
    def playTop(self, shuffled):
        tracks = list(self.top.tracks) or list(self.mine.tracks)
        if not tracks:
            return
        if shuffled:
            random.shuffle(tracks)
        self.app.playback.play_tracks(tracks, 0)

    @Slot(int)
    def openRelease(self, index):
        entries = self.releases.entries
        if not 0 <= index < len(entries):
            return
        entry = entries[index]
        self.album_serial += 1
        serial = self.album_serial
        self.album.replace([])
        row = next((row for row in self.profile.get("releases", []) if row["id"] == entry["id"]), {})
        self.album_cover_url = row.get("big") or row.get("cover", "")
        self.update(albumOpen=True, albumTitle=entry["title"], albumCover=entry["cover"], albumFacts=entry["info"],
                    albumStatus="loading", albumLink=entry.get("link", ""))

        def cover():
            big = self.store.picture(row.get("big", "")) if row.get("big") else None
            if big and isValid(self):
                self.pictured.emit(self.serial, {"album": (serial, big)})
        threading.Thread(target=cover, daemon=True).start()

        def work():
            try:
                tracks, problem = self.store.release(entry["id"]), ""
            except Exception:
                tracks, problem = [], "Deezer не отдал треки этого релиза. Попробуйте ещё раз."
            if isValid(self):
                self.released.emit(serial, tracks, problem)
        threading.Thread(target=work, daemon=True).start()

    def release_arrived(self, serial, rows, problem):
        if serial != self.album_serial or not self.state["albumOpen"]:
            return
        if problem:
            self.update(albumStatus=problem)
            return
        artist = self.state["name"]
        library = {(key(track.title), key(track.artist)): track for track in self.app.tracks}
        tracks, fresh = [], []
        for row in rows:
            singer = row.get("artist") or artist
            track = library.get((key(row["title"]), key(singer)))
            if track is None:
                track = Track(row["title"], singer, "Deezer", row["link"])
                fresh.append(track)
            tracks.append(track)
        if fresh and self.album_cover_url and covers.STORE:
            covers.STORE.want(fresh, url=self.album_cover_url)
        total = sum(row.get("seconds", 0) for row in rows)
        self.album.replace(tracks, [("", clock(row.get("seconds", 0))) for row in rows])
        facts = [self.state["albumFacts"], plural(len(rows), ("трек", "трека", "треков"))]
        if total:
            facts.append(f"{total // 60} мин")
        self.update(albumStatus="ready", albumFacts=" · ".join(part for part in facts if part))

    @Slot()
    def closeRelease(self):
        self.album_serial += 1
        self.update(albumOpen=False)

    @Slot(bool)
    def playRelease(self, shuffled):
        tracks = list(self.album.tracks)
        if tracks:
            if shuffled:
                random.shuffle(tracks)
            self.app.playback.play_tracks(tracks, 0)

    @Slot(str)
    def openLink(self, link):
        if link:
            self.app.open_link(link)
