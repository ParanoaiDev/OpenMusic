import json
import re
from urllib.error import HTTPError

from library import Entry, ImportFailed, spotify_url, text
from web import page


# Spotify shows this many tracks of a playlist to a visitor who is not signed in.
VISIBLE_TRACKS = 100


def playlist(link):
    """The name of a public playlist and the tracks its public page lists."""
    match = re.fullmatch(
        r"(?:https?://)?open\.spotify\.com/(?:intl-[a-zA-Z-]+/)?(?:embed/)?playlist/([a-zA-Z0-9]{22})/?(?:[?#].*)?"
        r"|spotify:playlist:([a-zA-Z0-9]{22})", link.strip())
    if not match:
        raise ImportFailed("Вставьте ссылку на плейлист вида https://open.spotify.com/playlist/…")
    try:
        html = page(f"https://open.spotify.com/embed/playlist/{match[1] or match[2]}", 8 * 1024 * 1024)
    except HTTPError as error:
        raise ImportFailed(f"Spotify вернул ошибку HTTP {error.code}. Попробуйте позже.") from error
    except OSError as error:
        raise ImportFailed("Не удалось связаться со Spotify. Проверьте интернет и попробуйте снова.") from error
    try:
        data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        details = json.loads(data[1])["props"]["pageProps"]
        if details.get("status") == 404:
            raise ImportFailed("Плейлист не найден. Проверьте ссылку и что плейлист открыт для всех.")
        found = details["state"]["data"]["entity"]
        rows = [row for row in found["trackList"] if isinstance(row, dict) and row.get("entityType") == "track"]
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError) as error:
        if isinstance(error, ImportFailed):
            raise
        raise ImportFailed("Spotify показал страницу плейлиста в неожиданном виде. Импортируйте архив.") from error
    # Several artists come joined by a comma and a no-break space; the first is the main one.
    entries = [Entry(text(row.get("title")), text(row.get("subtitle")).split(",\xa0")[0].strip(), spotify_url(row.get("uri")))
               for row in rows]
    entries = [entry for entry in entries if entry.title and entry.artist]
    if not entries:
        raise ImportFailed("В плейлисте не найдено треков.")
    return text(found.get("name")) or "плейлист", entries
