"""Imports run off the window thread. Each function returns the operation an ImportJob runs:
operation(cancelled, report) -> a line telling the user what was imported."""
import sqlite3

from PySide6.QtCore import QThread, Signal

import apple
import deezer
import local
import soundcloud
import spotify
import yandex
import youtube
from library import ImportFailed

SPOTIFY_PRIVACY = "https://www.spotify.com/account/privacy/"


class ImportJob(QThread):
    imported = Signal(str)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            result = self.operation(self.isInterruptionRequested, self.progress.emit)
            if not self.isInterruptionRequested():
                self.imported.emit(result)
        except ImportFailed as error:
            self.failed.emit(str(error))
        except (OSError, sqlite3.Error):
            self.failed.emit("Не удалось прочитать или сохранить данные. Проверьте доступ к файлам.")


def spotify_playlist(library, link):
    def run(cancelled, report):
        name, entries = spotify.playlist(link)
        count = library.import_entries(entries, "Spotify")
        limit = f" Это первые {count}: остальные Spotify без входа не показывает." if len(entries) >= spotify.VISIBLE_TRACKS else ""
        return f"Spotify · «{name}» · треков добавлено: {count}.{limit}"
    return run


def soundcloud_likes(library, link):
    def run(cancelled, report):
        known = {soundcloud.uploader(track.url): track.artist for track in library.tracks() if track.source == "SoundCloud"}
        known = {name: shown for name, shown in known.items() if shown != name}
        entries = soundcloud.likes(link, cancelled, report, known)
        count = library.import_entries(entries, "SoundCloud", replace=True)
        return f"SoundCloud · лайков загружено: {count}"
    return run


def files(library, paths, source):
    def run(cancelled, report):
        return f"{source} · записей обработано: {library.import_files(paths, source)}"
    return run


def by_link(library, source, fetch):
    """The operation for a playlist or album fetched by link: fetch(cancelled, report) gives its name and tracks."""
    def run(cancelled, report):
        report(f"{source} · читаю список треков…")
        name, entries = fetch(cancelled, report)
        if cancelled():
            raise ImportFailed("Импорт отменён.")
        return f"{source} · «{name}» · треков добавлено: {library.import_entries(entries, source)}"
    return run


def deezer_link(library, link):
    """A public Deezer playlist or album."""
    return by_link(library, "Deezer", lambda cancelled, report: deezer.tracks(link, cancelled, report))


def yandex_link(library, link):
    """A public Yandex Music playlist or album."""
    return by_link(library, "Яндекс Музыка", lambda cancelled, report: yandex.tracks(link))


def apple_link(library, link):
    """A public Apple Music playlist or album."""
    return by_link(library, "Apple Music", lambda cancelled, report: apple.tracks(link))


def youtube_playlist(library, link):
    """A public YouTube or YouTube Music playlist."""
    return by_link(library, "YouTube", lambda cancelled, report: youtube.tracks(link, cancelled))


def on_disk(library, read, nothing):
    """The operation for music on this disk: read(cancelled, report) gives the tracks and how many files had no artist."""
    def run(cancelled, report):
        entries, skipped = read(cancelled, report)
        if cancelled():
            raise ImportFailed("Импорт отменён.")
        if not entries:
            raise ImportFailed(nothing)
        count = library.import_entries(entries, "Файлы")
        return f"Файлы · треков добавлено: {count}" + (f" · пропущено без артиста: {skipped}" if skipped else "")
    return run


def m3u_files(library, paths):
    """M3U or M3U8 playlists."""
    def read(cancelled, report):
        found = [local.playlist(path, cancelled, report) for path in paths]
        return [entry for entries, _ in found for entry in entries], sum(skipped for _, skipped in found)
    return on_disk(library, read, "В плейлисте не найдено треков: нужны строки #EXTINF вида «Артист - Название» или файлы с тегами.")


def music_folder(library, path):
    """A folder of audio files, with the folders inside it."""
    return on_disk(library, lambda cancelled, report: local.folder(path, cancelled, report),
                   "В файлах этой папки нет тегов с артистом и названием, а имена не вида «Артист - Название».")
