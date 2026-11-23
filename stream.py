"""Sound for a track of the library, found on SoundCloud through yt-dlp. Nothing here touches Qt:
find() waits on the network for a few seconds, so call it from a worker thread.

A track imported from SoundCloud already has its page. Any other track is searched for by artist
and title, and the best match wins: same title, the artist in the uploader or the title, no remix
or cover the original doesn't have. The page found is remembered, so the next time only the stream
address, which expires, is asked for again."""
import hashlib
import math
import queue
import re
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from library import key

# A result shorter than this is a preview, not the track.
SHORTEST_MS = 45_000
# And one longer than this is a set, a broadcast or a whole album.
LONGEST_MS = 15 * 60_000
SEARCH_RESULTS = 12
VERSIONS = ("remix", "cover", "slowed", "sped up", "speed up", "speed", "nightcore", "instrumental", "karaoke",
            "minus", "минус", "ремикс", "кавер", "live", "8d", "reverb", "bass boosted", "mashup", "blend", "bootleg",
            "edit", "flip", "rework", "tiktok", "acoustic", "акустика")
VERSION = re.compile(r"\b(" + "|".join(re.escape(word) for word in VERSIONS) + r")\b")
# Words uploaders add to a title that say nothing about which recording it is.
FILLER = {"prod", "by", "feat", "ft", "official", "audio", "video", "music", "lyrics", "lyric", "hd", "hq", "mp3", "original",
          "премьера", "клип", "трека", "альбом", "album", "ost", "single", "сингл", "new", "full", "version", "версия"}
# A page found before this moment was chosen by the first rule (the first upload that fits, were it
# a cover with a thousand plays); it is looked for again by the present one.
CHOSEN_SINCE = 1795461312
# The score of an upload that has the title, names the artist and is no other version.
GOOD = 4.5


class StreamFailed(Exception):
    """No sound was found or it could not be fetched. The message is worded for the user."""


@dataclass(frozen=True)
class Source:
    url: str
    title: str
    artist: str
    duration_ms: int
    page: str
    artwork: str = ""


def clean(text):
    """A title without the decorations uploaders add: track numbers, (prod. …), feat. …, brackets."""
    text = key(text)
    text = re.sub(r"^\d{1,2}[.)]\s*", "", text)
    text = re.sub(r"[(\[][^)\]]*(prod|feat|ft\.|official|audio|video|lyrics|премьера|клип)[^)\]]*[)\]]", " ", text)
    text = re.sub(r"\b(feat|ft)\.?\s.*$", " ", text)
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


LATIN = (("shch", "щ"), ("dzh", "дж"), ("zh", "ж"), ("kh", "х"), ("ts", "ц"), ("ch", "ч"), ("sh", "ш"), ("yu", "ю"),
         ("ya", "я"), ("yo", "ё"), ("ey", "ей"), ("iy", "ий"), ("y", "ы"), ("a", "а"), ("b", "б"), ("v", "в"),
         ("g", "г"), ("d", "д"), ("e", "е"), ("z", "з"), ("i", "и"), ("j", "й"), ("k", "к"), ("l", "л"), ("m", "м"),
         ("n", "н"), ("o", "о"), ("p", "п"), ("r", "р"), ("s", "с"), ("t", "т"), ("u", "у"), ("f", "ф"), ("h", "х"),
         ("c", "к"), ("w", "в"), ("x", "кс"), ("q", "к"))
CYRILLIC = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
            "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
            "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y",
            "ь": "", "э": "e", "ю": "yu", "я": "ya"}


def to_cyrillic(text):
    """A rough Russian spelling of a transliterated name, for searching: Monetochka → монеточка."""
    text, result = text.lower(), ""
    while text:
        for latin, cyrillic in LATIN:
            if text.startswith(latin):
                result, text = result + cyrillic, text[len(latin):]
                break
        else:
            result, text = result + text[0], text[1:]
    return result


def to_latin(text):
    return "".join(CYRILLIC.get(char, char) for char in key(text))


def voice(name):
    """A name by its sound, the same for either alphabet and the common ways to spell it:
    «Макс Корж» and "Max Korzh", «Скриптонит» and "Skryptonite", «Оксимирон» and "Oxxxymiron"."""
    # «МС» in Russian letters is the same "MC" rappers put before their names.
    sound = re.sub(r"[^\w\s]|_", " ", to_latin(re.sub(r"\bмс\b", "mc", key(name))))
    sound = re.sub(r"(.)\1+", r"\1", sound)
    for letters, plain in (("kh", "h"), ("ph", "f"), ("ck", "k"), ("x", "ks"), ("w", "v"), ("j", "i"), ("y", "i"), ("q", "k")):
        sound = sound.replace(letters, plain)
    sound = re.sub(r"c(?!h)", "k", sound)
    sound = re.sub(r"(.)\1+", r"\1", sound)
    return " ".join(word[:-1] if len(word) > 4 and word.endswith("e") else word for word in sound.split())


def same_artist(artist, *places):
    """Whether the artist, or any of several an artist line names, is heard as whole words in any
    of the places, whichever alphabet each is written in."""
    names = [name for name in re.split(r"\s*(?:,|&|;|\bfeat\.?|\bft\.?|\sx\s)\s*", artist) if name.strip()] or [artist]
    wanted = {voice(name) for name in names} - {""}
    found = " " + " ".join(voice(place) for place in places) + " "
    return any(f" {name} " in found for name in wanted)


def words(text):
    return set(clean(text).split())


def spoken(text):
    """The words of a title by their sound, so that «Тело» and "Telo" are one word."""
    return set(voice(clean(text)).split())


def score(candidate, artist, title, strict=False):
    """How well a search result matches the track; below 1 it is not the track. Of the uploads that
    fit, the artist's own and the one people play most win; a version the track is not (a cover,
    sped up), words the title does not have (another song, "по-польски") and an upload that does
    not name the artist at all lose."""
    found_title = candidate.get("title") or ""
    uploader = candidate.get("uploader") or ""
    wanted = spoken(title)
    if not wanted:
        return 0.0
    in_title = spoken(found_title)
    overlap = len(wanted & in_title) / len(wanted)
    if overlap < 0.5:
        return 0.0
    points = overlap * 2
    if voice(clean(title)) in voice(clean(found_title)):
        points += 1
    if same_artist(artist, uploader, found_title):
        # The artist's own page: "LIZER FAN" is not Lizer's.
        names = [name for name in re.split(r"\s*(?:,|&|;|\bfeat\.?|\bft\.?|\sx\s)\s*", artist) if name.strip()] or [artist]
        points += 1.5 + 0.3 * (voice(uploader) in {voice(name) for name in names})
    elif strict:
        return 0.0
    else:
        points -= 2
    added = set(VERSION.findall(key(found_title))) - set(VERSION.findall(key(title)))
    points -= 1.5 * len(added)
    extra = in_title - wanted - spoken(artist) - spoken(uploader) - FILLER - set(VERSIONS)
    points -= 0.3 * min(4, len([word for word in extra if not word.isdigit()]))
    points += 0.15 * math.log10((candidate.get("plays") or 0) + 1)
    if not SHORTEST_MS <= (candidate.get("duration") or 0) * 1000 <= LONGEST_MS:
        return 0.0
    return points


def open_streams(item):
    """The streams of a track that can be played. Major labels' streams come encrypted (protocol
    ctr-/cbc-encrypted-hls, a "cbcs" path): without their player's keys they are noise."""
    return [entry for entry in (item.get("media") or {}).get("transcodings") or []
            if (entry.get("format") or {}).get("protocol") in ("hls", "progressive")
            and not entry.get("snipped")
            and "/cbcs/" not in (entry.get("url") or "") and "/ctr/" not in (entry.get("url") or "")]


def track_name(artist, title):
    return f"{key(artist)}\n{key(title)}"


def expiry(url):
    """When a stream address stops working, from its own expires= field; soon if it has none."""
    found = re.search(r"[?&]expires=(\d+)", url)
    return int(found[1]) if found else time.time() + 600


class Resolver:
    """Finds sound for tracks. Talks to SoundCloud's own API through yt-dlp's SoundCloud extractor,
    which keeps the client id it needs, so a track costs two requests: a search (or, for a track
    imported from SoundCloud, a lookup of its page) and the address of its stream.
    Safe to use from several threads: each thread gets its own yt-dlp session."""

    def __init__(self, cache_path=None):
        self.cache_path = Path(cache_path) if cache_path else None
        self.local = threading.local()
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.cache_path)) as db, db:
                db.execute("CREATE TABLE IF NOT EXISTS pages (track TEXT PRIMARY KEY, page TEXT NOT NULL, saved REAL NOT NULL)")

    def client(self):
        session = getattr(self.local, "session", None)
        if session is None:
            if not find_spec("yt_dlp"):
                raise StreamFailed("Чтобы слушать треки, нужна программа yt-dlp. Установите её и попробуйте снова.")
            import yt_dlp
            session = yt_dlp.YoutubeDL({
                "quiet": True, "no_warnings": True, "noplaylist": True, "format": "bestaudio/best",
                "socket_timeout": 15, "skip_download": True, "noprogress": True,
            })
            extractor = session.get_info_extractor("Soundcloud")
            extractor.initialize()
            self.local.session, self.local.extractor = session, extractor
        return session

    def api(self, path, **query):
        self.client()
        extractor = self.local.extractor
        try:
            return extractor._call_api(extractor._API_V2_BASE + path, None, query=query)
        except Exception as error:
            raise StreamFailed("SoundCloud не ответил. Проверьте интернет и попробуйте снова.") from error

    def remembered(self, track_key):
        if not self.cache_path:
            return None
        with closing(sqlite3.connect(self.cache_path)) as db:
            row = db.execute("SELECT page FROM pages WHERE track = ? AND saved >= ?", (track_key, CHOSEN_SINCE)).fetchone()
        return row[0] if row else None

    def outdated(self):
        """[(track key, page)] of the pages chosen by the rule before the present one."""
        if not self.cache_path:
            return []
        with closing(sqlite3.connect(self.cache_path)) as db:
            return db.execute("SELECT track, page FROM pages WHERE saved < ?", (CHOSEN_SINCE,)).fetchall()

    def remember(self, track_key, page):
        if self.cache_path:
            with closing(sqlite3.connect(self.cache_path)) as db, db:
                db.execute("INSERT OR REPLACE INTO pages VALUES (?, ?, ?)", (track_key, page, time.time()))

    def renew(self, changed=lambda artist, title: None, cancelled=lambda: False):
        """Looks again for every page chosen by the rule before the present one. Where another
        upload wins now, changed(artist, title) is called (names as the cache keeps them, in small
        letters): the file downloaded from the old upload is not the track any more. Returns how
        many tracks changed. Slow: a search for each, so for a worker thread."""
        count = 0
        for name, page in self.outdated():
            if cancelled():
                break
            artist, _, title = name.partition("\n")
            try:
                found = self.search(artist, title).get("permalink_url") or page
            except StreamFailed as error:
                if not str(error).startswith("Не нашёл"):
                    break       # no network: another time
                continue
            self.remember(name, found)
            if found != page:
                count += 1
                changed(artist, title)
        return count

    def forget(self, artist, title):
        if self.cache_path:
            with closing(sqlite3.connect(self.cache_path)) as db, db:
                db.execute("DELETE FROM pages WHERE track = ?", (track_name(artist, title),))

    def search(self, artist, title):
        queries = [(f"{artist} {title}", False)]
        if re.fullmatch(r"[A-Za-z0-9 .'&-]+", artist):
            queries.append((f"{to_cyrillic(artist)} {title}", False))
        # Only the title: anyone can have a song called «90», so the artist must match.
        queries.append((title, True))
        best, chosen = 0.0, None
        for query, strict in queries:
            found = self.api("search/tracks", q=query, limit=SEARCH_RESULTS).get("collection") or []
            for item in found:
                # SNIP is a 30-second preview, BLOCK is not playable here.
                if item.get("kind") != "track" or item.get("policy") in ("SNIP", "BLOCK") or not open_streams(item):
                    continue
                shown = {"title": item.get("title") or "", "uploader": (item.get("user") or {}).get("username") or "",
                         "duration": (item.get("full_duration") or item.get("duration") or 0) / 1000,
                         "plays": item.get("playback_count") or 0}
                points = score(shown, artist, title, strict)
                if points > best:
                    best, chosen = points, item
            # A plain upload of the track by its artist scores above GOOD: no need to ask further.
            if best >= GOOD:
                break
        if chosen is not None and best >= 1:
            return chosen
        raise StreamFailed(f"Не нашёл «{title}» на SoundCloud.")

    def stream(self, item, page=""):
        """The stream of a track as the API describes it: the best AAC over HLS, else what there is."""
        transcodings = open_streams(item)
        if not transcodings and (item.get("media") or {}).get("transcodings"):
            raise StreamFailed("На SoundCloud этот трек защищён правообладателем, его не воспроизвести.")
        if not transcodings or item.get("policy") in ("SNIP", "BLOCK"):
            raise StreamFailed("SoundCloud даёт послушать только отрывок этого трека.")

        def rank(entry):
            preset = entry.get("preset") or ""
            protocol = (entry.get("format") or {}).get("protocol") or ""
            return ("aac_160" in preset) * 4 + ("aac" in preset) * 2 + (protocol == "progressive") + (not entry.get("snipped")) * 8
        chosen = max(transcodings, key=rank)
        if chosen.get("snipped"):
            raise StreamFailed("SoundCloud даёт послушать только отрывок этого трека.")
        self.client()
        extractor = self.local.extractor
        query = {"client_id": extractor._CLIENT_ID}
        if item.get("track_authorization"):
            query["track_authorization"] = item["track_authorization"]
        try:
            address = extractor._download_json(chosen["url"], None, query=query, note=False)["url"]
        except Exception as error:
            raise StreamFailed("Не удалось получить звук с SoundCloud. Возможно, трек закрыт или удалён.") from error
        artwork = (item.get("artwork_url") or (item.get("user") or {}).get("avatar_url") or "").replace("-large.", "-t500x500.")
        if "default_avatar" in artwork:
            artwork = ""
        return Source(address, item.get("title") or "", (item.get("user") or {}).get("username") or "",
                      int(item.get("full_duration") or item.get("duration") or 0), item.get("permalink_url") or page, artwork)

    def search_online(self, query, limit=20):
        """Tracks on SoundCloud for a query, as Track(title, artist, "SoundCloud", page)
        with their length and artwork: [(track, duration_ms, artwork)]."""
        from library import Track
        found = self.api("search/tracks", q=query, limit=limit).get("collection") or []
        result = []
        for item in found:
            if item.get("kind") != "track" or item.get("policy") in ("SNIP", "BLOCK") or not open_streams(item):
                continue
            artwork = (item.get("artwork_url") or (item.get("user") or {}).get("avatar_url") or "").replace("-large.", "-t500x500.")
            result.append((Track(item.get("title") or "", (item.get("user") or {}).get("username") or "", "SoundCloud",
                                 item.get("permalink_url") or ""),
                           int(item.get("full_duration") or item.get("duration") or 0), artwork))
        return result

    def related(self, track, limit=25):
        """Tracks SoundCloud plays after this one on its own station: the seed of "Мой поток"."""
        from library import Track
        if track.source == "SoundCloud" and track.url:
            item = self.api("resolve", url=track.url)
        else:
            page = self.remembered(track_name(track.artist, track.title))
            item = self.api("resolve", url=page) if page else self.search(track.artist, track.title)
        found = self.api(f"tracks/{item['id']}/related", limit=limit).get("collection") or []
        return [Track(entry.get("title") or "", (entry.get("user") or {}).get("username") or "", "SoundCloud",
                      entry.get("permalink_url") or "")
                for entry in found if entry.get("kind") == "track" and entry.get("policy") not in ("SNIP", "BLOCK")
                and open_streams(entry)]

    def find(self, track):
        """The sound of a library track: Track(title, artist, source, url, …) from library.py."""
        track_key = track_name(track.artist, track.title)
        if track.source == "SoundCloud" and track.url:
            return self.stream(self.api("resolve", url=track.url), track.url)
        page = self.remembered(track_key)
        if page:
            try:
                return self.stream(self.api("resolve", url=page), page)
            except StreamFailed:
                self.forget(track.artist, track.title)
        source = self.stream(self.search(track.artist, track.title))
        self.remember(track_key, source.page)
        return source


class Audio:
    """Whole tracks kept as files, so a track found in advance or played before starts at once.
    An HLS stream is fetched segment by segment, several at a time; for AAC the init part and the
    segments joined in order are an ordinary fragmented MP4 file. The folder keeps to a size."""

    LIMIT = 1500 * 1024 * 1024
    WORKERS = 8

    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def path(self, artist, title):
        name = hashlib.blake2b(track_name(artist, title).encode("utf-8"), digest_size=12).hexdigest()
        return self.folder / f"{name}.m4a"

    def has(self, artist, title):
        return self.path(artist, title).exists()

    def fetch(self, source, artist, title, cancelled=lambda: False):
        target = self.path(artist, title)
        if target.exists():
            return target
        try:
            first = self.get(source.url)
            listing = first[:16].decode("utf-8", "replace")
            if not listing.startswith("#EXTM3U"):
                data = first
            else:
                text = first.decode("utf-8", "replace")
                base = source.url.split("?", 1)[0].rsplit("/", 1)[0]
                absolute = lambda link: link if link.startswith("http") else f"{base}/{link}"
                head = re.search(r'#EXT-X-MAP:URI="([^"]+)"', text)
                parts = [absolute(line.strip()) for line in text.splitlines() if line.strip() and not line.startswith("#")]
                if not parts or not head:
                    raise StreamFailed("Этот поток не сохранить файлом.")
                pieces = self.get_all([absolute(head[1])] + parts)
                if cancelled():
                    return None
                data = b"".join(pieces)
        except StreamFailed:
            raise
        except Exception as error:
            raise StreamFailed("Не удалось скачать трек.") from error
        partial = target.with_suffix(".part")
        partial.write_bytes(data)
        partial.replace(target)
        self.trim()
        return target

    @staticmethod
    def get(address, limit=64 * 1024 * 1024):
        from urllib.request import Request
        from web import AGENT, opener
        with opener.open(Request(address, headers={"User-Agent": AGENT}), timeout=20) as response:
            return response.read(limit)

    def get_all(self, addresses):
        """Fetches many pieces at once on daemon threads (a thread pool's threads would be waited
        for when the app closes) and returns them in order."""
        pieces = [None] * len(addresses)
        failures = []
        jobs = queue.Queue()
        for index, address in enumerate(addresses):
            jobs.put((index, address))

        def work():
            while True:
                try:
                    index, address = jobs.get_nowait()
                except queue.Empty:
                    return
                try:
                    pieces[index] = self.get(address)
                except Exception as error:
                    failures.append(error)
                    return
        threads = [threading.Thread(target=work, daemon=True) for _ in range(min(self.WORKERS, len(addresses)))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if failures or any(piece is None for piece in pieces):
            raise StreamFailed("Не удалось скачать трек.")
        return pieces

    def trim(self):
        files = sorted(self.folder.glob("*.m4a"), key=lambda item: item.stat().st_atime)
        total = sum(item.stat().st_size for item in files)
        for item in files:
            if total <= self.LIMIT:
                break
            total -= item.stat().st_size
            item.unlink(missing_ok=True)
