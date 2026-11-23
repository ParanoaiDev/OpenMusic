"""An artist's page from the open Deezer API (no key): the photo, the fans, the popular tracks, the
releases and similar artists, and the tracks of a release. Answers are kept on disk for three days and
the pictures for good, so an artist opened again shows at once and asks nothing."""
import hashlib
import http.client
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request

import deezer
from library import https_url, key, text
from web import AGENT, opener


API = "https://api.deezer.com"
KEEP = 3 * 24 * 3600
PICTURE_LIMIT = 6 * 1024 * 1024
# "A & B", "A feat. B", "A, B", "A x B": the page is the first artist's.
JOINED = re.compile(r"\s*(?:,|&|\bfeat\.?|\bft\.?|\bfeaturing\b|\sx\s|\swith\s|/)\s*", re.I)
KINDS = {"album": "Альбом", "single": "Сингл", "ep": "EP", "compile": "Сборник"}


class Unavailable(Exception):
    """Deezer could not be reached or did not answer as expected."""


def main_artist(name):
    first = JOINED.split(name.strip(), maxsplit=1)[0].strip()
    return first or name.strip()


def digest(value):
    return hashlib.blake2b(value.encode("utf-8"), digest_size=10).hexdigest()


def ask(path, cancelled=lambda: False):
    try:
        data = json.loads(deezer.ask(f"{API}/{path}", cancelled))
    except (OSError, ValueError) as error:
        raise Unavailable(str(error)) from error
    if not isinstance(data, dict):
        raise Unavailable(path)
    if data.get("error"):
        raise Unavailable(str(data["error"]))
    return data


def rows(data):
    found = data.get("data") if isinstance(data, dict) else None
    return [row for row in found if isinstance(row, dict)] if isinstance(found, list) else []


def number(value):
    return value if isinstance(value, int) and value >= 0 else 0


def choose(name, found):
    """The Deezer artist meant by a name: one spelled the same, the most followed of those. Namesakes
    are many ("Face" has seven), so the search is asked for fifty."""
    wanted = key(name)
    same = [row for row in found if key(text(row.get("name"))) == wanted]
    if not same:
        # "Скриптонит" is "Scriptonite" there: a lone close match is taken only when it is well known.
        same = [row for row in found[:1] if number(row.get("nb_fan")) >= 1000 and wanted in key(text(row.get("name")))]
    return max(same, key=lambda row: number(row.get("nb_fan")), default=None)


def track_row(row, artist):
    album = row.get("album") if isinstance(row.get("album"), dict) else {}
    singer = row.get("artist") if isinstance(row.get("artist"), dict) else {}
    return dict(title=text(row.get("title")), artist=text(singer.get("name")) or artist, link=https_url(row.get("link")),
                seconds=number(row.get("duration")), album=text(album.get("title")),
                cover=https_url(album.get("cover_xl")) or https_url(album.get("cover_big")),
                explicit=bool(row.get("explicit_lyrics")))


def release_row(row):
    day = text(row.get("release_date"))
    return dict(id=number(row.get("id")), title=text(row.get("title")), year=day[:4], date=day,
                kind=KINDS.get(text(row.get("record_type")).lower(), "Альбом"),
                cover=https_url(row.get("cover_medium")) or https_url(row.get("cover_big")), link=https_url(row.get("link")),
                big=https_url(row.get("cover_xl")) or https_url(row.get("cover_big")))


def releases_of(found):
    """Newest first, each title once: Deezer lists a deluxe and a plain edition side by side."""
    seen, result = set(), []
    for row in sorted(found, key=lambda row: row["date"], reverse=True):
        name = key(re.sub(r"\s*[(\[].*?[)\]]\s*", " ", row["title"])) or key(row["title"])
        if not row["id"] or not row["title"] or name in seen:
            continue
        seen.add(name)
        result.append(row)
    return result


class Artists:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.answers = self.folder / "artists"
        self.pictures = self.folder / "pictures"

    def kept(self, name):
        path = self.answers / f"{name}.json"
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and time.time() - data.get("at", 0) < KEEP else None

    def keep(self, name, data):
        self.answers.mkdir(parents=True, exist_ok=True)
        path = self.answers / f"{name}.json"
        spare = path.with_suffix(".part")
        spare.write_text(json.dumps(dict(data, at=time.time()), ensure_ascii=False), "utf-8")
        spare.replace(path)

    def profile(self, name, cancelled=lambda: False):
        """Everything for the page of the artist called so; found=False when Deezer knows no such artist.
        Raises Unavailable when Deezer could not be asked."""
        wanted = main_artist(name)
        place = "artist-" + digest(key(wanted))
        kept = self.kept(place)
        if kept is not None:
            return kept
        picked = choose(wanted, rows(ask(f"search/artist?q={quote(wanted)}&limit=50", cancelled)))
        if picked is None:
            data = dict(found=False, name=wanted)
            self.keep(place, data)
            return data
        number_ = number(picked.get("id"))
        with ThreadPoolExecutor(4) as pool:
            parts = [pool.submit(ask, path, cancelled) for path in
                     (f"artist/{number_}", f"artist/{number_}/top?limit=10", f"artist/{number_}/albums?limit=100",
                      f"artist/{number_}/related?limit=14")]
            whole, top, albums, related = (part.result() for part in parts)
        shown = text(whole.get("name")) or text(picked.get("name")) or wanted
        data = dict(found=True, id=number_, name=shown, fans=number(whole.get("nb_fan")), albums=number(whole.get("nb_album")),
                    picture=https_url(whole.get("picture_xl")) or https_url(whole.get("picture_big")),
                    link=https_url(whole.get("link")),
                    top=[row for row in (track_row(row, shown) for row in rows(top)) if row["title"]],
                    releases=releases_of([release_row(row) for row in rows(albums)])[:48],
                    related=[dict(name=text(row.get("name")), fans=number(row.get("nb_fan")),
                                  picture=https_url(row.get("picture_medium")) or https_url(row.get("picture_big")))
                             for row in rows(related) if text(row.get("name"))])
        self.keep(place, data)
        return data

    def release(self, number_, cancelled=lambda: False):
        """The tracks of one release, in their order."""
        place = f"release-{int(number_)}"
        kept = self.kept(place)
        if kept is not None:
            return kept["tracks"]
        tracks = [dict(title=text(row.get("title")), artist=text((row.get("artist") or {}).get("name")) if isinstance(row.get("artist"), dict) else "",
                       link=https_url(row.get("link")), seconds=number(row.get("duration")), explicit=bool(row.get("explicit_lyrics")))
                  for row in rows(ask(f"album/{int(number_)}/tracks?limit=200", cancelled))]
        tracks = [track for track in tracks if track["title"]]
        self.keep(place, dict(tracks=tracks))
        return tracks

    def place(self, url):
        """Where a picture from Deezer's image servers is kept, or None for any other address."""
        address = https_url(url)
        host = urlsplit(address).hostname or ""
        if not address or not (host == "dzcdn.net" or host.endswith(".dzcdn.net")):
            return None
        return self.pictures / f"{digest(address)}.jpg"

    def save(self, path, body):
        if not body or len(body) > PICTURE_LIMIT:
            return False
        self.pictures.mkdir(parents=True, exist_ok=True)
        spare = path.with_name(path.name + f".{threading.get_ident()}.part")
        spare.write_bytes(body)
        spare.replace(path)
        return True

    def picture(self, url):
        """One picture saved on disk; its path, or None."""
        path = self.place(url)
        if path is None or path.exists():
            return path
        try:
            request = Request(https_url(url), headers={"User-Agent": AGENT})
            with opener.open(request, timeout=15) as response:
                body = response.read(PICTURE_LIMIT + 1)
        except OSError:
            return None
        return path if self.save(path, body) else None

    def pictures_for(self, addresses, landed, lanes=8):
        """Saves many pictures, calling landed(address, path) for each as it is there. The image servers
        take about a second to shake hands, so each lane keeps one connection open for all its pictures
        instead of opening one per picture."""
        waiting = []
        for address in dict.fromkeys(address for address in addresses if address):
            path = self.place(address)
            if path is None:
                continue
            if path.exists():
                landed(address, path)
            else:
                waiting.append((address, path))

        def lane(share):
            connection, host = None, ""
            for address, path in share:
                parts = urlsplit(address)
                for attempt in range(2):
                    try:
                        if connection is None or host != parts.hostname:
                            if connection is not None:
                                connection.close()
                            host = parts.hostname
                            connection = http.client.HTTPSConnection(host, timeout=15)
                        connection.request("GET", parts.path + (f"?{parts.query}" if parts.query else ""),
                                           headers={"User-Agent": AGENT, "Connection": "keep-alive"})
                        response = connection.getresponse()
                        body = response.read(PICTURE_LIMIT + 1)
                        if response.status == 200 and self.save(path, body):
                            landed(address, path)
                        break
                    except (OSError, http.client.HTTPException):
                        # A kept connection the server has closed: once more on a new one.
                        if connection is not None:
                            connection.close()
                        connection = None
            if connection is not None:
                connection.close()

        if waiting:
            with ThreadPoolExecutor(lanes) as pool:
                list(pool.map(lane, [waiting[number_::lanes] for number_ in range(lanes)]))
