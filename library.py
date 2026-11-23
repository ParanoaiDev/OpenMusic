import csv
import io
import json
import re
import sqlite3
import unicodedata
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit


MAX_FILE = 128 * 1024 * 1024
MAX_ARCHIVE_DATA = 256 * 1024 * 1024


class ImportFailed(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    title: str
    artist: str
    url: str = ""
    minute: str = ""
    milliseconds: int = 0


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    source: str
    url: str
    plays: int = 0
    milliseconds: int = 0


def key(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def text(value):
    return value.strip() if isinstance(value, str) else ""


def artist_and_title(shown):
    """("Artist", "Title") from "Artist - Title", the way files and uploads are commonly named.
    ("", shown) when no dash stands apart in it."""
    halves = re.split(r"\s+[-–—]\s+", shown.strip(), maxsplit=1)
    return (halves[0], halves[1]) if len(halves) == 2 and all(halves) else ("", shown.strip())


def https_url(value):
    value = text(value)
    if any(char.isspace() or ord(char) < 32 or char == "\\" for char in value):
        return ""
    try:
        url = urlsplit(value)
        if url.scheme == "https" and url.hostname and not url.username and not url.password:
            return value
    except ValueError:
        pass
    return ""


def spotify_url(value):
    match = re.fullmatch(r"spotify:track:([a-zA-Z0-9]+)", text(value))
    return f"https://open.spotify.com/track/{match[1]}" if match else ""


def spotify_entries(data, kind):
    if kind == "history" and isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            title = text(row.get("master_metadata_track_name", row.get("trackName")))
            artist = text(row.get("master_metadata_album_artist_name", row.get("artistName")))
            duration = row.get("ms_played", row.get("msPlayed"))
            stamp = text(row.get("ts", row.get("endTime")))
            if not title or not artist or type(duration) is not int or not 0 < duration <= 86_400_000:
                continue
            try:
                time = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if time.tzinfo:
                    time = time.astimezone(timezone.utc)
            except (OverflowError, ValueError):
                continue
            minute = time.strftime("%Y-%m-%dT%H:%M")
            yield Entry(title, artist, spotify_url(row.get("spotify_track_uri")), minute, duration)
    elif kind == "library" and isinstance(data, dict) and isinstance(data.get("tracks"), list):
        for row in data["tracks"]:
            if isinstance(row, dict):
                yield Entry(text(row.get("track")), text(row.get("artist")), spotify_url(row.get("uri")))
    elif kind == "playlist" and isinstance(data, dict) and isinstance(data.get("playlists"), list):
        for playlist in data["playlists"]:
            if not isinstance(playlist, dict) or not isinstance(playlist.get("items"), list):
                continue
            for item in playlist["items"]:
                track = item.get("track") if isinstance(item, dict) else None
                if isinstance(track, dict):
                    yield Entry(text(track.get("trackName")), text(track.get("artistName")), spotify_url(track.get("trackUri")))
    else:
        raise ImportFailed("Структура JSON не совпадает с форматом экспорта Spotify.")


def spotify_kind(name):
    name = PurePosixPath(name).name.lower()
    if re.fullmatch(r"streaminghistory(?:_music_)?\d*\.json", name) or re.fullmatch(
        r"streaming_history_audio(?:_[\w-]+)?\.json", name
    ) or re.fullmatch(r"endsong(?:_\d+)?\.json", name):
        return "history"
    if name == "yourlibrary.json":
        return "library"
    if re.fullmatch(r"playlist\d*\.json", name):
        return "playlist"
    return None


def spotify_file(path):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            files = [file for file in archive.infolist() if not file.is_dir() and spotify_kind(file.filename)]
            if not files:
                raise ImportFailed("В ZIP не найдена история прослушивания, библиотека или плейлисты Spotify.")
            if sum(file.file_size for file in files) > MAX_ARCHIVE_DATA:
                raise ImportFailed("Архив слишком большой. Выберите нужные JSON-файлы по отдельности.")
            for file in files:
                if file.file_size > MAX_FILE:
                    raise ImportFailed("Один из JSON-файлов превышает 128 МБ.")
                with archive.open(file) as stream:
                    data = json.load(io.TextIOWrapper(stream, encoding="utf-8-sig"))
                yield from spotify_entries(data, spotify_kind(file.filename))
        return
    if path.stat().st_size > MAX_FILE:
        raise ImportFailed("Файл превышает 128 МБ.")
    with path.open(encoding="utf-8-sig") as stream:
        data = json.load(stream)
    kind = spotify_kind(path.name)
    if kind is None:
        if isinstance(data, dict):
            kind = "playlist" if "playlists" in data else "library"
        elif isinstance(data, list) and any(
            isinstance(row, dict) and ("trackName" in row or "master_metadata_track_name" in row)
            for row in data
        ):
            kind = "history"
    yield from spotify_entries(data, kind)


def csv_file(path):
    if path.stat().st_size > MAX_FILE:
        raise ImportFailed("Файл превышает 128 МБ.")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        header = stream.readline()
        delimiter = max((",", ";", "\t"), key=header.count)
        stream.seek(0)
        rows = csv.DictReader(stream, delimiter=delimiter, strict=True)
        columns = {key(name): name for name in rows.fieldnames or []}
        title = next((columns[name] for name in ("title", "track", "track name", "трек") if name in columns), None)
        artist = next((columns[name] for name in ("artist", "artist name", "artist name(s)", "артист") if name in columns), None)
        if title is None or artist is None:
            raise ImportFailed("В CSV нужны столбцы title и artist. Столбец url необязателен.")
        url = columns.get("url")
        for row in rows:
            yield Entry(text(row.get(title)), text(row.get(artist)), https_url(row.get(url)))


class Library:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY, source TEXT NOT NULL,
                    title_key TEXT NOT NULL, artist_key TEXT NOT NULL,
                    title TEXT NOT NULL, artist TEXT NOT NULL, url TEXT NOT NULL,
                    UNIQUE (source, title_key, artist_key)
                );
                CREATE TABLE IF NOT EXISTS plays (
                    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
                    minute TEXT NOT NULL, milliseconds INTEGER NOT NULL,
                    PRIMARY KEY (track_id, minute, milliseconds)
                ) WITHOUT ROWID;
            """)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def store(self, db, entries, source):
        count = 0
        for entry in entries:
            if not entry.title or not entry.artist:
                continue
            (track_id,) = db.execute("""
                INSERT INTO tracks (source, title_key, artist_key, title, artist, url)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (source, title_key, artist_key) DO UPDATE SET
                  url = CASE WHEN excluded.url = '' THEN tracks.url ELSE excluded.url END
                RETURNING id
            """, (source, key(entry.title), key(entry.artist), entry.title, entry.artist, entry.url)).fetchone()
            if entry.minute:
                db.execute("INSERT OR IGNORE INTO plays VALUES (?, ?, ?)",
                           (track_id, entry.minute, entry.milliseconds))
            count += 1
        return count

    def import_files(self, paths, source):
        parser = spotify_file if source == "Spotify" else csv_file
        count = 0
        with closing(self.connect()) as db, db:
            for path in map(Path, paths):
                try:
                    count += self.store(db, parser(path), source)
                except (OSError, ValueError, csv.Error, zipfile.BadZipFile, RuntimeError) as error:
                    message = str(error) if isinstance(error, ImportFailed) else "Не удалось прочитать файл. Проверьте формат экспорта."
                    raise ImportFailed(f"{path.name}\n{message}") from error
            if not count:
                raise ImportFailed("В выбранных файлах не найдено музыкальных треков.")
        return count

    def import_entries(self, entries, source, replace=False):
        """Adds tracks fetched by link. `replace` makes them the whole of the source, as for a fresh list of likes."""
        with closing(self.connect()) as db, db:
            if replace:
                db.execute("DELETE FROM tracks WHERE source = ?", (source,))
            return self.store(db, entries, source)

    def tracks(self):
        with closing(self.connect()) as db:
            return [Track(*row) for row in db.execute("""
                SELECT title, artist, source, url, count(plays.track_id), coalesce(sum(milliseconds), 0)
                FROM tracks LEFT JOIN plays ON tracks.id = plays.track_id
                GROUP BY tracks.id
            """)]

    def clear(self, source):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM tracks WHERE source = ?", (source,))


def track_link(track):
    if track.url:
        return track.url
    if track.source == "Spotify":
        return "https://open.spotify.com/search/" + quote(f"{track.artist} {track.title}", safe="")
    return ""


def artist_ranking(tracks):
    artists = {}
    for track in tracks:
        artist = artists.setdefault(key(track.artist), [track.artist, 0, set()])
        artist[1] += track.milliseconds
        artist[2].add(key(track.title))
    return sorted(((name, duration, len(titles)) for name, duration, titles in artists.values()),
                  key=lambda artist: (-artist[1], -artist[2], key(artist[0])))
