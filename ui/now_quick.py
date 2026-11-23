"""The now-playing screen on the graphics card: ui/qml/NowPlaying.qml draws and animates it, this
module feeds it. It follows what plays, finds its text (lyrics.py), cover and colours (covers.py),
the artist's photo, the ring of the logo, and passes on the loudness (pulse.py) and the position."""
import hashlib
import json
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QFont, QFontMetricsF
from PySide6.QtQuickWidgets import QQuickWidget

import lyrics
from library import key
from . import covers
from .art import cover as drawn, ring
from .lyrics_view import LyricsFinder

QML = Path(__file__).resolve().parent / "qml" / "NowPlaying.qml"
# Words of a line that only has line timing come in one after another at this pace: an entrance,
# not a guess at when each word is sung.
CASCADE_MS = 70


def accent(words):
    """The word of a line that gets the white plate: the longest real word, if it is long enough."""
    candidates = [index for index, word in enumerate(words) if sum(char.isalnum() for char in word) >= 4]
    return max(candidates, key=lambda index: (len(words[index]), -index)) if candidates else -1


def word_timed(found):
    """Whether the text has real timing for its words, not an even share of each line."""
    for line in found.lines:
        lengths = [word.end_ms - word.start_ms for word in line.words]
        if len(lengths) > 2 and max(lengths) - min(lengths) > 3:
            return True
    return False


class Bridge(QObject):
    stateChanged = Signal()
    # The text has signals of its own: the screen builds a row for every line, and must not build
    # them again each time a cover arrives or a button is pressed.
    linesChanged = Signal()
    clipRowsChanged = Signal()
    timingChanged = Signal()
    pulseChanged = Signal()

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.state = dict(hasTrack=False, title="", artist="", cover="", artistPhoto="",
                          colours=["#3c3c3c", "#282828", "#505050", "#191919"], mood=QColor(200, 200, 200),
                          message="Включите трек — здесь появятся его обложка и текст.", lines=[], synced=False,
                          rough=False, note="",
                          clipRows=[], mode="list", offsetMs=0, offsetText="Текст: в такт", textScale=1.0, centered=False,
                          ring=dict(band="", edge="", tilt=0.0, squash=0.8, speed=10.0, phase=0.0))
        self.timing = dict(positionBase=0.0, positionAt=time.time() * 1000, playing=False)
        self.loud = dict(level=0.0, bass=0.0)

    def update(self, **values):
        lines = "lines" in values and values["lines"] != self.state["lines"]
        rows = "clipRows" in values and values["clipRows"] != self.state["clipRows"]
        self.state.update(values)
        if lines:
            self.linesChanged.emit()
        if rows:
            self.clipRowsChanged.emit()
        self.stateChanged.emit()

    def get(name, store="state"):
        return lambda self: getattr(self, store)[name]

    hasTrack = Property(bool, get("hasTrack"), notify=stateChanged)
    title = Property(str, get("title"), notify=stateChanged)
    artist = Property(str, get("artist"), notify=stateChanged)
    cover = Property(str, get("cover"), notify=stateChanged)
    artistPhoto = Property(str, get("artistPhoto"), notify=stateChanged)
    colours = Property("QVariantList", get("colours"), notify=stateChanged)
    mood = Property(QColor, get("mood"), notify=stateChanged)
    message = Property(str, get("message"), notify=stateChanged)
    lines = Property("QVariantList", get("lines"), notify=linesChanged)
    synced = Property(bool, get("synced"), notify=stateChanged)
    # The text has no timing of its own: its lines are paced over the track, to scroll along.
    rough = Property(bool, get("rough"), notify=stateChanged)
    # A line under the buttons that says what kind of timing the text has, when it is not exact.
    note = Property(str, get("note"), notify=stateChanged)
    clipRows = Property("QVariantList", get("clipRows"), notify=clipRowsChanged)
    mode = Property(str, get("mode"), notify=stateChanged)
    offsetMs = Property(int, get("offsetMs"), notify=stateChanged)
    offsetText = Property(str, get("offsetText"), notify=stateChanged)
    ring = Property("QVariantMap", get("ring"), notify=stateChanged)
    textScale = Property(float, get("textScale"), notify=stateChanged)
    centered = Property(bool, get("centered"), notify=stateChanged)
    positionBase = Property(float, get("positionBase", "timing"), notify=timingChanged)
    positionAt = Property(float, get("positionAt", "timing"), notify=timingChanged)
    playing = Property(bool, get("playing", "timing"), notify=timingChanged)
    level = Property(float, get("level", "loud"), notify=pulseChanged)
    bass = Property(float, get("bass", "loud"), notify=pulseChanged)
    del get

    @Slot(float)
    def seek(self, start):
        self.page.playback.media.setPosition(int(max(0, start - self.state["offsetMs"])))

    @Slot(str)
    def setMode(self, mode):
        self.update(mode=mode)
        self.page.save_look()

    @Slot(float)
    def scaleText(self, step):
        self.update(textScale=max(0.7, min(1.6, round(self.state["textScale"] + step, 2))))
        self.page.save_look()

    @Slot()
    def toggleAlign(self):
        self.update(centered=not self.state["centered"])
        self.page.save_look()

    @Slot(int)
    def shift(self, amount):
        self.page.shift(amount)

    @Slot(float, float)
    def layout(self, width, pixels):
        self.page.layout_clip(width, pixels)


class NowPlayingQuick(QObject):
    def __init__(self, playback, cache, pulse, folder):
        super().__init__()
        self.playback = playback
        self.pulse = pulse
        self.folder = Path(folder)
        (self.folder / "cache").mkdir(parents=True, exist_ok=True)
        self.offsets_path = self.folder / "lyric-offsets.json"
        try:
            self.offsets = json.loads(self.offsets_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.offsets = {}
        self.finder = LyricsFinder(cache, self)
        self.finder.done.connect(self.arrived)
        self.track = None
        self.asked = None
        self.found = None
        self.clip_layout = (1000.0, 80.0)
        self.bridge = Bridge(self)
        self.look_path = self.folder / "now-playing.json"
        try:
            look = json.loads(self.look_path.read_text(encoding="utf-8"))
            self.bridge.state.update(mode=look.get("mode", "list"), textScale=float(look.get("textScale", 1.0)),
                                     centered=bool(look.get("centered", False)))
        except (OSError, ValueError):
            pass
        self.ticker = QTimer(self)
        self.ticker.setInterval(30)
        self.ticker.timeout.connect(self.tick)
        media = playback.media
        media.positionChanged.connect(self.position_changed)
        media.playbackStateChanged.connect(lambda _: self.position_changed(media.position()))
        media.durationChanged.connect(lambda _: self.follow())
        playback.changed.connect(self.follow)
        if covers.STORE:
            covers.STORE.updated.connect(self.cover_arrived)
        self.follow()

    # ---- what plays ----

    def position_changed(self, position):
        # The player reports what it decodes; the speakers are a little behind it.
        heard = position - self.playback.engine.latency_ms() if self.playback.engine.available else position
        self.bridge.timing.update(positionBase=float(max(0, heard)), positionAt=time.time() * 1000, playing=self.playback.playing)
        self.bridge.timingChanged.emit()

    def tick(self):
        if not self.playback.playing:
            self.pulse.rest()
        self.bridge.loud.update(level=self.pulse.level, bass=self.pulse.bass)
        self.bridge.pulseChanged.emit()

    def set_active(self, on):
        """Loudness goes to the screen only while it is shown."""
        self.ticker.start() if on else self.ticker.stop()

    def duration(self):
        """The length of the track that plays, 0 until it is known. While the next track loads the
        player still holds the one before, so its own word counts only once the new one has
        loaded: a text looked up by the length of another track loses its timing."""
        playback = self.playback
        source = playback.source
        if source is None:
            return 0
        if source.duration_ms:
            return source.duration_ms
        return 0 if playback.loading else max(0, playback.media.duration())

    def follow(self):
        track = self.playback.current
        if track is None:
            self.track, self.asked = None, None
            self.bridge.update(hasTrack=False, title="", artist="", lines=[], clipRows=[], synced=False, rough=False, note="",
                               message="Включите трек — здесь появятся его обложка и текст.")
            return
        duration = self.duration()
        wanted = (id(track), bool(duration))
        if wanted == self.asked:
            return
        fresh = self.asked is None or self.asked[0] != id(track)
        self.asked = wanted
        if fresh:
            self.track = track
            self.found = None
            self.bridge.update(hasTrack=True, title=track.title, artist=track.artist, lines=[], clipRows=[], synced=False,
                               rough=False, note="", message="Ищу текст…", ring=self.ring_of(track.artist), **self.offset_state(), **self.looks())
        # Without the length of the recording the timing may belong to another version, so the
        # text is asked for again once the length is known.
        if duration or fresh:
            self.finder.ask(track, duration)

    def looks(self):
        """Cover, colours and artist photo of the current track, as the screen takes them."""
        track = self.track
        store = covers.STORE
        path = store.store.path(track.artist, track.title) if store else None
        if path is None or not path.exists():
            path = self.folder / "cache" / f"drawn-{hashlib.blake2b(covers.seed(track).encode(), digest_size=8).hexdigest()}.png"
            if not path.exists():
                drawn(covers.seed(track), 320).save(str(path))
        colours = [colour.name() for colour in store.palette(track)] if store else ["#3c3c3c"] * 4
        mood = store.colour(track) if store else QColor(200, 200, 200)
        photo = store.store.artist_path(track.artist) if store else None
        return dict(cover=QUrl.fromLocalFile(str(path)).toString(), colours=colours, mood=mood,
                    artistPhoto=QUrl.fromLocalFile(str(photo)).toString() if photo and photo.exists() else "")

    def cover_arrived(self, name):
        if self.track is None:
            return
        if name == covers.track_key(self.track) or name == f"artist\n{key(self.track.artist)}":
            self.bridge.update(**self.looks())

    def ring_of(self, artist):
        """The ring of the logo for an artist: its flat band and edge as pictures, and how to lay them."""
        shape = ring(artist)
        name = hashlib.blake2b(artist.encode("utf-8"), digest_size=8).hexdigest()
        band_path = self.folder / "cache" / f"ring-{name}-band.png"
        edge_path = self.folder / "cache" / f"ring-{name}-edge.png"
        if not band_path.exists() or not edge_path.exists():
            band, edge = shape.sprite(1024)
            band.save(str(band_path))
            edge.save(str(edge_path))
        return dict(band=QUrl.fromLocalFile(str(band_path)).toString(), edge=QUrl.fromLocalFile(str(edge_path)).toString(),
                    tilt=shape.tilt, squash=shape.squash, speed=shape.speed, phase=shape.phase)

    # ---- text ----

    def arrived(self, track, found, problem):
        if self.playback.current is not track:
            return
        if problem:
            message = problem
        elif found is None:
            message = "Текста для этого трека не нашлось."
        elif found.instrumental:
            message = "Этот трек без слов."
        else:
            message = "" if found.synced else "Текст без разметки по времени."
        self.found = found if found and not found.instrumental else None
        shown, rough, note = [], False, ""
        if self.found and self.found.synced:
            shown = self.found.lines
            if self.found.approximate:
                note = "Разметка от записи другой длины — если текст расходится с музыкой, подвиньте его кнопками − и +"
        elif self.found:
            # No timing: the lines are paced over the track, so the text still scrolls along.
            shown = lyrics.paced(self.found.lines, self.duration())
            rough = bool(shown) and shown[0].start_ms is not None
            note = "У этого текста нет разметки по времени — он листается примерно, колесо мыши двигает его" if rough else ""
        lines = [dict(start=float(line.start_ms if line.start_ms is not None else 0),
                      end=float(line.end_ms if line.end_ms is not None else 0), text=line.text) for line in shown]
        self.bridge.update(lines=lines, synced=bool(self.found and self.found.synced), rough=rough, note=note, message=message,
                           clipRows=self.clip_rows())

    def layout_clip(self, width, pixels):
        self.clip_layout = (width, pixels)
        self.bridge.update(clipRows=self.clip_rows())

    def clip_rows(self):
        """Each line of the text broken into rows of words that fit the clip screen, with the delay
        after the line's start at which each word comes in."""
        if not self.found or not self.found.synced:
            return []
        width, pixels = self.clip_layout
        plain = QFont("Inter Display")
        plain.setWeight(QFont.Weight.Black)
        plain.setPixelSize(max(8, int(pixels)))
        slanted = QFont(plain)
        slanted.setItalic(True)
        metrics, italic = QFontMetricsF(plain), QFontMetricsF(slanted)
        space = pixels * 0.26
        timed = word_timed(self.found)
        result = []
        for line in self.found.lines:
            words = line.words or []
            texts = [word.text for word in words] or line.text.split()
            chosen = accent(texts)
            span = max(0, (line.end_ms or 0) - (line.start_ms or 0))
            step = min(CASCADE_MS, span * 0.45 / max(1, len(texts)))
            rows, row, x = [], [], 0.0
            for index, text in enumerate(texts):
                advance = (italic if index == chosen else metrics).horizontalAdvance(text) + (pixels * 0.3 if index == chosen else 0)
                if row and x + advance > width:
                    rows.append(row)
                    row, x = [], 0.0
                delay = (words[index].start_ms - line.start_ms) if timed and words else index * step
                row.append(dict(text=text, accent=index == chosen, delay=float(max(0, delay))))
                x += advance + space
            if row:
                rows.append(row)
            result.append(rows)
        return result

    # ---- moving the text against the music ----

    def offset_state(self):
        value = self.offsets.get(covers.track_key(self.track), 0) if self.track else 0
        seconds = value / 1000
        text = "Текст: в такт" if not value else f"Текст {'раньше' if value > 0 else 'позже'} {abs(seconds):.2f} с".replace(".", ",")
        return dict(offsetMs=int(value), offsetText=text)

    def shift(self, amount):
        if self.track is None:
            return
        name = covers.track_key(self.track)
        self.offsets[name] = max(-15000, min(15000, self.offsets.get(name, 0) + amount))
        try:
            self.offsets_path.write_text(json.dumps(self.offsets, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        self.bridge.update(**self.offset_state())

    def set_mode(self, mode):
        self.bridge.update(mode=mode)

    def save_look(self):
        state = self.bridge.state
        try:
            self.look_path.write_text(json.dumps(dict(mode=state["mode"], textScale=state["textScale"], centered=state["centered"])),
                                      encoding="utf-8")
        except OSError:
            pass
