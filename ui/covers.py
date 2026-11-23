"""Real album covers for the interface, with the drawn covers of art.py standing in until one arrives.

Covers are looked up on a daemon thread, slowly, because the services refuse a client that asks
too fast; the track that plays always goes first. When a cover lands, `updated` tells the views,
and each cover fades in over the drawn one. Every cover also gives a colour, its mood, which the
now-playing screen and the glows use; the interface itself stays black and white."""
import collections
import colorsys
import queue
import threading
import time

from PySide6.QtCore import QElapsedTimer, QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap
from shiboken6 import isValid

import artwork
from library import key
from .art import SCALE, cover as drawn

STORE = None
FADE_MS = 700
# Exact covers (a Spotify page, a picture address) are fetched this many at a time.
EXACT_WORKERS = 12
# Searching by name goes one at a time with a short pause: the services refuse a client that hurries.
SEARCH_PAUSE = 1.0
REFUSED_PAUSE = 60.0


def track_key(track):
    return f"{key(track.artist)}\n{key(track.title)}"


def seed(track):
    return f"{track.artist}\n{track.title}"


class Covers(QObject):
    updated = Signal(str)

    def __init__(self, folder, parent):
        super().__init__(parent)
        self.store = artwork.Store(folder)
        self.images = {}
        self.pixmaps = {}
        self.colours = {}
        self.arrived = {}
        self.clock = QElapsedTimer()
        self.clock.start()
        self.queue = collections.deque()
        self.queued = set()
        self.wake = threading.Event()
        self.deezer_after = 0.0
        # Daemon threads rather than a thread pool: a pool's threads are waited for at exit, so
        # closing the app in the middle of loading covers would hang until every one arrived.
        self.exact = queue.Queue()
        for _ in range(EXACT_WORKERS):
            threading.Thread(target=self.exact_work, daemon=True).start()
        self.artists = queue.Queue()
        for _ in range(4):
            threading.Thread(target=self.artist_work, daemon=True).start()
        self.searches = collections.deque()
        self.search_wake = threading.Event()
        threading.Thread(target=self.work, daemon=True).start()
        threading.Thread(target=self.search_work, daemon=True).start()

    def image(self, track):
        name = track_key(track)
        if name not in self.images:
            path = self.store.path(track.artist, track.title)
            picture = QImage(str(path)) if path.exists() else QImage()
            self.images[name] = None if picture.isNull() else picture
        return self.images[name]

    def fading(self, track):
        """0..1 while a cover that just arrived fades in; 1 once it settled."""
        landed = self.arrived.get(track_key(track))
        if landed is None:
            return 1.0
        return min(1.0, (self.clock.elapsed() - landed) / FADE_MS)

    def pixmap(self, track, size, round_=False):
        """The cover at a size in logical pixels; the drawn one while there is no real cover."""
        name = (track_key(track), size, round_)
        if name in self.pixmaps:
            return self.pixmaps[name]
        picture = self.image(track)
        if picture is None:
            return drawn(seed(track), size)
        side = size * SCALE
        result = QPixmap(side, side)
        result.fill(Qt.GlobalColor.transparent)
        with QPainter(result) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            clip = QPainterPath()
            if round_:
                clip.addEllipse(QRectF(0, 0, side, side))
            else:
                clip.addRoundedRect(QRectF(0, 0, side, side), side * 0.07, side * 0.07)
            painter.setClipPath(clip)
            scaled = picture.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(QRectF(0, 0, side, side), scaled,
                              QRectF((scaled.width() - side) / 2, (scaled.height() - side) / 2, side, side))
        result.setDevicePixelRatio(SCALE)
        self.pixmaps[name] = result
        return result

    def paint(self, painter, area, track, size):
        """Draws the cover into an area, cross-fading from the drawn cover when the real one just came."""
        fade = self.fading(track)
        if fade < 1:
            stand_in = drawn(seed(track), size)
            painter.drawPixmap(area, stand_in, QRectF(stand_in.rect()))
            painter.save()
            painter.setOpacity(painter.opacity() * fade)
        picture = self.pixmap(track, size)
        painter.drawPixmap(area, picture, QRectF(picture.rect()))
        if fade < 1:
            painter.restore()

    def colour(self, track):
        """The mood of a cover: its most vivid colour, brought to a lightness that glows on black.
        Grey for drawn covers and for covers without colour."""
        name = track_key(track)
        if name in self.colours:
            return self.colours[name]
        picture = self.image(track)
        if picture is None:
            return QColor(200, 200, 200)
        small = picture.scaled(24, 24, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        weight_sum, red, green, blue = 0.0, 0.0, 0.0, 0.0
        for y in range(small.height()):
            for x in range(small.width()):
                pixel = small.pixelColor(x, y)
                h, l, s = colorsys.rgb_to_hls(pixel.redF(), pixel.greenF(), pixel.blueF())
                weight = (s ** 2) * (1 - abs(l - 0.5) * 1.6) + 0.002
                weight_sum += weight
                red += pixel.redF() * weight
                green += pixel.greenF() * weight
                blue += pixel.blueF() * weight
        h, l, s = colorsys.rgb_to_hls(red / weight_sum, green / weight_sum, blue / weight_sum)
        r, g, b = colorsys.hls_to_rgb(h, 0.58, min(1.0, s * 1.35) if s > 0.12 else 0.0)
        result = QColor.fromRgbF(r, g, b)
        self.colours[name] = result
        return result

    def palette(self, track, count=4):
        """A few distinct colours of a cover, the most vivid first, for the moving background."""
        name = ("palette", track_key(track))
        if name in self.colours:
            return self.colours[name]
        picture = self.image(track)
        if picture is None:
            base = [QColor(70, 70, 70), QColor(40, 40, 40), QColor(110, 110, 110), QColor(25, 25, 25)]
            return base[:count]
        small = picture.scaled(32, 32, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        buckets = {}
        for y in range(small.height()):
            for x in range(small.width()):
                pixel = small.pixelColor(x, y)
                h, l, s = colorsys.rgb_to_hls(pixel.redF(), pixel.greenF(), pixel.blueF())
                if l < 0.06:
                    continue
                slot = (int(h * 12) if s > 0.15 else 12, int(l * 3))
                weight = 0.15 + s * (1 - abs(l - 0.5))
                entry = buckets.setdefault(slot, [0.0, 0.0, 0.0, 0.0])
                entry[0] += weight
                entry[1] += pixel.redF() * weight
                entry[2] += pixel.greenF() * weight
                entry[3] += pixel.blueF() * weight
        ranked = sorted(buckets.values(), key=lambda entry: -entry[0])
        colours = []
        for weight, red, green, blue in ranked:
            h, l, s = colorsys.rgb_to_hls(red / weight, green / weight, blue / weight)
            r, g, b = colorsys.hls_to_rgb(h, min(0.55, max(0.22, l)), min(1.0, s * 1.25))
            colour = QColor.fromRgbF(r, g, b)
            if all(abs(colour.hslHue() - other.hslHue()) > 18 or abs(colour.lightness() - other.lightness()) > 50
                   for other in colours):
                colours.append(colour)
            if len(colours) == count:
                break
        while len(colours) < count:
            colours.append(QColor(colours[-1] if colours else QColor(60, 60, 60)).darker(160))
        self.colours[name] = colours
        return colours

    def artist_image(self, name):
        cached = ("artist", key(name))
        if cached not in self.images:
            path = self.store.artist_path(name, )
            picture = QImage(str(path)) if path.exists() else QImage()
            self.images[cached] = None if picture.isNull() else picture
        return self.images[cached]

    def artist_pixmap(self, name, size):
        """A round photo of the artist, or None while there is none."""
        cached = ("artist", key(name), size)
        if cached in self.pixmaps:
            return self.pixmaps[cached]
        picture = self.artist_image(name)
        if picture is None:
            return None
        side = size * SCALE
        result = QPixmap(side, side)
        result.fill(Qt.GlobalColor.transparent)
        with QPainter(result) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            clip = QPainterPath()
            clip.addEllipse(QRectF(0, 0, side, side))
            painter.setClipPath(clip)
            scaled = picture.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(QRectF(0, 0, side, side), scaled,
                              QRectF((scaled.width() - side) / 2, (scaled.height() - side) / 2, side, side))
        result.setDevicePixelRatio(SCALE)
        self.pixmaps[cached] = result
        return result

    def want_artists(self, tracks):
        """Asks for a photo of every artist, through the first of their tracks that has an address."""
        seen = set()
        for track in tracks:
            name = key(track.artist)
            if name in seen or not track.url or track.source not in ("Spotify", "SoundCloud"):
                continue
            seen.add(name)
            if not self.store.artist_path(track.artist).exists():
                self.artists.put((track.artist, track.url))

    def artist_work(self):
        while True:
            artist, url = self.artists.get()
            try:
                found = self.store.fetch_artist(artist, url)
            except Exception:
                found = False
            if found and isValid(self):
                self.updated.emit(f"artist\n{key(artist)}")

    def want(self, tracks, first=False, url=""):
        """Asks for covers of tracks that have none yet. `first` puts them ahead of the rest."""
        for track in tracks:
            name = track_key(track)
            if self.store.has(track.artist, track.title):
                continue
            exact = bool(url) or (track.source == "Spotify" and bool(track.url))
            if not exact and self.store.missed(track.artist, track.title):
                continue
            if name in self.queued:
                if not first:
                    continue
                # Already waiting somewhere in the line: the track that plays jumps to the front.
                for item in list(self.queue):
                    if track_key(item[0]) == name:
                        try:
                            self.queue.remove(item)
                        except ValueError:
                            pass
            self.queued.add(name)
            item = (track, url)
            self.queue.appendleft(item) if first else self.queue.append(item)
        self.wake.set()  # also cuts short the pause between background lookups

    def work(self):
        """Hands tracks out: those with an exact source to the parallel pool, the rest to the search lane."""
        while True:
            if not self.queue:
                self.wake.wait()
                self.wake.clear()
                continue
            track, url = self.queue.popleft()
            if url or (track.source == "Spotify" and track.url):
                self.exact.put((track, url))
            else:
                self.searches.append((track, url))
                self.search_wake.set()

    def finish(self, track, found):
        self.queued.discard(track_key(track))
        if found and isValid(self):
            self.updated.emit(track_key(track))

    def exact_work(self):
        while True:
            track, url = self.exact.get()
            self.exact_one(track, url)

    def exact_one(self, track, url):
        try:
            found = self.store.fetch(track.artist, track.title, url, False, track.url)
        except Exception:
            found = False
        if not found and not url:
            # No cover at Spotify: let the search lane try by name.
            self.searches.append((track, ""))
            self.search_wake.set()
            return
        self.finish(track, found)

    def search_work(self):
        while True:
            if not self.searches:
                self.search_wake.wait()
                self.search_wake.clear()
                continue
            track, url = self.searches.popleft()
            try:
                found = self.store.fetch(track.artist, track.title, url, time.monotonic() > self.deezer_after)
            except artwork.Refused:
                self.deezer_after = time.monotonic() + REFUSED_PAUSE
                found = self.store.has(track.artist, track.title)
                self.store.miss(track.artist, track.title) if not found else None
            except Exception:
                found = False
            self.finish(track, found)
            time.sleep(SEARCH_PAUSE)

    def landed(self, name):
        """Called on the window thread when a cover arrived: forget stale copies, start the fade."""
        if name.startswith("artist\n"):
            artist = name.split("\n", 1)[1]
            self.images.pop(("artist", artist), None)
            for cached in [cached for cached in self.pixmaps if cached[:2] == ("artist", artist)]:
                del self.pixmaps[cached]
            self.arrived[name] = self.clock.elapsed()
            return
        self.images.pop(name, None)
        self.colours.pop(name, None)
        self.colours.pop(("palette", name), None)
        for cached in [cached for cached in self.pixmaps if cached[0] == name]:
            del self.pixmaps[cached]
        self.arrived[name] = self.clock.elapsed()


def install(folder, parent):
    global STORE
    STORE = Covers(folder, parent)
    STORE.updated.connect(STORE.landed)
    return STORE
