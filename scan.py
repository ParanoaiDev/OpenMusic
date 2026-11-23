"""Finds the music on this computer: walks the home folder and the mounted drives, looks at every
audio file with ffprobe and keeps what is a track, not a sound. A track lasts between 45 seconds
and half an hour, is not a voice message or a recording, does not live among a game's or a
program's files, and says who plays it: in its tags, its name "Artist - Title", or the folders of
a music collection (Music/Artist/Album/01 Title.mp3). No Qt here."""
import getpass
import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

import local
from library import Entry, ImportFailed, key

SHORTEST_S = 45
LONGEST_S = 30 * 60
SMALLEST = 400 * 1024
MOST_FILES = 30000
# Folders that hold programs, games and their sounds, never someone's music.
NOT_MUSIC = {
    "node_modules", "__pycache__", "site-packages", "dist-packages", "venv", ".venv", "env", "steamapps", "steam",
    "steamlibrary", "proton", "compatdata", "wine", "pfx", "drive_c", "windows", "program files", "program files (x86)",
    "programdata", "appdata", "$recycle.bin", "system volume information", "lost+found", "trash", "snap", "flatpak",
    "games", "heroic", "lutris", "bottles", "itch", "android", "sdk", "build", "dist", "target", "cache", "caches",
    "logs", "sfx", "sound effects", "soundeffects", "ringtones", "notifications", "alarms", "ui sounds", "samples",
    "sample packs", "presets", "plugins", "addons", "assets", "resources", "res", "textures", "models",
}
# Names of voice messages and recordings: Telegram, WhatsApp, recorders.
VOICE = re.compile(r"^(audio_\d|voice|ptt-|aud-\d|rec[_ -]?\d|recording|запись|диктофон|голосов|new recording)", re.IGNORECASE)
MUSIC_FOLDERS = {"music", "музыка", "my music", "моя музыка"}


def places():
    """Where to look: the home folder and the drives mounted for this user."""
    found = [Path.home()]
    user = getpass.getuser()
    for base in (Path("/run/media") / user, Path("/media") / user, Path("/media"), Path("/mnt")):
        try:
            found += [item for item in base.iterdir() if item.is_dir() and not item.is_symlink()]
        except OSError:
            pass
    unique = []
    for place in found:
        if place.is_dir() and not any(place == other or other in place.parents for other in unique):
            unique.append(place)
    return unique


def candidates(roots, cancelled, report):
    """Audio files big enough to be a song, outside hidden, program and game folders."""
    files = []
    for root in roots:
        for place, inside, names in os.walk(root, onerror=lambda error: None):
            if cancelled():
                raise ImportFailed(local.CANCELLED)
            inside[:] = sorted(name for name in inside if not name.startswith(".") and name.casefold() not in NOT_MUSIC
                               and not os.path.islink(os.path.join(place, name)))
            for name in names:
                if Path(name).suffix.lower() in local.AUDIO and not name.startswith("."):
                    path = Path(place, name)
                    try:
                        if path.stat().st_size >= SMALLEST:
                            files.append(path)
                    except OSError:
                        pass
            if len(files) >= MOST_FILES:
                return files
            if len(files) % 200 == 0 and files:
                report(f"Ищу музыку на компьютере… аудиофайлов: {len(files)}")
    return files


def probe(program, path):
    """(seconds, bits per second, channels, tags) of a file, or None when ffprobe can't read it."""
    try:
        done = subprocess.run([program, "-v", "error", "-show_entries",
                               "format=duration,bit_rate:format_tags:stream=codec_type,channels:stream_tags", "-of", "json", str(path)],
                              capture_output=True, stdin=subprocess.DEVNULL, timeout=20)
        data = json.loads(done.stdout.decode("utf-8", "replace"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    form = data.get("format") or {}
    try:
        seconds = float(form.get("duration") or 0)
    except ValueError:
        seconds = 0.0
    streams = [stream for stream in data.get("streams") or [] if isinstance(stream, dict)]
    if any(stream.get("codec_type") == "video" and not str(path).lower().endswith((".mp3", ".m4a", ".flac")) for stream in streams):
        return None
    channels = max([int(stream.get("channels") or 0) for stream in streams if stream.get("codec_type") == "audio"] or [0])
    try:
        rate = int(form.get("bit_rate") or 0)
    except ValueError:
        rate = 0
    return seconds, rate, channels, local.named(data)


def collection_artist(path, roots):
    """The artist a music collection's folders give: Music/Artist/Album/file or Music/Artist/file."""
    parts = path.parent.parts
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].casefold() in MUSIC_FOLDERS:
            inside = parts[index + 1:]
            if len(inside) in (1, 2):
                return inside[0]
            return ""
    return ""


def judge(path, info, roots):
    """(entry, None) for a track, or (None, the reason it is not one)."""
    if info is None:
        return None, "unreadable"
    seconds, rate, channels, known = info
    if seconds < SHORTEST_S:
        return None, "short"
    if seconds > LONGEST_S:
        return None, "long"
    if VOICE.match(path.stem) or (channels == 1 and 0 < rate < 48000 and not known["artist"]):
        return None, "voice"
    found = local.entry(path, known)
    if found is None:
        artist = collection_artist(path, roots)
        title = known["title"] or re.sub(r"^\d{1,3}(?:\s*[.)_-]\s*|\s+)(?=\S)", "", path.stem).strip()
        if artist and title:
            found = Entry(title, artist, path.resolve().as_uri())
    if found is None:
        return None, "nameless"
    return Entry(found.title, found.artist, found.url), None


def find(roots, cancelled=lambda: False, report=lambda message: None):
    """(tracks, {reason: how many files were left out}, folders with music)."""
    program = shutil.which("ffprobe")
    if not program:
        raise ImportFailed("Чтобы отличить треки от звуков, нужна программа ffprobe из пакета ffmpeg. Установите её и повторите.")
    report("Ищу музыку на компьютере…")
    files = candidates(roots, cancelled, report)
    if not files:
        raise ImportFailed("На компьютере не нашлось аудиофайлов.")
    workers = ThreadPoolExecutor(8)
    asked = [workers.submit(probe, program, path) for path in files]
    waiting = set(asked)
    try:
        while waiting:
            if cancelled():
                raise ImportFailed(local.CANCELLED)
            _, waiting = wait(waiting, timeout=0.25)
            report(f"Слушаю файлы: {len(asked) - len(waiting)} из {len(asked)}")
    finally:
        workers.shutdown(wait=False, cancel_futures=True)
    best = {}
    skipped = {}
    for path, answer in zip(files, asked):
        info = answer.result()
        entry, reason = judge(path, info, roots)
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        name = (key(entry.artist), key(entry.title))
        quality = (info[1], info[0])
        if name not in best or quality > best[name][0]:
            if name in best:
                skipped["copy"] = skipped.get("copy", 0) + 1
            best[name] = (quality, entry, path.parent)
        else:
            skipped["copy"] = skipped.get("copy", 0) + 1
    tracks = [entry for _, entry, _ in best.values()]
    folders = len({folder for _, _, folder in best.values()})
    return tracks, skipped, folders


def plural(count, forms):
    tail = count % 100
    form = forms[2] if 11 <= tail <= 14 else forms[0] if count % 10 == 1 else forms[1] if 2 <= count % 10 <= 4 else forms[2]
    return f"{count} {form}"


def summary(added, skipped, folders):
    parts = [f"Файлы · найдено и добавлено: {plural(added, ('трек', 'трека', 'треков'))} из {plural(folders, ('папки', 'папок', 'папок'))}"]
    names = (("short", "короткие звуки"), ("voice", "голосовые и записи"), ("nameless", "без артиста"),
             ("long", "длинные записи"), ("copy", "копии"), ("unreadable", "нечитаемые"))
    left = [f"{title} — {skipped[reason]}" for reason, title in names if skipped.get(reason)]
    if left:
        parts.append("пропущено: " + ", ".join(left))
    return " · ".join(parts)


def computer(library, roots=None):
    """The import operation (see jobs.py): finds the music and adds it to the source «Файлы»."""
    def run(cancelled, report):
        tracks, skipped, folders = find(roots or places(), cancelled, report)
        if cancelled():
            raise ImportFailed(local.CANCELLED)
        if not tracks:
            raise ImportFailed("Аудиофайлы есть, но треков среди них нет: у всех нет артиста в тегах и имени, или это короткие звуки и записи.")
        report(f"Добавляю {len(tracks)} треков…")
        return summary(library.import_entries(tracks, "Файлы"), skipped, folders)
    return run
