"""A public Apple Music playlist or album by link, read from the data its page carries (no sign-in)."""
import json
import re
from urllib.error import HTTPError
from urllib.parse import parse_qs

from library import Entry, ImportFailed, https_url, text
from web import steady


LINK = re.compile(r"(?:https?://)?music\.apple\.com/([a-z]{2})/(playlist|album)/(?:[^/?#\s]+/)?(pl\.[\w-]+|\d+)/?(?:\?([^#\s]*))?(?:#.*)?", re.I)
UNEXPECTED = "Apple Music показал страницу в неожиданном виде. Попробуйте позже."


def song_id(row):
    about = row.get("contentDescriptor")
    numbers = about.get("identifiers") if isinstance(about, dict) else None
    return numbers.get("storeAdamID") if isinstance(numbers, dict) else None


def entry(row):
    # A playlist names each artist of a track separately, the main one first; an album gives one line.
    links = [link for link in row.get("subtitleLinks") or [] if isinstance(link, dict)]
    artist = text(links[0].get("title")) if links else ""
    about = row.get("contentDescriptor")
    return Entry(text(row.get("title")), artist or text(row.get("artistName")),
                 https_url(about.get("url")) if isinstance(about, dict) else "")


def reading(html, song=""):
    """The name and tracks a playlist or album page holds. `song` narrows an album to the one track
    its link points at."""
    try:
        data = re.search(r'<script[^>]*id="?serialized-server-data"?[^>]*>(.*?)</script>', html, re.S)
        sections = json.loads(data[1])["data"][0]["data"]["sections"]
        name, rows = "", []
        for section in sections:
            items = [item for item in section.get("items") or [] if isinstance(item, dict)]
            if section.get("itemKind") == "trackLockup":
                rows += items
            elif section.get("itemKind") == "containerDetailHeaderLockup" and items:
                name = text(items[0].get("title"))
        chosen = [row for row in rows if song and song_id(row) == song]
        entries = [entry(row) for row in chosen or rows]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, RecursionError) as error:
        raise ImportFailed(UNEXPECTED) from error
    return name, [track for track in entries if track.title and track.artist]


def tracks(link):
    """The name of a public playlist or album and its tracks."""
    match = LINK.fullmatch(link.strip())
    if not match:
        raise ImportFailed("Вставьте ссылку на плейлист или альбом вида https://music.apple.com/…/playlist/…")
    country, kind, number = match[1].lower(), match[2].lower(), match[3]
    address = f"https://music.apple.com/{country}/{kind}/{number}"
    try:
        html = steady(address, 64 * 1024 * 1024)
    except HTTPError as error:
        if error.code == 404:
            raise ImportFailed("Apple Music не нашёл такой плейлист или альбом. Проверьте ссылку и что плейлист открыт для всех.") from error
        raise ImportFailed(f"Apple Music вернул ошибку HTTP {error.code}. Попробуйте позже.") from error
    except OSError as error:
        raise ImportFailed("Не удалось связаться с Apple Music. Проверьте интернет и попробуйте снова.") from error
    name, entries = reading(html, parse_qs(match[4] or "").get("i", [""])[0])
    if not entries:
        raise ImportFailed("По этой ссылке Apple Music не показал ни одного трека.")
    return name or ("альбом" if kind == "album" else "плейлист"), entries
