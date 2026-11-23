"""The home screen on the graphics card: ui/qml/Home.qml draws it, this module gives it its lists:
"Мой поток" with covers floating around it, quick access circles, mixes, artists, tracks. It keeps
the signals of the old widget home, so the window drives it the same way."""
import hashlib
import random
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QCursor
from PySide6.QtQuickWidgets import QQuickWidget

from library import key
from . import covers
from .art import avatar, cover as drawn, initial
from .home import greeting, mixes
from .models import Items
from .widgets import measure, plural

QML = Path(__file__).resolve().parent / "qml" / "Home.qml"


class Bridge(QObject):
    """What Home.qml reads. Every value tells the screen only when it really changed, and the
    lists are models changed in place: a rebuild that changes nothing redraws nothing."""
    greetingChanged = Signal()
    streamCaptionChanged = Signal()
    streamingChanged = Signal()
    emptyChanged = Signal()
    coloursChanged = Signal()
    pulsed = Signal()
    LISTS = ("floating", "dial", "mixes", "artists", "recent", "tracks")

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.data = dict(greeting=greeting(), streamCaption="Бесконечно по вашему вкусу", streaming=False, empty=False,
                         colours=["#3a2a40", "#202030", "#402838", "#141418"])
        self.lists = {name: Items(self) for name in self.LISTS}
        self.loud = 0.0

    def get(name):
        return lambda self: self.data[name]

    def model(name):
        return Property(QObject, lambda self: self.lists[name], constant=True)

    greeting = Property(str, get("greeting"), notify=greetingChanged)
    streamCaption = Property(str, get("streamCaption"), notify=streamCaptionChanged)
    streaming = Property(bool, get("streaming"), notify=streamingChanged)
    empty = Property(bool, get("empty"), notify=emptyChanged)
    colours = Property("QVariantList", get("colours"), notify=coloursChanged)
    floating = model("floating")
    dial = model("dial")
    mixes = model("mixes")
    artists = model("artists")
    recent = model("recent")
    tracks = model("tracks")
    bass = Property(float, lambda self: self.loud, notify=pulsed)
    del get, model

    def update(self, **values):
        for name, value in values.items():
            if name in self.lists:
                self.lists[name].replace(value)
            elif self.data[name] != value:
                self.data[name] = value
                getattr(self, name + "Changed").emit()

    @Slot()
    def startStream(self):
        self.page.radio_requested.emit()

    @Slot()
    def openSearch(self):
        self.page.search_requested.emit()

    @Slot()
    def openImport(self):
        self.page.import_requested.emit()

    @Slot(int)
    def dialChosen(self, index):
        self.page.dial_chosen(index)

    @Slot(int)
    def playMix(self, index):
        if 0 <= index < len(self.page.mix_tracks):
            self.page.play_requested.emit(self.page.mix_tracks[index], 0)

    @Slot(str)
    def showArtist(self, name):
        self.page.artist_chosen.emit(name)

    @Slot(str, int)
    def playTrack(self, kind, index):
        tracks = self.page.lists.get(kind, [])
        if 0 <= index < len(tracks):
            self.page.play_requested.emit(tracks, index)

    @Slot(str, int)
    def hovered(self, kind, index):
        tracks = self.page.lists.get(kind, [])
        if 0 <= index < len(tracks):
            self.page.hovered.emit(tracks[index])

    @Slot(str, int)
    def trackMenu(self, kind, index):
        tracks = self.page.lists.get(kind, [])
        if 0 <= index < len(tracks) and self.page.app:
            self.page.app.openMenu("home-" + kind, index)


class HomeQuick(QObject):
    import_requested = Signal()
    artist_chosen = Signal(str)
    play_requested = Signal(object, int)
    open_requested = Signal(object)
    hovered = Signal(object)
    radio_requested = Signal()
    search_requested = Signal()

    def __init__(self, folder):
        super().__init__()
        self.app = None
        self.folder = Path(folder) / "cache"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.tracks = []
        self.artists = []
        self.recent_tracks = []
        self.mix_tracks = []
        self.made_mixes = []        # (number, tracks, artist names) from mixes.py, once they are built
        self.dial_actions = []
        self.lists = {}
        self.bridge = Bridge(self)
        # Covers arrive in bursts at first; the lists are rebuilt at most this often meanwhile.
        self.refresher = QTimer(self)
        self.refresher.setSingleShot(True)
        self.refresher.setInterval(1500)
        self.refresher.timeout.connect(self.rebuild)

    # ---- pictures as the screen takes them ----

    def cover_url(self, track):
        from . import urls
        return urls.cover(track)

    def old_cover_url(self, track):
        store = covers.STORE
        if store:
            path = store.store.path(track.artist, track.title)
            if path.exists():
                return QUrl.fromLocalFile(str(path)).toString()
        name = hashlib.blake2b(covers.seed(track).encode("utf-8"), digest_size=8).hexdigest()
        path = self.folder / f"drawn-{name}.png"
        if not path.exists():
            drawn(covers.seed(track), 200).save(str(path))
        return QUrl.fromLocalFile(str(path)).toString()

    def artist_url(self, name):
        from . import urls
        return urls.artist(name)

    def old_artist_url(self, name):
        store = covers.STORE
        if store:
            path = store.store.artist_path(name)
            if path.exists():
                return QUrl.fromLocalFile(str(path)).toString()
        digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).hexdigest()
        path = self.folder / f"avatar-{digest}.png"
        if not path.exists():
            avatar(name, 200, initial(name)).save(str(path))
        return QUrl.fromLocalFile(str(path)).toString()

    def colour(self, track):
        return covers.STORE.colour(track).name() if covers.STORE else "#a0a0a0"

    def track_item(self, track):
        return dict(title=track.title, artist=track.artist, cover=self.cover_url(track), colour=self.colour(track))

    # ---- the lists ----

    def show_library(self, tracks, artists):
        self.tracks, self.artists = tracks, artists
        self.rebuild()

    def show_recent(self, recent):
        self.recent_tracks = recent
        self.rebuild()

    def set_mixes(self, made):
        """Mixes made of circles of artists that go together take the place of the plain ones."""
        self.made_mixes = list(made)
        self.rebuild()

    def update_covers(self):
        if not self.refresher.isActive():
            self.refresher.start()

    def rebuild(self):
        tracks, artists = self.tracks, self.artists
        if not tracks:
            self.bridge.update(empty=True, floating=[], dial=[], mixes=[], artists=[], recent=[], tracks=[])
            return
        store = covers.STORE
        top = tracks[:40]
        palette = store.palette(top[0]) if store else []
        names = [colour.name() for colour in palette] or self.bridge.data["colours"]
        with_cover = [track for track in top if store and store.store.has(track.artist, track.title)] or top
        floating = [self.cover_url(track) for track in with_cover[:10]]
        self.mix_tracks, mix_items = [], []
        for number, chosen, names_text in self.made_mixes or mixes(tracks, artists):
            self.mix_tracks.append(chosen)
            shown = [track for track in chosen if store and store.store.has(track.artist, track.title)][:4] or chosen[:4]
            while len(shown) < 4:
                shown.append(shown[-1])
            mix_items.append(dict(number=number, artists=names_text, covers=[self.cover_url(track) for track in shown],
                                  colour=self.colour(shown[0])))
        artist_items = []
        for name, duration, count in artists[:24]:
            mine = next((track for track in tracks if key(track.artist) == key(name)), None)
            artist_items.append(dict(name=name, caption=measure(duration, count), picture=self.artist_url(name),
                                     colour=self.colour(mine) if mine else "#a0a0a0"))
        self.lists = dict(recent=self.recent_tracks[:20], tracks=tracks[:30])
        self.dial_actions = []
        dial = []
        likes = self.app.userdata.likes() if self.app else []
        if likes:
            dial.append(dict(name="Мне нравится", picture="", glyph=self.glyph("heart-filled"), colour="#7a4cff"))
            self.dial_actions.append(("likes", None))
        dial.append(dict(name="Мой поток", picture="", glyph=self.glyph("radio"), colour=names[0]))
        self.dial_actions.append(("stream", None))
        for name, _, _ in artists[:5]:
            dial.append(dict(name=name, picture=self.artist_url(name), glyph="", colour="#404040"))
            self.dial_actions.append(("artist", name))
        self.bridge.update(empty=False, greeting=greeting(), colours=(names + names * 4)[:4], floating=floating, dial=dial,
                           mixes=mix_items, artists=artist_items,
                           recent=[self.track_item(track) for track in self.lists["recent"]],
                           tracks=[self.track_item(track) for track in self.lists["tracks"]],
                           streamCaption=f"Бесконечно по вашему вкусу · {plural(len(tracks), ('трек', 'трека', 'треков'))} и похожие на них")

    def glyph(self, name):
        path = self.folder / f"glyph-{name}.png"
        if not path.exists():
            from .icons import pixmap
            pixmap(name, 96, "#ffffff").save(str(path))
        return QUrl.fromLocalFile(str(path)).toString()

    def dial_chosen(self, index):
        if not (0 <= index < len(self.dial_actions)) or not self.app:
            return
        kind, value = self.dial_actions[index]
        if kind == "likes":
            self.app.setPage(2)
            self.app.setView("likes", -1)
        elif kind == "stream":
            self.radio_requested.emit()
        elif kind == "artist":
            self.artist_chosen.emit(value)

    def set_streaming(self, streaming):
        if streaming != self.bridge.data["streaming"]:
            self.bridge.update(streaming=streaming)

    def set_bass(self, value):
        self.bridge.loud = value
        self.bridge.pulsed.emit()
