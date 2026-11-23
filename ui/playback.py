"""What is playing: a queue of library tracks whose sound stream.py finds, or one local file.

Everything that waits on the network happens on a few daemon threads, by priority: the track asked
to play first, then the next one of the queue, then the track under the pointer, then the tracks
on screen. A track that was played, hovered or comes next is downloaded whole and starts at once;
one asked for cold plays from its stream while the file is fetched for next time."""
import itertools
import queue
import threading
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from shiboken6 import isValid

import similar
import stream
from library import key

PLAY, NEXT, HOVER, WARM, KEEP = range(5)
WORKERS = 3
# A stream address found in advance is trusted until this long before it expires.
MARGIN_SECONDS = 10 * 60


def on_disk(track):
    """The path of a track that is a file on this computer (imported from a folder or an M3U)."""
    if track.url.startswith("file://"):
        from PySide6.QtCore import QUrl
        path = QUrl(track.url).toLocalFile()
        import os
        return path if os.path.exists(path) else None
    return None


def track_key(track):
    return f"{track.source}\n{key(track.artist)}\n{key(track.title)}"


def song(track):
    """What a track is as a song, whichever service it comes from and however it is spelled there."""
    return similar.song_key(*similar.names_of(track))


FLOW = "Мой поток"
# "Next" pressed between these moments of a track means the track was not wanted: earlier it had
# hardly been heard, later it was listened to.
SKIP_FROM_MS, SKIP_UNTIL_MS = 1500, 30000


class Finder(QObject):
    """Looks up and fetches sound on daemon threads, so the network never blocks the window or its
    closing. Each job says what to do: find the stream, and maybe download the whole track."""

    found = Signal(int, object, object)
    saved = Signal(object, str)
    failed = Signal(int, object, str)

    def __init__(self, resolver, audio, parent):
        super().__init__(parent)
        self.resolver = resolver
        self.audio = audio
        self.jobs = queue.PriorityQueue()
        self.order = itertools.count()
        self.known = {}
        self.busy = set()
        self.lock = threading.Lock()
        self.hover_token = 0
        for _ in range(WORKERS):
            threading.Thread(target=self.work, daemon=True).start()

    def ask(self, priority, track, download, token=0):
        self.jobs.put((priority, next(self.order), track, download, token))

    def fresh(self, track):
        entry = self.known.get(track_key(track))
        if entry and stream.expiry(entry.url) - time.time() > MARGIN_SECONDS:
            return entry
        return None

    def work(self):
        while True:
            priority, _, track, download, token = self.jobs.get()
            name = track_key(track)
            if priority == HOVER and token != self.hover_token:
                continue
            if priority != PLAY:
                with self.lock:
                    if name in self.busy:
                        continue
                    self.busy.add(name)
            try:
                if self.audio.has(track.artist, track.title):
                    if priority == PLAY and isValid(self):
                        self.found.emit(priority, track, None)
                    continue
                source = self.fresh(track) or self.resolver.find(track)
                self.known[name] = source
                if priority == PLAY and isValid(self):
                    self.found.emit(priority, track, source)
                if download:
                    path = self.audio.fetch(source, track.artist, track.title)
                    if path and isValid(self):
                        self.saved.emit(track, str(path))
            except stream.StreamFailed as error:
                if priority == PLAY and isValid(self):
                    self.failed.emit(priority, track, str(error))
            except Exception:
                if priority == PLAY and isValid(self):
                    self.failed.emit(priority, track, "Не удалось получить звук трека.")
            finally:
                with self.lock:
                    self.busy.discard(name)


class Radio(QObject):
    """Finds tracks to play after a seed track, on a daemon thread. pick(seed, count, skip) chooses
    them, skip being the songs already in the queue; the app puts similar.py there, and until then
    it is what SoundCloud's own station plays after the track."""

    found = Signal(object, object, str)

    def __init__(self, resolver, parent):
        super().__init__(parent)
        self.pick = lambda seed, count, skip: resolver.related(seed, limit=count)

    def ask(self, seed, count, skip):
        def work():
            tracks, problem = [], ""
            try:
                tracks = self.pick(seed, count, skip)
            except (similar.Nothing, stream.StreamFailed) as error:
                problem = str(error)
            except Exception:
                problem = "Не удалось подобрать похожие треки."
            if isValid(self):
                self.found.emit(seed, tracks, problem)
        threading.Thread(target=work, daemon=True).start()


class Playback(QObject):
    """The queue and the player. Besides playing in order it shuffles, repeats one track or the
    queue, plays faster or slower, stops on a sleep timer, keeps a history of what was heard, and in
    radio mode ("Мой поток", a jam) keeps adding tracks close to the ones it grows from."""

    changed = Signal()
    problem = Signal(str)
    played = Signal(object, int)
    # A radio asked for more: the track it asked about, the tracks added, what went wrong if anything.
    radio_grew = Signal(object, object, str)
    # The listener switched a track off in its first seconds.
    skipped = Signal(object)

    def __init__(self, resolver, audio, parent):
        super().__init__(parent)
        self.shuffle = False
        self.repeat = "off"
        self.radio = False
        self.radio_name = FLOW
        self.radio_seeds = []       # the tracks the radio grows from, asked about in turn
        self.radio_turn = 0
        self.radio_take = 12        # how many tracks the next answer may add
        self.radio_batch = 12       # and every answer after it
        self.radio_asked = None
        self.radio_seen = set()     # the songs that were in the queue, so none comes twice
        self.radio_busy = False
        self.sleep_at = 0.0
        self.started_ms = 0
        self.counted = False
        self.radio_finder = Radio(resolver, self)
        self.radio_finder.found.connect(self.radio_found)
        self.sleeper = QTimer(self)
        self.sleeper.setInterval(1000)
        self.sleeper.timeout.connect(self.sleep_tick)
        self.counter = QTimer(self)
        self.counter.setInterval(1000)
        self.counter.timeout.connect(self.count_play)
        self.counter.start()
        self.audio_files = audio
        self.media = QMediaPlayer(self)
        from .audio_engine import AudioEngine, Volume
        self.engine = AudioEngine(self.media, audio.folder.parent / "sound.json", parent=self)
        if self.engine.available:
            # The player only decodes; the engine plays, with the effects on the way.
            self.audio = Volume(self.engine)
        else:
            self.audio = QAudioOutput(self)
            self.audio.setVolume(0.75)
            self.media.setAudioOutput(self.audio)
        self.media.mediaStatusChanged.connect(self.status_changed)
        self.media.playbackStateChanged.connect(lambda _: self.changed.emit())
        self.media.errorOccurred.connect(self.media_failed)
        self.finder = Finder(resolver, audio, self)
        self.finder.found.connect(self.found)
        self.finder.failed.connect(self.failed)
        self.queue = []
        self.index = -1
        self.current = None
        self.local = ""
        self.source = None
        self.loading = False
        self.request = None
        self.misses = 0
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(300)
        self.hover_timer.timeout.connect(self.hover_settled)
        self.hovered = None
        self.resume_at = 0

    @property
    def playing(self):
        return self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def play_tracks(self, tracks, index, radio=False):
        self.queue = list(tracks)
        self.local = ""
        self.misses = 0
        self.radio = radio
        self.radio_busy = False
        self.radio_asked = None
        self.radio_seen = {song(track) for track in self.queue}
        if self.shuffle and len(self.queue) > 1:
            self.shuffle_rest(index)
            index = 0
        self.start(index)

    def play_radio(self, seed, seeds=(), name=FLOW, first=None, batch=12, rest=()):
        """Starts an endless radio from a track: it plays first, and tracks close to the seeds are
        added whenever the queue runs out. seeds: the tracks to grow from, asked about in turn (the
        first track alone by default); first: how many tracks the first answer may add, batch: every
        answer after it; rest: tracks already known to follow. A seed that is playing goes on."""
        self.radio_name = name
        self.radio_seeds = list(seeds) or [seed]
        self.radio_turn = 0
        self.radio_batch = batch
        self.radio_take = first or batch
        if self.current is not None and self.is_current(seed) and (self.playing or self.loading):
            self.queue = [self.current, *rest]
            self.index = 0
            self.misses = 0
            self.radio = True
            self.radio_busy = False
            self.radio_asked = None
            self.radio_seen = {song(track) for track in self.queue}
            self.changed.emit()
            if len(self.queue) <= 3:
                self.extend_radio()
        else:
            self.play_tracks([seed, *rest], 0, radio=True)

    def extend_radio(self):
        if not self.radio or self.radio_busy or not self.queue:
            return
        seeds = self.radio_seeds or [self.queue[0]]
        seed = seeds[self.radio_turn % len(seeds)]
        self.radio_turn += 1
        self.radio_busy = True
        self.radio_asked = seed
        self.radio_finder.ask(seed, self.radio_take, frozenset(self.radio_seen))

    def radio_found(self, seed, tracks, problem):
        if seed is not self.radio_asked:
            return      # the answer to a radio that is over
        self.radio_busy = False
        self.radio_asked = None
        if not self.radio:
            return
        # A seed is a track of the listener's own: it plays too, ahead of what is close to it.
        added = []
        for track in [seed, *tracks][:self.radio_take + 1]:
            name = song(track)
            if name not in self.radio_seen:
                self.radio_seen.add(name)
                self.queue.append(track)
                added.append(track)
        self.radio_take = self.radio_batch
        if len(added) < 4 and len(self.radio_seeds) < 12:
            # The seeds have little new left to give: the radio grows on from what it found itself.
            known = {similar.voice(similar.main_artist(similar.names_of(track)[0])) for track in self.radio_seeds}
            fresh = []
            for track in reversed(self.queue[-12:]):
                artist = similar.voice(similar.main_artist(similar.names_of(track)[0]))
                if artist not in known and len(fresh) < 2:
                    known.add(artist)
                    fresh.append(track)
            self.radio_seeds += fresh
        self.radio_grew.emit(seed, added, problem)
        self.changed.emit()
        self.look_ahead()

    def shuffle_rest(self, index):
        """Keeps the chosen track first and shuffles the rest of the queue."""
        import random
        chosen = self.queue[index]
        rest = self.queue[:index] + self.queue[index + 1:]
        random.shuffle(rest)
        self.queue = [chosen] + rest

    def set_shuffle(self, on):
        self.shuffle = on
        if on and self.index >= 0 and len(self.queue) > 1:
            import random
            upcoming = self.queue[self.index + 1:]
            random.shuffle(upcoming)
            self.queue = self.queue[:self.index + 1] + upcoming
        self.changed.emit()

    def cycle_repeat(self):
        self.repeat = {"off": "all", "all": "one", "one": "off"}[self.repeat]
        self.changed.emit()

    def set_speed(self, rate):
        if self.engine.available:
            self.engine.set_speed(rate)
        else:
            self.media.setPlaybackRate(rate)
        self.changed.emit()

    def sleep_in(self, minutes):
        """Stops playback after so many minutes; 0 cancels, -1 means at the end of this track."""
        if minutes == 0:
            self.sleep_at = 0.0
            self.sleeper.stop()
        elif minutes < 0:
            self.sleep_at = -1.0
            self.sleeper.stop()
        else:
            self.sleep_at = time.monotonic() + minutes * 60
            self.sleeper.start()
        self.changed.emit()

    def sleep_tick(self):
        if self.sleep_at > 0 and time.monotonic() >= self.sleep_at:
            self.sleep_at = 0.0
            self.sleeper.stop()
            self.fade_out()

    def fade_out(self):
        from .motion import tween
        start = self.audio.volume()
        def done():
            self.media.pause()
            self.audio.setVolume(start)
            self.changed.emit()
        tween(self, start, 0, 4000, self.audio.setVolume, done, name="sleep")

    def count_play(self):
        """A track counts as heard after 30 seconds or half its length, once per start."""
        if self.current and self.playing and not self.counted:
            heard = self.media.position()
            duration = self.media.duration()
            if heard >= 30000 or (duration and heard >= duration / 2):
                self.counted = True
                self.played.emit(self.current, int(heard))

    def play_file(self, path):
        self.queue, self.index, self.current, self.source = [], -1, None, None
        self.local = path
        self.request = None
        self.loading = False
        self.media.setSource(QUrl.fromLocalFile(path))
        self.media.play()
        self.changed.emit()

    def restore(self, tracks, index, position):
        """Puts back the queue of the last session with its track paused where it stopped; nothing is
        fetched until play is pressed."""
        if not 0 <= index < len(tracks):
            return
        self.queue = list(tracks)
        self.index = index
        self.current = self.queue[index]
        self.local = ""
        self.source = None
        self.request = None
        self.loading = False
        self.resume_at = max(0, int(position))
        self.radio_seen = {song(track) for track in self.queue}
        self.changed.emit()

    def start(self, index, at=0):
        if not 0 <= index < len(self.queue):
            return
        self.resume_at = max(0, int(at))
        self.index = index
        track = self.current = self.queue[index]
        self.source = None
        self.request = track
        self.counted = False
        self.media.stop()
        if self.radio and len(self.queue) - index <= 3:
            self.extend_radio()
        local = on_disk(track)
        if local:
            self.source = stream.Source(track.url, track.title, track.artist, 0, "")
            self.loading = True
            self.media.setSource(QUrl.fromLocalFile(local))
            self.media.play()
        elif track.url.startswith("file://"):
            self.problem.emit(f"{track.artist} — {track.title}: файла больше нет на диске.")
            self.loading = False
        elif self.audio_files.has(track.artist, track.title):
            self.load_file(track)
        else:
            known = self.finder.fresh(track)
            if known:
                self.load_stream(known)
                self.finder.ask(KEEP, track, True)
            else:
                self.loading = True
                self.finder.ask(PLAY, track, True)
        self.changed.emit()

    def found(self, priority, track, source):
        if track is not self.request or self.source is not None:
            return
        if source is None:
            self.load_file(track)
        else:
            self.load_stream(source)

    def load_file(self, track):
        path = self.audio_files.path(track.artist, track.title)
        self.source = stream.Source(QUrl.fromLocalFile(str(path)).toString(), track.title, track.artist, 0, "")
        known = self.finder.known.get(track_key(track))
        if known:
            self.source = stream.Source(self.source.url, known.title, known.artist, known.duration_ms, known.page, known.artwork)
        self.loading = True
        self.media.setSource(QUrl.fromLocalFile(str(path)))
        self.media.play()

    def load_stream(self, source):
        self.source = source
        self.loading = True
        self.media.setSource(QUrl(source.url))
        self.media.play()
        self.changed.emit()

    def failed(self, priority, track, message):
        if track is not self.request:
            return
        self.loading = False
        self.misses += 1
        self.problem.emit(f"{track.artist} — {track.title}: {message}")
        self.changed.emit()
        # A few misses in a row mean something is wrong for every track, so it stops skipping.
        if self.misses < 3 and self.index + 1 < len(self.queue):
            QTimer.singleShot(1200, lambda wanted=track: wanted is self.request and self.start(self.index + 1))

    def status_changed(self, status):
        if status in (QMediaPlayer.MediaStatus.BufferedMedia, QMediaPlayer.MediaStatus.LoadedMedia) and self.loading and self.source:
            self.loading = False
            self.misses = 0
            if self.resume_at:
                self.media.setPosition(self.resume_at)
                self.resume_at = 0
            self.changed.emit()
            self.look_ahead()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.sleep_at < 0:
                self.sleep_at = 0.0
                self.changed.emit()
            elif self.repeat == "one":
                self.media.setPosition(0)
                self.media.play()
            elif self.index + 1 < len(self.queue):
                self.start(self.index + 1)
            elif self.repeat == "all" and self.queue:
                self.start(0)
            else:
                self.changed.emit()

    def look_ahead(self):
        """The next two tracks of the queue are fetched whole while this one plays."""
        for offset, priority in ((1, NEXT), (2, WARM)):
            following = self.index + offset
            if 0 <= following < len(self.queue):
                track = self.queue[following]
                if not track.url.startswith("file://") and not self.audio_files.has(track.artist, track.title):
                    self.finder.ask(priority, track, True)

    def hover(self, track):
        """The pointer rests on a track: after a moment it is fetched, so a click starts it at once."""
        self.hovered = track
        self.hover_timer.start()

    def hover_settled(self):
        track = self.hovered
        if track is None or track.url.startswith("file://") or self.audio_files.has(track.artist, track.title):
            return
        self.finder.hover_token += 1
        self.finder.ask(HOVER, track, True, self.finder.hover_token)

    def warm(self, tracks):
        """Finds the streams of tracks on screen ahead of time; only addresses, no downloads."""
        for track in tracks[:10]:
            if track.url.startswith("file://"):
                continue
            if not self.audio_files.has(track.artist, track.title) and not self.finder.fresh(track):
                self.finder.ask(WARM, track, False)

    def media_failed(self, error, message):
        if self.current and self.source:
            self.failed(PLAY, self.current, "Поток не воспроизводится.")
        elif self.local:
            self.problem.emit("Файл не воспроизводится.")
            self.changed.emit()

    def toggle(self):
        if self.playing:
            self.media.pause()
        elif self.current and self.source is None and not self.loading and self.request is None:
            # The track put back from the last session starts where it stopped.
            self.start(self.index, self.resume_at)
        elif self.current or self.local:
            if self.media.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia and self.queue:
                self.start(self.index)
            else:
                self.media.play()

    def next(self):
        """The listener asks for the next track. Asked in the first seconds of a track that had
        begun to play, it also says the track was not wanted."""
        going_on = self.index + 1 < len(self.queue) or (self.repeat == "all" and bool(self.queue))
        if going_on and self.current is not None and self.source is not None and not self.loading \
                and SKIP_FROM_MS <= self.media.position() < SKIP_UNTIL_MS:
            self.skipped.emit(self.current)
        if self.index + 1 < len(self.queue):
            self.misses = 0
            self.start(self.index + 1)
        elif self.repeat == "all" and self.queue:
            self.start(0)

    def play_at(self, index):
        """Jumps to a track of the queue."""
        if 0 <= index < len(self.queue):
            self.misses = 0
            self.start(index)

    def remove_at(self, index):
        if 0 <= index < len(self.queue) and index != self.index:
            del self.queue[index]
            if index < self.index:
                self.index -= 1
            self.changed.emit()

    def drop_ahead(self, artist):
        """Takes the tracks of an artist (by voice) out of what is still to play."""
        ahead = [track for track in self.queue[self.index + 1:]
                 if similar.voice(similar.main_artist(similar.names_of(track)[0])) != artist]
        if len(ahead) != len(self.queue) - self.index - 1:
            self.queue = self.queue[:self.index + 1] + ahead
            self.changed.emit()
            self.look_ahead()

    def play_next(self, track):
        """Puts a track right after the current one."""
        if self.index < 0:
            self.play_tracks([track], 0)
        else:
            self.queue.insert(self.index + 1, track)
            self.changed.emit()
            self.look_ahead()

    def enqueue(self, track):
        if self.index < 0:
            self.play_tracks([track], 0)
        else:
            self.queue.append(track)
            self.changed.emit()

    def previous(self):
        if self.media.position() > 3000 or self.index <= 0:
            self.media.setPosition(0)
        else:
            self.misses = 0
            self.start(self.index - 1)

    def is_current(self, track):
        return self.current is not None and track_key(track) == track_key(self.current)
