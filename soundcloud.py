import html
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from threading import Event
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urlsplit

from library import Entry, ImportFailed, https_url, text
from web import page
from ytdlp import Refused, listing


# A display name costs one profile page, and SoundCloud refuses a visitor who asks for hundreds.
# So each import names only this many of the most liked uploaders; the rest keep their profile address.
MAX_NAMES = 30
# SoundCloud sometimes stalls instead of refusing, so naming gets this long and the import goes on without the rest.
NAMES_SECONDS = 20


def liked(profile, cancelled):
    """(uploader, title, link) of every track the profile publicly likes, as yt-dlp lists them."""
    try:
        rows = listing(f"https://soundcloud.com/{profile}/likes", ("url", "title", "ie_key"), cancelled, "лайков SoundCloud")
    except Refused as error:
        if "404" in str(error):
            raise ImportFailed("Профиль SoundCloud не найден. Проверьте ссылку.") from error
        raise ImportFailed("Не удалось получить лайки SoundCloud. Проверьте интернет или обновите yt-dlp.") from error
    tracks = {}
    for row in rows:
        link = https_url(row.get("url"))
        parts = urlsplit(link)
        path = parts.path.strip("/").split("/")
        # Liked playlists and albums come without ie_key and are skipped.
        if row.get("ie_key") == "Soundcloud" and parts.hostname == "soundcloud.com" and len(path) == 2 and text(row.get("title")):
            tracks[link] = (path[0], text(row["title"]), link)
    return list(tracks.values())


def uploader(link):
    return urlsplit(link).path.strip("/").split("/")[0]


def display_name(profile, refused):
    if refused.is_set():
        return profile
    try:
        match = re.search(r'<meta property="og:title" content="([^"]+)"', page(f"https://soundcloud.com/{profile}", 65536, 6))
        return html.unescape(match[1]).strip() or profile
    except HTTPError as error:
        if error.code in (403, 429):
            refused.set()
        return profile
    except (OSError, TypeError):
        return profile


def likes(profile, cancelled=lambda: False, report=lambda message: None, known=None):
    """Publicly liked tracks of a profile. `known` maps uploaders to display names learned by earlier imports."""
    match = re.fullmatch(r"(?:(?:https?://)?(?:www\.|m\.)?soundcloud\.com/)?([a-zA-Z0-9_-]+)(?:/likes)?/?(?:[?#].*)?", profile.strip())
    if not match:
        raise ImportFailed("Введите ссылку вида https://soundcloud.com/имя-профиля.")
    report("SoundCloud · читаю лайки профиля…")
    tracks = liked(match[1], cancelled)
    if not tracks:
        raise ImportFailed("В этом профиле нет открытых лайков.")
    names = dict(known or {})
    ranking = Counter(uploader(link) for _, _, link in tracks).most_common()
    unnamed = [name for name, _ in ranking if name not in names][:MAX_NAMES]
    report("SoundCloud · уточняю имена артистов…")
    refused = Event()
    workers = ThreadPoolExecutor(4)
    lookups = {workers.submit(display_name, name, refused): name for name in unnamed}
    waiting = set(lookups)
    deadline = monotonic() + NAMES_SECONDS
    try:
        while waiting and monotonic() < deadline:
            if cancelled():
                raise ImportFailed("Импорт отменён.")
            finished, waiting = wait(waiting, timeout=0.2)
            for lookup in finished:
                names[lookups[lookup]] = lookup.result()
    finally:
        workers.shutdown(wait=False, cancel_futures=True)
    return [Entry(title, names.get(name, name), link) for name, title, link in tracks]
