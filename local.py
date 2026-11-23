"""Music that is already on the disk: M3U playlists and folders of audio files. Tags are read with ffprobe."""
import json
import os
import re
import shutil
import subprocess

import tools
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from urllib.parse import unquote, urlsplit

from library import Entry, ImportFailed, artist_and_title, https_url, text


AUDIO = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".wma", ".aiff", ".aif", ".ape", ".wv", ".mka"}
MAX_PLAYLIST = 16 * 1024 * 1024
CANCELLED = "Импорт отменён."


def named(probe):
    """{"title": …, "artist": …} out of what ffprobe prints as JSON. Ogg and Opus keep tags on the
    audio stream, the other formats on the file."""
    places = [probe.get("format")] + list(probe.get("streams") or []) if isinstance(probe, dict) else []
    found = {}
    for place in places:
        tags = place.get("tags") if isinstance(place, dict) else None
        for name, value in (tags.items() if isinstance(tags, dict) else ()):
            found.setdefault(name.lower(), text(value))
    return {"title": found.get("title", ""), "artist": found.get("artist") or found.get("album_artist", "")}


def tags(program, path):
    try:
        done = subprocess.run([program, "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json", str(path)],
                              capture_output=True, stdin=subprocess.DEVNULL, timeout=20, **tools.QUIET)
        return named(json.loads(done.stdout.decode("utf-8", "replace")))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return named({})


def from_name(path):
    """(artist, title) as the file is named: "Artist - Title.mp3", perhaps after a track number."""
    return artist_and_title(re.sub(r"^\d{1,3}(?:\s*[.)_-]\s*|\s+)(?=\S)", "", Path(path).stem))


def entry(path, known):
    """The track a file holds, or None when neither its tags nor its name say who plays it."""
    artist, title = from_name(path)
    artist, title = known["artist"] or artist, known["title"] or title
    return Entry(title, artist, Path(path).resolve().as_uri()) if artist and title else None


def read(paths, cancelled, report):
    """The tags of each file, in order. Without ffprobe every file comes back untagged."""
    program = tools.program("ffprobe")
    if not program or not paths:
        return [named({}) for _ in paths]
    workers = ThreadPoolExecutor(8)
    asked = [workers.submit(tags, program, path) for path in paths]
    waiting = set(asked)
    try:
        while waiting:
            if cancelled():
                raise ImportFailed(CANCELLED)
            _, waiting = wait(waiting, timeout=0.2)
            report(f"Файлы · читаю теги: {len(asked) - len(waiting)} из {len(asked)}")
    finally:
        workers.shutdown(wait=False, cancel_futures=True)
    return [answer.result() for answer in asked]


def folder(path, cancelled=lambda: False, report=lambda message: None):
    """(tracks, files skipped for want of an artist) of the audio files in a folder and the folders inside it."""
    if not tools.program("ffprobe"):
        raise ImportFailed("Чтобы прочитать теги, нужна программа ffprobe из пакета ffmpeg. Установите её и повторите импорт.")
    if not Path(path).is_dir():
        raise ImportFailed("Выберите папку с музыкой.")
    report("Файлы · ищу аудиофайлы…")
    files = []
    for place, inside, names in os.walk(path):
        if cancelled():
            raise ImportFailed(CANCELLED)
        inside[:] = sorted(name for name in inside if not name.startswith("."))
        files += [Path(place, name) for name in sorted(names) if Path(name).suffix.lower() in AUDIO and not name.startswith(".")]
    if not files:
        raise ImportFailed("В этой папке нет аудиофайлов.")
    found = [entry(file, known) for file, known in zip(files, read(files, cancelled, report))]
    return [track for track in found if track], found.count(None)


def playlist(path, cancelled=lambda: False, report=lambda message: None):
    """(tracks, rows skipped for want of an artist) of an M3U or M3U8 playlist. A row is named by its
    #EXTINF line "Artist - Title"; a file on this disk without one is named by its tags or its name."""
    path = Path(path)
    try:
        if path.stat().st_size > MAX_PLAYLIST:
            raise ImportFailed(f"{path.name}\nФайл плейлиста больше 16 МБ.")
        raw = path.read_bytes()
    except OSError as error:
        raise ImportFailed(f"{path.name}\nНе удалось прочитать файл плейлиста.") from error
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        # M3U without the 8 is in the encoding of the system that wrote it; for Russian names that is Windows-1251.
        lines = raw.decode("cp1251", "replace").splitlines()
    rows = []
    shown = ""
    for line in map(str.strip, lines):
        if line[:8].upper() == "#EXTINF:":
            shown = line.partition(",")[2].strip()
        elif line and not line.startswith("#"):
            rows.append((shown, line))
            shown = ""
    places = [place(target, path.parent) for _, target in rows]
    # Only files that the playlist itself does not name need their tags read.
    unnamed = [file for (shown, _), (file, _) in zip(rows, places) if file and not artist_and_title(shown)[0]]
    known = dict(zip(unnamed, read(unnamed, cancelled, report)))
    found = []
    for (shown, target), (file, link) in zip(rows, places):
        artist, title = artist_and_title(shown)
        if artist:
            found.append(Entry(title, artist, link))
        elif file:
            found.append(entry(file, known[file]))
        else:
            # A file that is not here, or an address: its name is all there is to go by.
            artist, title = from_name(unquote(urlsplit(target).path) if "://" in target else target.replace("\\", "/"))
            found.append(Entry(title, artist, link) if artist else None)
    return [track for track in found if track], found.count(None)


def place(target, base):
    """(file, link) a playlist row points at: a file found on this disk and its file:// address, or
    (None, link) with the https address the row gives, if any."""
    if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]+://", target) and not target.lower().startswith("file://"):
        return None, https_url(target)
    name = unquote(urlsplit(target).path) if target.lower().startswith("file://") else target
    for variant in (name, name.replace("\\", "/")):
        try:
            file = (base / variant).resolve()
            if file.is_file():
                return file, file.as_uri()
        except (OSError, ValueError):
            pass
    return None, ""
