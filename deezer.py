"""A public Deezer playlist or album by link, read from the open API at api.deezer.com (no key)."""
import json
import re
from time import sleep
from urllib.error import HTTPError

from library import Entry, ImportFailed, https_url, text
from web import steady


API = "https://api.deezer.com"
LINK = re.compile(r"(?:https?://)?(?:www\.)?deezer\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?(playlist|album)/(\d+)/?(?:[?#].*)?", re.I)
# The Deezer app shares links of this kind; they redirect to the full address.
SHORT = re.compile(r"(?:https?://)?(link\.deezer\.com/s/[\w-]+)/?(?:[?#].*)?", re.I)
# Deezer's Akamai front refuses about every second request at random, whatever the pace,
# so a refusal is asked again this many times, this many seconds apart.
ATTEMPTS = 8
PAUSE = 1.5
PAGE = 500


def ask(url, cancelled):
    """What Deezer answers at an address, asking again after a refusal."""
    for attempt in range(ATTEMPTS):
        if cancelled():
            raise ImportFailed("Импорт отменён.")
        try:
            return steady(url, 32 * 1024 * 1024)
        except HTTPError as error:
            if error.code not in (403, 429) or attempt + 1 == ATTEMPTS:
                raise
            error.close()
        sleep(PAUSE)


def answer(path, cancelled):
    """The JSON the API holds at a path."""
    try:
        body = ask(f"{API}/{path}", cancelled)
    except HTTPError as error:
        raise ImportFailed(f"Deezer вернул ошибку HTTP {error.code}. Попробуйте позже.") from error
    except OSError as error:
        raise ImportFailed("Не удалось связаться с Deezer. Проверьте интернет и попробуйте снова.") from error
    try:
        data = json.loads(body)
    except ValueError as error:
        raise ImportFailed("Deezer ответил в неожиданном виде. Попробуйте позже.") from error
    if not isinstance(data, dict):
        raise ImportFailed("Deezer ответил в неожиданном виде. Попробуйте позже.")
    failure = data.get("error")
    if failure:
        code = failure.get("code") if isinstance(failure, dict) else None
        if code == 800:
            raise ImportFailed("Deezer не нашёл такой плейлист или альбом. Проверьте ссылку.")
        if code in (200, 300):
            raise ImportFailed("Этот плейлист закрыт. Откройте его для всех в Deezer и повторите импорт.")
        raise ImportFailed("Deezer не отдал список треков. Попробуйте позже.")
    return data


def target(short, cancelled):
    """Where a short link leads."""
    try:
        ask(f"https://{short}", cancelled)
    except HTTPError as error:
        if 300 <= error.code < 400:
            return text(error.headers.get("Location"))
        raise ImportFailed(f"Deezer вернул ошибку HTTP {error.code}. Попробуйте позже.") from error
    except OSError as error:
        raise ImportFailed("Не удалось связаться с Deezer. Проверьте интернет и попробуйте снова.") from error
    return ""


def entry(row):
    artist = row.get("artist")
    return Entry(text(row.get("title")), text(artist.get("name")) if isinstance(artist, dict) else "", https_url(row.get("link")))


def tracks(link, cancelled=lambda: False, report=lambda message: None):
    """The name of a public playlist or album and its tracks."""
    link = link.strip()
    short = SHORT.fullmatch(link)
    match = LINK.fullmatch(target(short[1], cancelled) if short else link)
    if short and not match:
        raise ImportFailed("Эта короткая ссылка Deezer не ведёт на плейлист или альбом. Откройте его в браузере и скопируйте адрес оттуда.")
    if not match:
        raise ImportFailed("Вставьте ссылку на плейлист или альбом вида https://www.deezer.com/playlist/…")
    place = f"{match[1].lower()}/{match[2]}"
    found = answer(place, cancelled)
    inside = found.get("tracks")
    rows = inside.get("data") if isinstance(inside, dict) else None
    rows = list(rows) if isinstance(rows, list) else []
    # A long list comes in part; the rest is asked for from where the part ends.
    total = found.get("nb_tracks")
    while isinstance(total, int) and len(rows) < total:
        report(f"Deezer · прочитано треков: {len(rows)} из {total}")
        more = answer(f"{place}/tracks?index={len(rows)}&limit={PAGE}", cancelled).get("data")
        if not isinstance(more, list) or not more:
            break
        rows += more
    entries = [entry(row) for row in rows if isinstance(row, dict)]
    entries = [track for track in entries if track.title and track.artist]
    if not entries:
        raise ImportFailed("По этой ссылке Deezer не показал ни одного трека.")
    return text(found.get("title")) or ("альбом" if match[1].lower() == "album" else "плейлист"), entries
