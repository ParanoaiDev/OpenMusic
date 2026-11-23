"""A public Yandex Music playlist or album by link, read from the open API (no sign-in)."""
import json
import re
from urllib.error import HTTPError
from urllib.parse import quote, unquote

from library import Entry, ImportFailed, text
from web import steady


API = "https://api.music.yandex.net"
HOST = r"(?:https?://)?(?:next\.)?music\.yandex\.(?:ru|kz|by|uz|com)"
END = r"/?(?:[?#].*)?"
# The forms a link takes, and the API path each one stands for.
FORMS = (
    (re.compile(HOST + r"/users/([^/?#\s]+)/playlists/(\d+)" + END, re.I),
     lambda match: f"users/{quote(unquote(match[1]), safe='')}/playlists/{match[2]}"),
    (re.compile(HOST + r"/playlists/([\w.-]+)" + END, re.I), lambda match: f"playlist/{match[1]}"),
    (re.compile(HOST + r"/album/(\d+)" + END, re.I), lambda match: f"albums/{match[1]}/with-tracks"),
)
UNEXPECTED = "Яндекс Музыка ответила в неожиданном виде. Попробуйте позже."


def entry(track):
    artists = [artist for artist in track.get("artists") or [] if isinstance(artist, dict)]
    albums = [album for album in track.get("albums") or [] if isinstance(album, dict)]
    title = text(track.get("title"))
    # What Yandex shows in grey after the title: Remix, Live, feat. Somebody.
    if title and text(track.get("version")):
        title = f"{title} ({text(track['version'])})"
    number = str(track.get("id", ""))
    album = str(albums[0].get("id", "")) if albums else ""
    # A track the owner uploaded has no page of its own and no numeric id.
    url = ""
    if number.isdigit():
        url = f"https://music.yandex.ru/album/{album}/track/{number}" if album.isdigit() else f"https://music.yandex.ru/track/{number}"
    return Entry(title, text(artists[0].get("name")) if artists else "", url)


def tracks(link):
    """The name of a public playlist or album and its tracks."""
    path = next((make(match) for form, make in FORMS if (match := form.fullmatch(link.strip()))), None)
    if not path:
        raise ImportFailed("Вставьте ссылку на плейлист вида https://music.yandex.ru/users/…/playlists/… или на альбом.")
    try:
        data = json.loads(steady(f"{API}/{path}", 64 * 1024 * 1024))
    except HTTPError as error:
        if error.code in (400, 403, 404):
            raise ImportFailed("Яндекс Музыка не нашла такой плейлист. Проверьте ссылку и что плейлист открыт для всех.") from error
        raise ImportFailed(f"Яндекс Музыка вернула ошибку HTTP {error.code}. Попробуйте позже.") from error
    except OSError as error:
        raise ImportFailed("Не удалось связаться с Яндекс Музыкой. Проверьте интернет и попробуйте снова.") from error
    except ValueError as error:
        raise ImportFailed(UNEXPECTED) from error
    try:
        found = data["result"]
        if "volumes" in found:
            rows = [track for disc in found["volumes"] for track in disc]
        else:
            rows = [row.get("track") for row in found["tracks"] if isinstance(row, dict)]
        entries = [entry(row) for row in rows if isinstance(row, dict)]
    except (AttributeError, KeyError, TypeError) as error:
        raise ImportFailed(UNEXPECTED) from error
    entries = [track for track in entries if track.title and track.artist]
    if not entries:
        raise ImportFailed("По этой ссылке Яндекс Музыка не показала ни одного трека.")
    return text(found.get("title")) or "плейлист", entries
