"""Album covers for library tracks. Nothing here touches Qt; every call waits on the network.

A Spotify track gets its exact cover from Spotify's public oEmbed. Other tracks are matched by
artist and title on the iTunes Search API and then the Deezer API (all free, no key). A track that
plays also gets the artwork SoundCloud shows for it. Covers are kept as files, one per track, and a
track iTunes has no cover for is asked about again only after a week."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request

from library import key
from stream import same_artist, words
from web import AGENT, opener

API = "https://itunes.apple.com/search"
LARGEST = 4 * 1024 * 1024
MISS_SECONDS = 7 * 24 * 3600


def download(url, limit=LARGEST, timeout=15):
    request = Request(url, headers={"User-Agent": AGENT})
    with opener.open(request, timeout=timeout) as response:
        return response.read(limit)


DEEZER = "https://api.deezer.com/search"


class Refused(Exception):
    """A service turned the request away; the caller should wait before asking it again."""


def pick(candidates, artist, title):
    """The best of (artist, title, cover, length ms) candidates, or None when none is the track."""
    wanted = words(title)
    best, best_score = None, 0.0
    for name, found_title, picture, length in candidates:
        if not picture or not same_artist(artist, name):
            continue
        overlap = len(wanted & words(found_title)) / len(wanted) if wanted else 0
        if overlap > best_score:
            best, best_score = (picture, length), overlap
    return best if best_score >= 0.5 else None


def itunes(artist, title):
    query = urlencode({"term": f"{artist} {title}", "entity": "song", "limit": 8})
    results = json.loads(download(f"{API}?{query}", 1024 * 1024).decode("utf-8", "replace")).get("results") or []
    return pick([(item.get("artistName") or "", item.get("trackName") or "",
                  (item.get("artworkUrl100") or "").replace("100x100bb", "600x600bb"), item.get("trackTimeMillis") or 0)
                 for item in results], artist, title)


def deezer(artist, title):
    for term in (f"{artist} {title}", title):
        try:
            body = download(f"{DEEZER}?{urlencode({'q': term, 'limit': 10})}", 1024 * 1024)
        except HTTPError as error:
            if error.code in (403, 429):
                raise Refused() from error
            raise
        results = json.loads(body.decode("utf-8", "replace")).get("data") or []
        found = pick([((item.get("artist") or {}).get("name") or "", item.get("title") or "",
                       (item.get("album") or {}).get("cover_xl") or "", (item.get("duration") or 0) * 1000)
                      for item in results], artist, title)
        if found:
            return found
    return None


def spotify(track_url):
    """The album cover of a Spotify track, exactly, from Spotify's public oEmbed. Address or None."""
    if not track_url.startswith("https://open.spotify.com/track/"):
        return None
    answer = json.loads(download(f"https://open.spotify.com/oembed?{urlencode({'url': track_url})}", 256 * 1024)
                        .decode("utf-8", "replace"))
    picture = answer.get("thumbnail_url") or ""
    # The oEmbed picture is 300 px; the same image at 640 px differs only in its size code.
    return picture.replace("ab67616d00001e02", "ab67616d0000b273") if picture else None


def spotify_artist(track_url):
    """The photo of the main artist of a Spotify track: the track's public embed page names the
    artist, and the artist's oEmbed gives the photo (asked for at 640 px). Address or None."""
    found = re.search(r"open\.spotify\.com/track/([A-Za-z0-9]{22})", track_url or "")
    if not found:
        return None
    page = download(f"https://open.spotify.com/embed/track/{found[1]}", 2 * 1024 * 1024).decode("utf-8", "replace")
    data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not data:
        return None
    entity = json.loads(data[1])["props"]["pageProps"]["state"]["data"]["entity"]
    artists = entity.get("artists") or []
    if not artists or not artists[0].get("uri"):
        return None
    artist_id = artists[0]["uri"].rsplit(":", 1)[-1]
    answer = json.loads(download(f"https://open.spotify.com/oembed?{urlencode({'url': f'https://open.spotify.com/artist/{artist_id}'})}",
                                 256 * 1024).decode("utf-8", "replace"))
    picture = answer.get("thumbnail_url") or ""
    return picture.replace("ab67616100005174", "ab6761610000e5eb") if picture else None


def soundcloud_artist(track_url):
    """The profile picture of whoever uploaded a SoundCloud track, from the profile's public page."""
    found = re.match(r"https://soundcloud\.com/([^/?#]+)/", track_url or "")
    if not found:
        return None
    page = download(f"https://soundcloud.com/{found[1]}", 512 * 1024).decode("utf-8", "replace")
    picture = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    if not picture or "default_avatar" in picture[1]:
        return None
    return picture[1].replace("-t200x200.", "-t500x500.").replace("-large.", "-t500x500.")


def lookup(artist, title, deezer_allowed=True):
    """(cover address, track length in ms) of the best match on iTunes, then Deezer; or None."""
    return itunes(artist, title) or (deezer(artist, title) if deezer_allowed else None)


class Store:
    """Cover files in a folder, named after the track."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def name(artist, title):
        return hashlib.blake2b(f"{key(artist)}\n{key(title)}".encode("utf-8"), digest_size=12).hexdigest()

    def path(self, artist, title):
        return self.folder / f"{self.name(artist, title)}.jpg"

    def artist_path(self, artist):
        return self.folder / f"artist-{self.name(artist, '')}.jpg"

    def fetch_artist(self, artist, track_url):
        """Saves the photo of an artist, found from one of their tracks. True when there is one."""
        target = self.artist_path(artist)
        if target.exists():
            return True
        miss = target.with_suffix(".miss")
        if miss.exists() and time.time() - miss.stat().st_mtime < MISS_SECONDS:
            return False
        try:
            url = spotify_artist(track_url) if "open.spotify.com" in (track_url or "") else soundcloud_artist(track_url)
        except (OSError, ValueError, KeyError, TypeError):
            url = None
        if not url:
            miss.touch()
            return False
        partial = target.with_suffix(".part")
        partial.write_bytes(download(url))
        partial.replace(target)
        return True

    def has(self, artist, title):
        return self.path(artist, title).exists()

    def missed(self, artist, title):
        miss = self.folder / f"{self.name(artist, title)}.miss"
        return miss.exists() and time.time() - miss.stat().st_mtime < MISS_SECONDS

    def save(self, artist, title, data):
        target = self.path(artist, title)
        temporary = target.with_suffix(".part")
        temporary.write_bytes(data)
        temporary.replace(target)

    def miss(self, artist, title):
        (self.folder / f"{self.name(artist, title)}.miss").touch()

    def fetch(self, artist, title, url="", deezer_allowed=True, page=""):
        """Finds and saves the cover of one track. True when there is a cover file afterwards.
        `page` is the track's own address: a Spotify track gets its exact cover from it.
        Raises Refused when Deezer turned the request away, so nothing is marked as missing."""
        if not url and page:
            try:
                url = spotify(page) or ""
            except (OSError, ValueError):
                url = ""
        if not url:
            found = lookup(artist, title, deezer_allowed)
            if found is None:
                self.miss(artist, title)
                return False
            url = found[0]
        self.save(artist, title, download(url))
        return True
