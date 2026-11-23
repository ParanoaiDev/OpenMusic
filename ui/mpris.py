"""MPRIS: how Linux desktops talk to music players. With it KDE's player widget, the lock screen,
the media keys of any keyboard and KDE Connect on a phone show and control what OpenMusic plays.
QtDBus does the talking; the two interfaces are adaptors on one object at /org/mpris/MediaPlayer2."""
import hashlib

from PySide6.QtCore import ClassInfo, Property, QMetaType, QObject, Signal, Slot
from PySide6.QtDBus import QDBusAbstractAdaptor, QDBusArgument, QDBusConnection, QDBusMessage, QDBusObjectPath

PATH = "/org/mpris/MediaPlayer2"
ROOT = "org.mpris.MediaPlayer2"
PLAYER = ROOT + ".Player"
NAME = ROOT + ".openmusic"
NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"


@ClassInfo({"D-Bus Interface": ROOT})
class RootAdaptor(QDBusAbstractAdaptor):
    def __init__(self, holder, app):
        super().__init__(holder)
        self.app = app

    CanQuit = Property(bool, lambda self: True)
    CanRaise = Property(bool, lambda self: True)
    HasTrackList = Property(bool, lambda self: False)
    Identity = Property(str, lambda self: "OpenMusic")
    DesktopEntry = Property(str, lambda self: "OpenMusic")
    SupportedUriSchemes = Property("QStringList", lambda self: ["file"])
    SupportedMimeTypes = Property("QStringList", lambda self: ["audio/mpeg", "audio/flac", "audio/ogg", "audio/mp4", "audio/x-wav"])

    @Slot()
    def Raise(self):
        self.app.showWindow(-1)

    @Slot()
    def Quit(self):
        self.app.quitApp()


@ClassInfo({"D-Bus Interface": PLAYER})
class PlayerAdaptor(QDBusAbstractAdaptor):
    Seeked = Signal("qlonglong")

    def __init__(self, holder, mpris):
        super().__init__(holder)
        self.mpris = mpris
        self.app = mpris.app

    def get(name):
        return lambda self: self.mpris.values()[name]

    def set_loop(self, value):
        wanted = {"None": "off", "Playlist": "all", "Track": "one"}.get(value)
        playback = self.app.playback
        while wanted and playback.repeat != wanted:
            playback.cycle_repeat()

    def set_shuffle(self, value):
        self.app.playback.set_shuffle(bool(value))

    def set_rate(self, value):
        if 0.5 <= value <= 2.0:
            self.app.setSpeed(float(value))

    def set_volume(self, value):
        self.app.setVolume(max(0.0, min(1.0, float(value))))

    PlaybackStatus = Property(str, get("PlaybackStatus"))
    LoopStatus = Property(str, get("LoopStatus"), set_loop)
    Rate = Property(float, get("Rate"), set_rate)
    Shuffle = Property(bool, get("Shuffle"), set_shuffle)
    Metadata = Property("QVariantMap", get("Metadata"))
    Volume = Property(float, get("Volume"), set_volume)
    Position = Property("qlonglong", lambda self: self.mpris.position())
    MinimumRate = Property(float, lambda self: 0.5)
    MaximumRate = Property(float, lambda self: 2.0)
    CanGoNext = Property(bool, get("CanGoNext"))
    CanGoPrevious = Property(bool, get("CanGoPrevious"))
    CanPlay = Property(bool, get("CanPlay"))
    CanPause = Property(bool, get("CanPause"))
    CanSeek = Property(bool, get("CanSeek"))
    CanControl = Property(bool, lambda self: True)
    del get

    @Slot()
    def Next(self):
        self.app.next()

    @Slot()
    def Previous(self):
        self.app.previous()

    @Slot()
    def Pause(self):
        if self.app.playback.playing:
            self.app.toggle()

    @Slot()
    def Play(self):
        if not self.app.playback.playing:
            self.app.toggle()

    @Slot()
    def PlayPause(self):
        self.app.toggle()

    @Slot()
    def Stop(self):
        self.Pause()

    @Slot("qlonglong")
    def Seek(self, offset):
        self.app.seek(int(self.app.playback.media.position() + offset / 1000))

    @Slot(QDBusObjectPath, "qlonglong")
    def SetPosition(self, track, position):
        if track.path() == self.mpris.track_id() and position >= 0:
            self.app.seek(int(position / 1000))

    @Slot(str)
    def OpenUri(self, uri):
        from PySide6.QtCore import QUrl
        path = QUrl(uri).toLocalFile()
        if path:
            self.app.playback.play_file(path)


class Mpris(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.holder = QObject(self)
        self.root = RootAdaptor(self.holder, app)
        self.player = PlayerAdaptor(self.holder, self)
        self.sent = {}
        bus = QDBusConnection.sessionBus()
        self.bus = bus
        self.ok = bool(bus.isConnected() and bus.registerObject(PATH, self.holder, QDBusConnection.RegisterOption.ExportAdaptors)
                       and bus.registerService(NAME))

    def track_id(self):
        playback = self.app.playback
        track = playback.current
        if track is None:
            return NO_TRACK if not playback.local else "/org/openmusic/track/file"
        return "/org/openmusic/track/t" + hashlib.blake2b(f"{track.artist}\n{track.title}".encode("utf-8"), digest_size=8).hexdigest()

    def position(self):
        return int(max(0, self.app.playback.media.position()) * 1000)

    def values(self):
        app, playback = self.app, self.app.playback
        player = app.player
        has = player["hasTrack"]
        status = "Playing" if playback.playing or (playback.loading and has) else ("Paused" if has else "Stopped")
        metadata = {"mpris:trackid": QDBusObjectPath(self.track_id())}
        if has:
            metadata["xesam:title"] = player["title"]
            if player.get("artist"):
                metadata["xesam:artist"] = [player["artist"]]
            if player["cover"]:
                metadata["mpris:artUrl"] = player["cover"]
            duration = app.time["duration"]
            if duration > 0:
                metadata["mpris:length"] = int(duration) * 1000
            if playback.current is not None and playback.current.url.startswith("http"):
                metadata["xesam:url"] = playback.current.url
        return {
            "PlaybackStatus": status,
            "LoopStatus": {"off": "None", "all": "Playlist", "one": "Track"}[playback.repeat],
            "Rate": float(player["speed"]),
            "Shuffle": bool(playback.shuffle),
            "Metadata": metadata,
            "Volume": float(player["volume"]),
            "CanGoNext": bool(player["canNext"]),
            "CanGoPrevious": bool(has),
            "CanPlay": bool(has),
            "CanPause": bool(has),
            "CanSeek": bool(has and app.time["duration"] > 0),
        }

    @staticmethod
    def comparable(value):
        if isinstance(value, dict):
            return {name: Mpris.comparable(item) for name, item in value.items()}
        if isinstance(value, QDBusObjectPath):
            return value.path()
        return value

    def changed(self):
        """Tells the desktop what changed since the last time."""
        if not self.ok:
            return
        values = self.values()
        fresh = {name: value for name, value in values.items()
                 if self.comparable(value) != self.comparable(self.sent.get(name))}
        if not fresh:
            return
        self.sent = values
        message = QDBusMessage.createSignal(PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged")
        nothing = QDBusArgument()       # an empty list of strings: a plain empty list would go as the wrong type
        nothing.beginArray(QMetaType(QMetaType.Type.QString))
        nothing.endArray()
        message.setArguments([PLAYER, fresh, nothing])
        self.bus.send(message)

    def seeked(self, milliseconds=None):
        if self.ok:
            self.player.Seeked.emit(int(milliseconds * 1000) if milliseconds is not None else self.position())
