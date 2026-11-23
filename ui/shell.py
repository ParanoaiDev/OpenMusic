"""The whole interface on the graphics card: ui/qml/Shell.qml draws every screen, panel and menu,
and the App object here is what it talks to. It holds the library, the player, the listener's
collections, search and import, and turns what they do into properties the screens bind to."""
import json
import os
import random
import sqlite3
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QStandardPaths, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QWindow
from PySide6.QtWidgets import QApplication, QFileDialog
from shiboken6 import isValid

import jobs
import lyrics
import mixes
import scan
import similar
import stream
import userdata
from library import Track, artist_ranking, key, track_link
from . import covers, urls
from .home_quick import HomeQuick
from .importer import SOURCES as IMPORT_SOURCES
from .island import Island
from .models import TrackModel
from .mpris import Mpris
from .now_quick import NowPlayingQuick
from .playback import FLOW, Playback, on_disk, song
from .pulse import Pulse
from .search_page import Online
from .settings import CACHE_CHOICES, Settings
from .tray import Tray
from .widgets import listening, plural
from .artist_page import ArtistPage

ARTIST_PAGE = 5
JAM = "Джем"
# A jam is the track it is made from and this many tracks in all.
JAM_SIZE = 40
# "Мой поток" is a third the listener's own tracks: each of them brings this many new ones close
# to it, and one more of their own comes in between.
FLOW_NEW = 4
# Mixes built for the home screen are kept this long, then built anew.
MIXES_KEEP = 7 * 24 * 3600
# Skips and plays older than this say nothing about what the listener wants now.
TASTE_DAYS = 120

LIBRARY_SOURCES = ("Spotify", "SoundCloud", "Deezer", "Яндекс Музыка", "Apple Music", "YouTube", "Файлы", "CSV")
PAGES = {"home": 0, "search": 1, "library": 2, "now": 3, "settings": 4}
ROOT = Path(__file__).resolve().parent.parent
MB = 1024 * 1024


class App(QObject):
    stateChanged = Signal()
    settingsChanged = Signal()
    playerChanged = Signal()
    timeChanged = Signal()
    toast = Signal(str, bool, bool)
    menuRequested = Signal("QVariantMap")
    askName = Signal(str, str, str, str)
    askConfirm = Signal(str, str, str)
    querySet = Signal(str)
    waveReady = Signal(object, object)
    spectrumChanged = Signal()
    mixesReady = Signal(object)

    def __init__(self, library):
        super().__init__()
        self.library = library
        folder = library.path.parent
        self.folder = folder
        self.settings = Settings(folder / "settings.json")
        urls.setup(folder)
        covers.install(folder / "covers", self)
        self.userdata = userdata.UserData(folder / "user.sqlite3")
        self.resolver = stream.Resolver(folder / "streams.sqlite3")
        self.playback = Playback(self.resolver, stream.Audio(folder / "audio"), self)
        # Tracks close to a track, for jams and "Мой поток": chosen on the radio's own thread.
        self.similar = similar.Similar(self.resolver)
        self.playback.radio_finder.pick = self.pick_similar
        self.playback.radio_grew.connect(self.radio_grew)
        self.artworks = {}
        self.taste = set()
        self.jam_wait = None        # (number, track) of the jam that is being collected
        self.avoid = {}             # voice of an artist → skipped that many more times than listened to
        self.skipped_songs = set()
        self.mixing = False
        self.playback.skipped.connect(self.skipped)
        self.mixesReady.connect(self.mixes_built)
        self.playback.audio_files.LIMIT = self.settings["cacheMb"] * MB
        self.playback.audio.setVolume(self.settings["volume"])
        self.pulse = Pulse(self.playback.media, self, self.playback.engine)
        self.now = NowPlayingQuick(self.playback, lyrics.Cache(folder / "lyrics.sqlite3"), self.pulse, folder)
        self.home = HomeQuick(folder)
        self.home.app = self
        self.library_model = TrackModel(self, "library")
        self.search_model = TrackModel(self, "search")
        self.queue_model = TrackModel(self, "queue")
        self.artist = ArtistPage(self, folder)
        self.artist.leave.connect(self.leave_artist)
        self.artist_return = 0
        self.online = Online(self.resolver, self)
        self.online.found.connect(self.search_arrived)
        self.window = None
        self.job = None
        self.closing = False
        self.quitting = False
        self.was_maximized = False
        self.tracks = []
        self.view_tracks = []
        self.view = ("library", None)
        self.source = ""
        self.query = ""
        self.search_text = ""
        self.search_local = []
        self.pending_tracks = []
        self.wave_for = None
        self.state = dict(page=0, view="library", viewTitle="Медиатека", viewCount="", emptyText="", sources=[], playlists=[],
                          libraryActions=[], searchStatus="Начните вводить — найдётся всё, что есть на SoundCloud.",
                          importSources=self.import_sources(), sound={}, presets=[], presetGroups=[], spaces=[], scenes=[], empty=True,
                          jams=[],
                          logo=urls.logo(), logoBig=urls.logo(280), queueCaption="",
                          # The start screen; OPENMUSIC_INTRO=0 opens the window at once.
                          intro=os.environ.get("OPENMUSIC_INTRO", "1") != "0" and self.settings["intro"],
                          islandAvailable=True, mprisOk=False, stats={}, cache={}, menuEntry=False,
                          cacheChoices=[dict(mb=mb, title=self.size_text(mb * MB)) for mb in CACHE_CHOICES])
        self.player = dict(hasTrack=False, title="Ничего не играет", artist="", caption="Нажмите на трек, чтобы послушать", cover="",
                           colour="#a0a0a0", playing=False, loading=False, liked=False, shuffle=False, repeat="off",
                           canNext=False, wave=[], volume=self.settings["volume"], speed=1.0, sleep="", radio=False, queueIndex=-1)
        self.time = dict(position=0, duration=0)

        self.playback.changed.connect(self.player_changed)
        self.playback.problem.connect(lambda message: self.say(message, error=True))
        self.playback.played.connect(self.heard)
        self.playback.finder.saved.connect(lambda *_: self.player_changed())
        media = self.playback.media
        media.positionChanged.connect(self.time_changed)
        media.durationChanged.connect(self.time_changed)
        media.durationChanged.connect(lambda _: self.mpris.changed())
        self.waveReady.connect(self.wave_arrived)
        self.home.import_requested.connect(lambda: self.window and self.window.setProperty("importOpen", True))
        self.home.search_requested.connect(lambda: self.setPage(1))
        self.home.radio_requested.connect(self.radioFromTaste)
        self.home.artist_chosen.connect(self.showArtist)
        self.home.play_requested.connect(self.playback.play_tracks)
        self.home.hovered.connect(self.playback.hover)
        self.cover_timer = QTimer(self)
        self.cover_timer.setSingleShot(True)
        self.cover_timer.setInterval(400)
        self.cover_timer.timeout.connect(self.covers_landed)
        covers.STORE.updated.connect(lambda _: self.cover_timer.isActive() or self.cover_timer.start())
        self.bass_timer = QTimer(self)
        self.bass_timer.setInterval(50)
        self.bass_timer.timeout.connect(lambda: self.home.set_bass(self.pulse.bass))
        self.bass_timer.start()
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(380)
        self.search_timer.timeout.connect(self.search_online)
        self.volume_saver = QTimer(self)
        self.volume_saver.setSingleShot(True)
        self.volume_saver.setInterval(700)
        self.volume_saver.timeout.connect(lambda: self.settings.set("volume", round(float(self.player["volume"]), 3)))
        self.bands_now = [0.0] * 48
        self.analyser = QTimer(self)
        self.analyser.setInterval(33)
        self.analyser.timeout.connect(self.analyse)
        self.island = Island(self)
        self.tray = Tray(self, ROOT / "assets" / "icon.png")
        self.mpris = Mpris(self)
        self.state["mprisOk"] = self.mpris.ok
        self.sound_state()
        self.refresh()
        QTimer.singleShot(20000, self.renew_sound)
        if self.settings["resume"]:
            self.restore_session()
        self.tray.sync()

    # ---- properties ----

    stateMap = Property("QVariantMap", lambda self: self.state, notify=stateChanged)
    settingsMap = Property("QVariantMap", lambda self: self.settings.values, notify=settingsChanged)
    playerMap = Property("QVariantMap", lambda self: self.player, notify=playerChanged)
    position = Property(int, lambda self: self.time["position"], notify=timeChanged)
    duration = Property(int, lambda self: self.time["duration"], notify=timeChanged)
    libraryModel = Property(QObject, lambda self: self.library_model, constant=True)
    searchModel = Property(QObject, lambda self: self.search_model, constant=True)
    queueModel = Property(QObject, lambda self: self.queue_model, constant=True)
    spectrum = Property("QVariantList", lambda self: self.bands_now, notify=spectrumChanged)

    def update(self, **values):
        self.state.update(values)
        self.stateChanged.emit()

    @Slot(str, result=str)
    def icon(self, name):
        return urls.icon(name)

    @Slot(str, str, result=str)
    def tinted(self, name, tint):
        return urls.icon(name, tint)

    def say(self, message, sticky=False, error=False):
        self.toast.emit(message, error, sticky)

    # ---- pages ----

    @Slot(int)
    def setPage(self, page):
        if page == 4:
            self.settings_info()
        self.update(page=page)
        self.now.set_active(page == 3)
        if page == 2:
            self.playback.warm(self.library_model.tracks)

    # ---- library ----

    def refresh(self):
        self.tracks = sorted(self.library.tracks(),
                             key=lambda track: (-track.milliseconds, -track.plays, key(track.title), key(track.artist)))
        ranking = artist_ranking(self.tracks)
        self.home.show_library(self.tracks, ranking)
        self.home.show_recent(self.userdata.recent())
        self.taste = {similar.voice(similar.main_artist(track.artist)) for track in self.tracks}
        self.read_dislikes()
        self.make_mixes()
        self.update(empty=not self.tracks)
        self.setView(*self.view)
        covers.STORE.want(self.tracks)
        places = {key(name): place for place, (name, _, _) in enumerate(ranking)}
        covers.STORE.want_artists(sorted(self.tracks, key=lambda track: places.get(key(track.artist), 10_000)))
        self.playback.warm(self.tracks[:8])

    @Slot(str, int)
    def setView(self, kind, playlist=-1):
        playlist = None if playlist is None or playlist < 0 else playlist
        data = self.userdata
        if kind == "likes":
            title, tracks = "Мне нравится", data.likes()
        elif kind == "history":
            title, tracks = "История", data.recent(300)
        elif kind == "playlist" and playlist is not None:
            names = {number: name for number, name, _ in data.playlists()}
            title, tracks = names.get(playlist, "Плейлист"), data.playlist_tracks(playlist)
        elif kind == "jam" and playlist is not None and data.jam_tracks(playlist):
            tracks = data.jam_tracks(playlist)
            title = f"Джем · {tracks[0].title}"
        else:
            kind, playlist, title, tracks = "library", None, "Медиатека", self.tracks
        self.view = (kind, playlist)
        self.view_tracks = tracks
        if kind != "library":
            self.source = ""
        self.update(view=kind, viewTitle=title, playlistId=playlist if playlist is not None else -1,
                    playlists=[dict(id=number, name=name, count=count) for number, name, count in data.playlists()],
                    jams=[dict(id=number, name=f"{seed.artist} — {seed.title}", count=count) for number, seed, count in data.jams()])
        self.apply_filter()

    @Slot(str)
    def filter(self, text):
        self.query = text
        self.apply_filter()

    @Slot(str)
    def setSource(self, source):
        self.source = source
        self.apply_filter()

    def apply_filter(self):
        words = key(self.query).split()
        tracks = self.view_tracks
        matches = [track for track in tracks if (not self.source or track.source == self.source)
                   and all(word in key(f"{track.title} {track.artist}") for word in words)]
        self.library_model.replace(matches)
        counts = {source: sum(track.source == source for track in tracks) for source in LIBRARY_SOURCES}
        several = self.view[0] == "library" and sum(bool(count) for count in counts.values()) > 1
        sources = []
        if several:
            sources.append(dict(name="", title=f"Все  {len(tracks)}", checked=not self.source))
            sources += [dict(name=source, title=f"{source}  {count}", checked=self.source == source)
                        for source, count in counts.items() if count]
        shown = plural(len(matches), ("трек", "трека", "треков"))
        empty = {"likes": "Здесь будут треки, которые вам понравятся. Нажмите ♡ у трека.",
                 "history": "Здесь появятся треки, которые вы слушали.",
                 "playlist": "Плейлист пуст. Добавьте треки через меню трека (правая кнопка).",
                 "jam": "Джем пуст."}.get(
            self.view[0], "Медиатека пуста. Нажмите «+» слева, чтобы добавить музыку.")
        if tracks and not matches:
            empty = "Ничего не найдено."
        actions = []
        if self.view[0] == "playlist":
            actions = [dict(title="Слушать плейлист", action="play-all", arg=""),
                       dict(title="Переименовать…", action="rename-playlist", arg=str(self.view[1])),
                       dict(title="Удалить плейлист", action="delete-playlist", arg=str(self.view[1]))]
        elif self.view[0] == "jam":
            actions = [dict(title="Слушать джем", action="play-jam", arg=str(self.view[1])),
                       dict(title="Собрать заново", action="refresh-jam", arg=str(self.view[1])),
                       dict(title="Сохранить как плейлист…", action="keep-jam", arg=str(self.view[1])),
                       dict(title="Удалить джем", action="delete-jam", arg=str(self.view[1]))]
        elif self.view[0] == "library":
            actions = [dict(title=f"Удалить импорт {source}", action="clear-source", arg=source)
                       for source, count in counts.items() if count]
        else:
            actions = [dict(title="Слушать всё", action="play-all", arg="")]
        count = shown if len(matches) == len(tracks) else f"{shown} из {len(tracks)}"
        if self.view[0] == "jam" and tracks:
            collecting = self.jam_wait is not None and self.jam_wait[0] == self.view[1]
            count = "Собираю похожие треки…" if collecting else f"{count} · по треку «{tracks[0].title}», {tracks[0].artist}"
        self.update(viewCount=count,
                    sources=sources, emptyText=empty, libraryActions=actions)

    @Slot(str, str)
    def libraryAction(self, action, arg):
        if action == "play-all" and self.library_model.tracks:
            self.playback.play_tracks(self.library_model.tracks, 0)
        elif action == "rename-playlist":
            names = {number: name for number, name, _ in self.userdata.playlists()}
            self.askName.emit("Переименовать плейлист", names.get(int(arg), ""), "rename-playlist", arg)
        elif action == "delete-playlist":
            names = {number: name for number, name, _ in self.userdata.playlists()}
            self.askConfirm.emit(f"Удалить плейлист «{names.get(int(arg), '')}»? Треки в медиатеке останутся.", "delete-playlist", arg)
        elif action == "clear-source":
            self.askConfirm.emit(f"Удалить из OpenMusic все треки {arg}?", "clear-source", arg)
        elif action == "new-playlist":
            self.pending_tracks = []
            self.askName.emit("Новый плейлист", "", "new-playlist", "")
        elif action in ("play-jam", "refresh-jam", "keep-jam", "delete-jam"):
            tracks = self.userdata.jam_tracks(int(arg))
            if not tracks:
                return
            if action == "play-jam":
                self.playback.play_radio(tracks[0], name=JAM, rest=tracks[1:])
            elif action == "refresh-jam":
                self.start_jam(tracks[0])
            elif action == "keep-jam":
                self.askName.emit("Сохранить джем как плейлист", f"Джем: {tracks[0].title}", "keep-jam", arg)
            else:
                self.userdata.delete_jam(int(arg))
                if self.jam_wait and self.jam_wait[0] == int(arg):
                    self.jam_wait = None
                self.setView("library", -1)
                self.say("Джем удалён")
        elif action == "clear-audio":
            self.askConfirm.emit("Удалить скачанный звук? Треки снова будут скачиваться при включении.", "clear-audio", "")

    @Slot(str, str)
    def confirmed(self, action, arg):
        if action == "delete-playlist":
            self.userdata.delete_playlist(int(arg))
            self.setView("library", -1)
        elif action == "clear-audio":
            removed = 0
            for item in self.playback.audio_files.folder.glob("*.m4a"):
                try:
                    removed += item.stat().st_size
                    item.unlink()
                except OSError:
                    pass
            self.settings_info()
            self.say(f"Скачанный звук удалён, освободилось {self.size_text(removed)}.")
        elif action == "clear-source":
            if self.job:
                self.say("Дождитесь завершения текущего импорта.")
                return
            try:
                self.library.clear(arg)
            except sqlite3.Error:
                self.say("Не удалось удалить данные из медиатеки.", error=True)
                return
            self.refresh()
            self.say(f"Импорт {arg} удалён.")

    @Slot(str, str, str)
    def named(self, action, arg, name):
        name = name.strip()
        if not name:
            return
        if action == "save-preset":
            self.soundSavePreset(name)
            return
        if action == "keep-jam":
            tracks = self.userdata.jam_tracks(int(arg))
            playlist = self.userdata.create_playlist(name)
            self.userdata.add_to_playlist(playlist, tracks)
            self.say(f"Плейлист «{name}» создан, треков: {len(tracks)}")
            self.setView("playlist", playlist)
        elif action == "rename-playlist":
            self.userdata.rename_playlist(int(arg), name)
            self.setView("playlist", int(arg))
        elif action == "new-playlist":
            playlist = self.userdata.create_playlist(name)
            if self.pending_tracks:
                self.userdata.add_to_playlist(playlist, self.pending_tracks)
                self.say(f"Плейлист «{name}» создан, треков: {len(self.pending_tracks)}")
            self.pending_tracks = []
            self.setPage(2)
            self.setView("playlist", playlist)

    @Slot(str)
    def showArtist(self, name):
        """The artist's own page: photo, popular tracks, releases, similar artists."""
        page = self.state["page"]
        if page != ARTIST_PAGE:
            self.artist_return = page
        self.artist.open(name, fresh=page != ARTIST_PAGE)
        self.setPage(ARTIST_PAGE)

    def leave_artist(self):
        self.setPage(self.artist_return if self.artist_return != ARTIST_PAGE else 0)

    @Slot(str)
    def filterArtist(self, name):
        """The library narrowed to the tracks of an artist."""
        self.setPage(2)
        self.setView("library", -1)
        self.source = ""
        self.query = name
        self.querySet.emit(name)
        self.apply_filter()

    # ---- tracks and their menu ----

    def list_of(self, name):
        return {"library": self.library_model.tracks, "search": self.search_model.tracks, "queue": self.playback.queue,
                "home-recent": self.home.lists.get("recent", []), "home-tracks": self.home.lists.get("tracks", []),
                **self.artist.lists()}.get(name, [])

    @Slot(str, int)
    def play(self, name, index):
        tracks = self.list_of(name)
        if not 0 <= index < len(tracks):
            return
        if name == "queue":
            self.playback.play_at(index)
            return
        track = tracks[index]
        if self.playback.is_current(track) and (self.playback.playing or self.playback.loading):
            return
        self.playback.play_tracks(list(tracks), index)

    @Slot(str, int)
    def hover(self, name, index):
        tracks = self.list_of(name)
        if 0 <= index < len(tracks):
            self.playback.hover(tracks[index])

    @Slot(str, int)
    def openMenu(self, name, index):
        tracks = self.list_of(name)
        if not 0 <= index < len(tracks):
            return
        track = tracks[index]
        extras = []
        if name == "library" and self.view[0] == "playlist":
            extras.append(dict(title="Убрать из плейлиста", action="remove-playlist"))
        if name == "queue" and index != self.playback.index:
            extras.append(dict(title="Убрать из очереди", action="remove-queue"))
        self.menuRequested.emit(dict(list=name, index=index, title=track.title, artist=track.artist,
                                     liked=self.userdata.liked(track), source=track.source,
                                     canOpen=bool(track_link(track)), extras=extras,
                                     playlists=[dict(id=number, name=f"{title}  ·  {count}") for number, title, count in self.userdata.playlists()]))

    @Slot(str, int, str, str)
    def trackAction(self, name, index, action, arg):
        tracks = self.list_of(name)
        if not 0 <= index < len(tracks):
            return
        track = tracks[index]
        pb = self.playback
        if action == "play":
            self.play(name, index)
        elif action == "next":
            pb.play_next(track)
            self.say(f"«{track.title}» сыграет следующим")
        elif action == "queue":
            pb.enqueue(track)
            self.say(f"«{track.title}» в очереди")
        elif action == "like":
            self.toggle_like(track)
        elif action == "playlist":
            added = self.userdata.add_to_playlist(int(arg), [track])
            names = {number: title for number, title, _ in self.userdata.playlists()}
            self.say(f"В «{names.get(int(arg), 'плейлист')}» добавлено" if added else "Этот трек уже в плейлисте")
            if self.view == ("playlist", int(arg)):
                self.setView("playlist", int(arg))
        elif action == "new-playlist":
            self.pending_tracks = [track]
            self.askName.emit("Новый плейлист", "", "new-playlist", "")
        elif action in ("jam", "radio"):
            self.start_jam(track)
        elif action == "open":
            self.open_link(track_link(track))
        elif action == "artist":
            self.showArtist(track.artist)
        elif action == "remove-playlist" and self.view[0] == "playlist":
            self.userdata.remove_from_playlist(self.view[1], track)
            self.setView("playlist", self.view[1])
        elif action == "remove-queue":
            pb.remove_at(index)

    def toggle_like(self, track):
        liked = not self.userdata.liked(track)
        self.userdata.set_liked(track, liked)
        self.say(f"«{track.title}» в «Мне нравится»" if liked else f"«{track.title}» убран из «Мне нравится»")
        self.player_changed()
        if self.view[0] == "likes":
            self.setView("likes", -1)
        self.home.rebuild()

    # ---- jams and "Мой поток" ----

    def start_jam(self, track):
        """A jam: the track plays, a list of tracks close to it is collected for the listener, kept
        in the library and played after it; when the list runs out, more are found."""
        if self.jam_wait:
            self.userdata.delete_jam(self.jam_wait[0])      # the one before was still being collected
        self.jam_wait = (self.userdata.save_jam([track]), track)
        self.playback.play_radio(track, name=JAM, first=JAM_SIZE - 1)
        self.setPage(2)
        self.setView("jam", self.jam_wait[0])
        self.say(f"Собираю джем по треку «{track.title}» — несколько секунд")

    def pick_similar(self, seed, count, skip):
        """Tracks close to the seed, for the radio; called on its thread."""
        flow = self.playback.radio_name == FLOW
        picks = self.similar.tracks(seed, count=FLOW_NEW if flow else count, skip=set(skip) | self.skipped_songs,
                                    taste=self.taste, avoid=self.avoid)
        for pick in picks:
            if pick.artwork:
                self.artworks[(pick.track.artist, pick.track.title)] = pick.artwork
        found = [pick.track for pick in picks]
        if flow:
            # One more of the listener's own tracks in between, by an artist of this batch if there is one.
            taken = set(skip) | self.skipped_songs | {song(seed)} | {song(track) for track in found}
            mine = [track for track in self.tracks if song(track) not in taken]
            artists = {similar.voice(similar.main_artist(similar.names_of(track)[0])) for track in [seed, *found]}
            close = [track for track in mine if similar.voice(similar.main_artist(track.artist)) in artists]
            if mine:
                found.insert(min(2, len(found)), random.choice(close or mine))
        return found

    def read_dislikes(self):
        """Which artists and songs the listener keeps switching off. An artist they have in the
        library or listen to is given that much credit first."""
        since = time.time() - TASTE_DAYS * 24 * 3600

        def artist(track):
            return similar.voice(similar.main_artist(similar.names_of(track)[0]))
        liked = {name: 2 for name in self.taste}
        for when, track, _ in self.userdata.history(3000):
            if when >= since:
                liked[artist(track)] = liked.get(artist(track), 0) + 1
        skips, songs = {}, {}
        for track, count in self.userdata.skips(since):
            skips[artist(track)] = skips.get(artist(track), 0) + count
            songs[song(track)] = songs.get(song(track), 0) + count
        self.avoid = {name: count - liked.get(name, 0) for name, count in skips.items() if count > liked.get(name, 0)}
        self.skipped_songs = {name for name, count in songs.items() if count >= 2}

    def skipped(self, track):
        self.userdata.skipped(track)
        self.read_dislikes()
        artist = similar.voice(similar.main_artist(similar.names_of(track)[0]))
        if self.playback.radio and self.avoid.get(artist, 0) >= 2:
            self.playback.drop_ahead(artist)

    # ---- the mixes of the home screen ----

    def make_mixes(self):
        """Mixes made of circles of artists that go together. What was built for these artists is
        taken from disk; when it is older than a week or there is none, it is built on a thread,
        which takes a minute of asking Deezer."""
        if not self.tracks:
            return
        path = self.folder / "cache" / "mixes.json"
        try:
            built = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            built = None
        ours = isinstance(built, dict) and built.get("signature") == mixes.signature(self.tracks)
        if ours:
            self.show_mixes(built)
        if (ours and time.time() - built.get("at", 0) < MIXES_KEEP) or self.mixing:
            return
        self.mixing = True
        tracks = list(self.tracks)

        def work():
            try:
                built = mixes.build(tracks, lambda: not isValid(self) or self.closing)
            except Exception:
                built = None
            if built:
                built["at"] = time.time()
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(built, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
            if isValid(self):
                self.mixesReady.emit(built)
        threading.Thread(target=work, daemon=True).start()

    def mixes_built(self, built):
        self.mixing = False
        if built and built.get("signature") == mixes.signature(self.tracks):
            self.show_mixes(built)

    def show_mixes(self, built):
        import datetime
        made = []
        for number, (tracks, names, artwork) in enumerate(mixes.arrange(built, datetime.date.today().toordinal()), start=1):
            for track in tracks:
                picture = artwork.get((track.artist, track.title))
                if picture and covers.STORE:
                    covers.STORE.want([track], url=picture)
            made.append((number, tracks, ", ".join(names[:2]) + (" и др." if len(names) > 2 else "")))
        self.home.set_mixes(made)

    def renew_sound(self):
        """Sound that was found by the rule before the present one is looked for again in the
        background; a file downloaded from an upload that lost goes, so the track is fetched anew."""
        if not self.resolver.outdated():
            return
        files = self.playback.audio_files

        def changed(artist, title):
            current = self.playback.current
            if current is None or stream.track_name(current.artist, current.title) != stream.track_name(artist, title):
                files.path(artist, title).unlink(missing_ok=True)

        def work():
            try:
                self.resolver.renew(changed, lambda: not isValid(self) or self.closing)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def radio_grew(self, seed, tracks, problem):
        store = covers.STORE
        for track in tracks:
            if store:
                store.want([track], url=self.artworks.pop((track.artist, track.title), ""))
        pb = self.playback
        if self.jam_wait and seed is self.jam_wait[1]:
            number = self.jam_wait[0]
            self.jam_wait = None
            found = [track for track in tracks if track is not seed]
            if found:
                number = self.userdata.save_jam([seed, *found])
                self.say(f"Джем готов: {plural(len(found) + 1, ('трек', 'трека', 'треков'))}")
                if self.view[0] == "jam":
                    self.setView("jam", number)
            else:
                self.userdata.delete_jam(number)
                if self.view[0] == "jam":
                    self.setView("library", -1)
                self.say(problem or "Похожих треков не нашлось.", error=True)
        elif problem and not tracks and len(pb.queue) <= 1:
            self.say(problem, error=True)

    def flow_seeds(self, count=12):
        """What "Мой поток" grows from: a dozen of the listener's tracks, each by another artist.
        A liked track is three times as likely to be taken as one that merely is in the library,
        one listened to more than once twice as likely."""
        weights = {}

        def add(tracks, weight):
            for track in tracks:
                name = userdata.track_key(track)
                if song(track) in self.skipped_songs:
                    continue
                if self.avoid.get(similar.voice(similar.main_artist(similar.names_of(track)[0])), 0):
                    weight = weight * 0.4
                weights[name] = (track, max(weight, weights.get(name, (track, 0))[1]))
        add(self.tracks, 1.0)
        add([track for track, plays, listened in self.userdata.top_tracks(limit=60) if plays >= 2 or listened >= 90_000], 2.0)
        add(self.userdata.likes(), 3.0)
        order = sorted(weights.values(), key=lambda pair: -random.random() ** (1 / pair[1]))
        seeds, artists = [], set()
        for track, _ in order:
            artist = similar.voice(similar.main_artist(similar.names_of(track)[0]))
            if artist not in artists:
                artists.add(artist)
                seeds.append(track)
                if len(seeds) == count:
                    break
        return seeds

    @Slot()
    def radioFromTaste(self):
        pb = self.playback
        if pb.radio and pb.radio_name == FLOW and pb.current:
            pb.toggle()
            return
        seeds = self.flow_seeds()
        if not seeds:
            self.window and self.window.setProperty("importOpen", True)
            return
        # Each of the listener's tracks brings a few close to it, then the next one takes over.
        pb.play_radio(seeds[0], seeds=seeds, first=FLOW_NEW + 1, batch=FLOW_NEW + 1)
        self.say("Мой поток: ваши треки и похожие на них")

    def heard(self, track, listened):
        self.userdata.played(track, listened)
        self.home.show_recent(self.userdata.recent())

    def open_link(self, url):
        if url and not QDesktopServices.openUrl(QUrl(url)):
            self.say("Не удалось открыть ссылку в браузере.", error=True)

    # ---- player ----

    def player_changed(self):
        pb = self.playback
        track = pb.current
        if track:
            title = track.title
            if pb.loading:
                caption = f"{track.artist} · ищу звук…"
            elif pb.source:
                caption = f"{track.artist} · {'с диска' if track.url.startswith('file://') else 'SoundCloud'}"
            else:
                caption = track.artist
            cover, colour = urls.cover(track), urls.colour(track)
            artist = track.artist
        elif pb.local:
            path = Path(pb.local)
            title, caption, cover, colour = path.stem, path.suffix.lstrip(".").upper(), "", "#a0a0a0"
            artist = ""
        else:
            title, caption, cover, colour = "Ничего не играет", "Нажмите на трек, чтобы послушать", "", "#a0a0a0"
            artist = ""
        sleep = ""
        if pb.sleep_at > 0:
            sleep = f"Сон через {int((pb.sleep_at - time.monotonic()) / 60) + 1} мин"
        elif pb.sleep_at < 0:
            sleep = "Сон после трека"
        self.player.update(hasTrack=bool(track or pb.local), title=title, artist=artist, caption=caption, cover=cover, colour=colour,
                           playing=pb.playing, loading=pb.loading, liked=bool(track and self.userdata.liked(track)),
                           shuffle=pb.shuffle, repeat=pb.repeat, radio=pb.radio, queueIndex=pb.index,
                           canNext=pb.index + 1 < len(pb.queue) or (pb.repeat == "all" and bool(pb.queue)),
                           volume=pb.audio.volume(), speed=pb.engine.speed if pb.engine.available else pb.media.playbackRate(),
                           sleep=sleep)
        if [id(track) for track in self.queue_model.tracks] != [id(track) for track in pb.queue]:
            self.queue_model.replace(pb.queue)
        else:
            self.queue_model.refresh(("current",))
        left = max(0, len(pb.queue) - pb.index - 1)
        self.update(queueCaption=f"Дальше {plural(left, ('трек', 'трека', 'треков'))}" + (f" · {pb.radio_name} добавляет треки сам" if pb.radio else ""))
        self.library_model.refresh(("current",))
        self.search_model.refresh(("current",))
        for model in self.artist.models():
            model.refresh(("current",))
        self.home.set_streaming(pb.radio and pb.radio_name == FLOW and pb.playing)
        self.load_wave()
        self.playerChanged.emit()
        self.island.sync()
        self.tray.sync()
        self.mpris.changed()

    def time_changed(self, *_):
        self.time.update(position=self.playback.media.position(), duration=self.playback.media.duration())
        self.timeChanged.emit()

    def load_wave(self):
        track = self.playback.current
        disk = on_disk(track) if track else None
        ready = bool(track and (disk or self.playback.audio_files.has(track.artist, track.title)))
        wanted = (id(track), ready)
        if wanted == self.wave_for:
            return
        self.wave_for = wanted
        self.player["wave"] = []
        if not ready:
            return
        path = disk or self.playback.audio_files.path(track.artist, track.title)
        store = urls.CACHE / "peaks" if disk else None

        def work():
            import waveform
            values = waveform.peaks(path, 160, store)
            if values and isValid(self):
                self.waveReady.emit(track, values)
        threading.Thread(target=work, daemon=True).start()

    def wave_arrived(self, track, values):
        if track is self.playback.current:
            self.player["wave"] = values
            self.playerChanged.emit()

    def covers_landed(self):
        for model in (self.library_model, self.search_model, self.queue_model, *self.artist.models()):
            model.refresh(("cover", "colour"))
        self.home.update_covers()
        if self.playback.current:
            self.player.update(cover=urls.cover(self.playback.current), colour=urls.colour(self.playback.current))
            self.playerChanged.emit()

    @Slot()
    def toggle(self):
        self.playback.toggle()

    @Slot()
    def next(self):
        self.playback.next()

    @Slot()
    def previous(self):
        self.playback.previous()

    @Slot(int)
    def seek(self, position):
        position = max(0, int(position))
        if self.playback.source is None and self.playback.current and not self.playback.loading:
            # The track put back from the last session: it will start from here.
            self.playback.resume_at = position
            self.time["position"] = position
            self.timeChanged.emit()
        else:
            self.playback.media.setPosition(position)
        self.mpris.seeked(position)

    @Slot(float)
    def setVolume(self, value):
        self.playback.audio.setVolume(value)
        self.player["volume"] = value
        self.playerChanged.emit()
        self.volume_saver.start()

    @Slot()
    def likeCurrent(self):
        if self.playback.current:
            self.toggle_like(self.playback.current)

    @Slot()
    def toggleShuffle(self):
        self.playback.set_shuffle(not self.playback.shuffle)

    @Slot()
    def cycleRepeat(self):
        self.playback.cycle_repeat()

    @Slot(float)
    def setSpeed(self, rate):
        self.playback.set_speed(rate)
        self.sound_state()

    @Slot(int)
    def sleepIn(self, minutes):
        self.playback.sleep_in(minutes)

    @Slot()
    def openFile(self):
        path, _ = QFileDialog.getOpenFileName(None, "Открыть аудиофайл", "", "Аудио (*.mp3 *.flac *.ogg *.opus *.wav *.m4a *.aac);;Все файлы (*)")
        if path:
            self.playback.play_file(path)

    # ---- search ----

    @Slot(str)
    def search(self, text):
        self.search_text = text.strip()
        words = key(self.search_text).split()
        self.search_local = [track for track in self.tracks if words and all(word in key(f"{track.title} {track.artist}") for word in words)][:15]
        self.search_model.replace(self.search_local)
        self.update(searchStatus=("Ищу на SoundCloud…" if len(self.search_text) >= 2 else
                                  "Начните вводить — найдётся всё, что есть на SoundCloud."))
        self.search_timer.start()

    def search_online(self):
        if len(self.search_text) >= 2:
            self.online.ask(self.search_text)

    def search_arrived(self, query, found, problem):
        if query != self.search_text:
            return
        seen = {(key(track.title), key(track.artist)) for track in self.search_local}
        remote = []
        for track, duration, artwork in found:
            if (key(track.title), key(track.artist)) in seen:
                continue
            remote.append(track)
            if artwork:
                covers.STORE.want([track], url=artwork)
        self.search_model.replace(self.search_local + remote)
        parts = []
        if self.search_local:
            parts.append(f"в медиатеке {len(self.search_local)}")
        if remote:
            parts.append(f"на SoundCloud {len(remote)}")
        self.update(searchStatus=problem or (("Найдено: " + ", ".join(parts)) if parts else "Ничего не нашлось."))

    # ---- import ----

    def import_sources(self):
        result = []
        for source in IMPORT_SOURCES:
            item = dict(source)
            item["icon"] = urls.icon(source["glyph"])
            item["steps"] = list(source["steps"])
            secondary = source.get("secondary")
            item["secondaryTitle"], item["secondaryKind"] = (secondary or ("", ""))
            item.pop("secondary", None)
            item.setdefault("field", "")
            item.setdefault("note", "")
            result.append(item)
        return result

    @Slot(str, str)
    def importChoose(self, kind, value):
        value = value.strip()
        names = {"deezer": ("Deezer", jobs.deezer_link), "yandex": ("Яндекс Музыка", jobs.yandex_link),
                 "apple": ("Apple Music", jobs.apple_link), "youtube": ("YouTube", jobs.youtube_playlist)}
        if kind == "spotify-request":
            self.open_link(jobs.SPOTIFY_PRIVACY)
        elif kind == "computer":
            self.start_import("Файлы", scan.computer(self.library))
        elif kind == "spotify-link":
            self.start_import("Spotify", jobs.spotify_playlist(self.library, value))
        elif kind == "soundcloud":
            self.start_import("SoundCloud", jobs.soundcloud_likes(self.library, value))
        elif kind in names:
            self.start_import(names[kind][0], names[kind][1](self.library, value))
        elif kind == "spotify-files":
            paths, _ = QFileDialog.getOpenFileNames(None, "Выберите экспорт Spotify", "", "Архив или данные Spotify (*.zip *.json)")
            if paths:
                self.start_import("Spotify", jobs.files(self.library, paths, "Spotify"))
        elif kind == "m3u":
            paths, _ = QFileDialog.getOpenFileNames(None, "Плейлист M3U", "", "Плейлисты (*.m3u *.m3u8)")
            if paths:
                self.start_import("Файлы", jobs.m3u_files(self.library, paths))
        elif kind == "folder":
            folder = QFileDialog.getExistingDirectory(None, "Папка с музыкой")
            if folder:
                self.start_import("Файлы", jobs.music_folder(self.library, folder))
        elif kind == "csv":
            paths, _ = QFileDialog.getOpenFileNames(None, "CSV с колонками title, artist и необязательной url", "", "Таблицы CSV (*.csv)")
            if paths:
                self.start_import("CSV", jobs.files(self.library, paths, "CSV"))

    def start_import(self, source, operation):
        if self.job is not None:
            self.say("Дождитесь завершения текущего импорта.")
            return
        self.say(f"Импорт из {source}…", sticky=True)
        self.job = jobs.ImportJob(operation, self)
        self.job.imported.connect(self.finish_import)
        self.job.progress.connect(lambda message: self.say(message, sticky=True))
        self.job.failed.connect(lambda message: self.say(message, error=True))
        self.job.finished.connect(self.release_job)
        self.job.start()

    def finish_import(self, result):
        self.say(result)
        self.refresh()

    def release_job(self):
        self.job.deleteLater()
        self.job = None
        if self.closing:
            self.requestClose()

    @Slot(result=bool)
    def requestClose(self):
        """The window's cross: hides into the tray when that is chosen, otherwise ends the app once
        the import running has stopped."""
        if not self.quitting and not self.closing and self.settings["closeToTray"] and self.tray.shown:
            self.was_maximized = bool(self.window and self.window.visibility() == QWindow.Visibility.Maximized)
            QTimer.singleShot(0, self.window.hide)
            self.tray.tell_hidden()
            return False
        if self.job is not None:
            self.closing = True
            self.job.requestInterruption()
            self.say("Завершение текущего импорта…", sticky=True)
            return False
        self.save_session()
        self.volume_saver.isActive() and self.settings.set("volume", round(float(self.player["volume"]), 3))
        QTimer.singleShot(0, QApplication.quit)
        return True

    @Slot()
    def quitApp(self):
        self.quitting = True
        self.requestClose()

    @Slot(int)
    def showWindow(self, page=-1):
        window = self.window
        if not window:
            return
        if page >= 0:
            self.setPage(page)
        if not window.isVisible():
            window.showMaximized() if self.was_maximized else window.show()
        elif window.visibility() == QWindow.Visibility.Minimized:
            window.showNormal()
        window.raise_()
        window.requestActivate()

    @Slot()
    def toggleWindow(self):
        window = self.window
        if window and window.isVisible() and window.visibility() != QWindow.Visibility.Minimized and window.isActive():
            self.was_maximized = window.visibility() == QWindow.Visibility.Maximized
            window.hide()
        else:
            self.showWindow(-1)

    # ---- the last session ----

    def save_session(self):
        pb = self.playback
        path = self.folder / "session.json"
        if not pb.queue or not 0 <= pb.index < len(pb.queue):
            path.unlink(missing_ok=True)
            return
        start = max(0, pb.index - 100)
        tracks = pb.queue[start:start + 400]
        position = pb.resume_at if pb.source is None else pb.media.position()
        duration = self.time["duration"]
        if duration and position > duration - 5000:
            position = 0
        data = dict(tracks=[dict(title=t.title, artist=t.artist, source=t.source, url=t.url) for t in tracks],
                    index=pb.index - start, position=int(max(0, position)), duration=int(duration),
                    shuffle=pb.shuffle, repeat=pb.repeat)
        try:
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def restore_session(self):
        try:
            data = json.loads((self.folder / "session.json").read_text(encoding="utf-8"))
            tracks = [Track(item["title"], item["artist"], item["source"], item["url"]) for item in data["tracks"]]
            index, position, duration = int(data["index"]), int(data["position"]), int(data.get("duration", 0))
        except (OSError, ValueError, KeyError, TypeError):
            return
        pb = self.playback
        pb.shuffle = bool(data.get("shuffle", False))
        pb.repeat = data.get("repeat", "off") if data.get("repeat") in ("off", "all", "one") else "off"
        self.time.update(position=position, duration=duration)
        pb.restore(tracks, index, position)

    # ---- settings ----

    @Slot(str, "QVariant")
    def setSetting(self, name, value):
        if not self.settings.set(name, value):
            return
        if name == "tray" and not value:
            self.settings.set("closeToTray", False)
        if name == "closeToTray" and value:
            self.settings.set("tray", True)
        if name == "cacheMb":
            audio = self.playback.audio_files
            audio.LIMIT = self.settings["cacheMb"] * MB
            threading.Thread(target=audio.trim, daemon=True).start()
            QTimer.singleShot(400, self.settings_info)
        self.island.sync()
        self.tray.sync()
        self.settingsChanged.emit()

    @staticmethod
    def size_text(size):
        if size >= 1000 * MB:
            return f"{size / 1000 / MB:.1f} ГБ".replace(".", ",").replace(",0 ", " ")
        return f"{round(size / MB)} МБ"

    def menu_entry(self):
        return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.ApplicationsLocation)) / "OpenMusic.desktop"

    @Slot()
    def addToMenu(self):
        path = self.menu_entry()
        text = "\n".join(["[Desktop Entry]", "Type=Application", "Name=OpenMusic", "GenericName=Музыкальный плеер",
                          "Comment=Ваша музыка из Spotify, SoundCloud и других сервисов",
                          f'Exec=python3 "{ROOT / "app.py"}"', f"Path={ROOT}", f"Icon={ROOT / 'assets' / 'icon.png'}",
                          "Terminal=false", "Categories=AudioVideo;Audio;Player;", "StartupWMClass=OpenMusic", ""])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError:
            self.say("Не удалось добавить OpenMusic в меню приложений.", error=True)
            return
        self.update(menuEntry=True)
        self.say("OpenMusic теперь есть в меню приложений.")

    def settings_info(self):
        """What the settings screen shows besides the switches: the listening statistics and the cache."""
        audio = self.playback.audio_files
        used = 0
        for item in audio.folder.glob("*.m4a"):
            try:
                used += item.stat().st_size
            except OSError:
                pass
        limit = self.settings["cacheMb"] * MB
        self.update(cache=dict(used=self.size_text(used), share=min(1.0, used / limit) if limit else 0.0, limit=self.size_text(limit)),
                    stats=self.stats(), menuEntry=self.menu_entry().exists(), islandAvailable=self.island.available)

    def stats(self):
        data = self.userdata
        now = time.time()
        periods = []
        for title, seconds in (("7 дней", 7 * 86400), ("30 дней", 30 * 86400), ("Всё время", 0)):
            ms, plays, tracks = data.totals(now - seconds if seconds else 0)
            periods.append(dict(title=title, time=listening(ms) if ms >= 60000 else ("меньше минуты" if ms else "—"),
                                plays=plural(plays, ("прослушивание", "прослушивания", "прослушиваний")),
                                tracks=plural(tracks, ("трек", "трека", "треков"))))
        month = now - 30 * 86400
        artists = data.stats(month)[:5]
        top = max((ms for _, ms, _ in artists), default=0) or 1
        top_artists = [dict(name=name, time=listening(ms), share=ms / top, picture=urls.artist(name),
                            plays=plural(plays, ("раз", "раза", "раз"))) for name, ms, plays in artists]
        top_tracks = [dict(title=track.title, artist=track.artist, cover=urls.cover(track),
                           plays=plural(plays, ("раз", "раза", "раз"))) for track, plays, _ in data.top_tracks(month, 5)]
        return dict(empty=not data.totals(0)[1], periods=periods, artists=top_artists, tracks=top_tracks,
                    likes=len(data.likes()), playlists=len(data.playlists()), library=len(self.tracks))

    # ---- queue ----

    @Slot(int)
    def queuePlay(self, index):
        self.playback.play_at(index)

    # ---- sound ----

    def sound_state(self):
        engine = self.playback.engine
        from .sound_panel import SCENES
        try:
            import effects
            groups = [dict(name=name, presets=list(names)) for name, names in effects.GROUPS.items()]
            spaces = list(effects.SPACES)
        except ImportError:
            groups, spaces = [], []
        sound = dict(engine.settings)
        custom = sound.pop("custom", None) or {}
        if custom:
            groups.append(dict(name="Свои", presets=list(custom)))
        sound["custom"] = list(custom)
        sound["bands"] = [float(value) for value in (sound.get("bands") or [0] * 10)]
        try:
            sound["freqs"] = [float(value) for value in effects.centres(len(sound["bands"]))]
        except NameError:
            sound["freqs"] = []
        sound["speed"] = engine.speed if engine.available else self.playback.media.playbackRate()
        sound["available"] = engine.available
        self.update(sound=sound, presets=[name for group in groups for name in group["presets"]], presetGroups=groups,
                    spaces=spaces, scenes=[dict(name=name, about=scene.get("about", "")) for name, scene in SCENES.items()])

    @Slot(str, "QVariant")
    def soundSet(self, name, value):
        self.playback.engine.update(**{name: value})
        self.sound_state()

    @Slot("QVariantList")
    def soundBands(self, values):
        self.playback.engine.update(bands=[float(value) for value in values], preset="Свой")
        self.sound_state()

    @Slot(str)
    def soundPreset(self, name):
        import effects
        engine = self.playback.engine
        count = len(engine.settings.get("bands") or []) or 10
        if name in effects.PRESETS:
            # A ready-made curve is drawn on as many bands as the listener has chosen.
            bands = effects.refit(effects.PRESETS[name], count)
        else:
            # One of the listener's own comes back exactly as it was saved, bands and all.
            bands = (engine.settings.get("custom") or {}).get(name)
        if bands:
            engine.update(preset=name, bands=[float(value) for value in bands])
            self.sound_state()

    @Slot(int)
    def soundLayout(self, count):
        """The same curve on 5, 10, 15 or 31 bands."""
        import effects
        engine = self.playback.engine
        if count not in effects.LAYOUTS:
            return
        bands = effects.refit(engine.settings.get("bands") or [0.0] * 10, count)
        engine.update(bands=bands, preset=engine.settings.get("preset"), scene=engine.settings.get("scene"))
        self.sound_state()

    @Slot()
    def soundAuto(self):
        """Fits the equalizer to the track that plays: evens out its balance of low and high."""
        engine = self.playback.engine
        count = len(engine.settings.get("bands") or []) or 10
        bands = engine.auto_bands(count) if engine.available else None
        if not bands:
            self.say("Включите трек и дайте ему поиграть пару секунд — тогда подстрою эквалайзер под него.", error=True)
            return
        engine.update(bands=bands, preset="Авто")
        self.sound_state()
        self.say("Эквалайзер подстроен под этот трек")

    @Slot(str)
    def soundSavePreset(self, name):
        """Keeps the bands as they are now under a name of the listener's own."""
        import effects
        name = name.strip()[:40]
        if not name or name in effects.PRESETS:
            self.say("Это имя у готового пресета — выберите другое." if name else "Нужно имя пресета.", error=True)
            return
        engine = self.playback.engine
        custom = dict(engine.settings.get("custom") or {})
        custom[name] = [float(value) for value in engine.settings.get("bands") or [0.0] * 10]
        engine.update(custom=custom, preset=name)
        self.sound_state()
        self.say(f"Пресет «{name}» сохранён")

    @Slot(str)
    def soundDeletePreset(self, name):
        engine = self.playback.engine
        custom = dict(engine.settings.get("custom") or {})
        if custom.pop(name, None) is not None:
            engine.update(custom=custom, preset="Свой" if engine.settings.get("preset") == name else engine.settings.get("preset"))
            self.sound_state()
            self.say(f"Пресет «{name}» удалён")

    @Slot()
    def askPresetName(self):
        self.askName.emit("Сохранить пресет эквалайзера", "", "save-preset", "")

    @Slot()
    def soundReset(self):
        """Everything of the sound panel back as it was at the start."""
        engine = self.playback.engine
        custom = engine.settings.get("custom") or {}
        values = engine.defaults()
        values["custom"] = custom
        engine.update(**values)
        self.playback.set_speed(1.0)
        self.sound_state()

    @Slot(bool)
    def soundWatch(self, on):
        """The analyser runs only while the sound panel is open."""
        self.playback.engine.watching = on
        if on:
            self.analyser.start()
        else:
            self.analyser.stop()
            self.playback.engine.recent = None
            self.bands_now = [0.0] * 48
            self.spectrumChanged.emit()

    def analyse(self):
        self.bands_now = self.playback.engine.spectrum(48) if self.playback.playing else [0.0] * 48
        self.spectrumChanged.emit()

    @Slot(str)
    def soundScene(self, name):
        import effects
        from .sound_panel import NEUTRAL, SCENES
        if name not in SCENES:
            return
        scene = {**NEUTRAL, **SCENES[name]}
        scene.pop("about", None)
        preset = scene.pop("preset")
        speed = scene.pop("speed")
        engine = self.playback.engine
        count = len(engine.settings.get("bands") or []) or 10
        engine.update(preset=preset, bands=effects.refit(effects.PRESETS[preset], count), enabled=True, **scene)
        self.playback.set_speed(speed)
        engine.update(scene=name)
        self.sound_state()
