"""Tracks close to a given one: what a jam and "Мой поток" are made of. Nothing here touches Qt,
and tracks() waits on the network for several seconds, so call it from a worker thread.

Three services are asked at once and their answers are blended:
  Deezer      the radio of the track's artist and the artists Deezer puts next to them (open API);
  YouTube     the mix YouTube plays after the track (read with yt-dlp, nothing is downloaded);
  SoundCloud  what its station plays after the track. It is trusted only when the upload is a
              well-played one: after a re-upload with a few thousand plays it answers with anything,
              and after an artist's own upload with little but that artist.
A track two services agree on comes first. Versions the seed is not (a remix, slowed, live) are left
out, an artist gets a few places and not the whole list, and the same artist does not play twice
in a row. Names are compared by how they sound, so "Max Korzh" and «Макс Корж» are one artist."""
import json
import queue
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from importlib.util import find_spec
from urllib.error import HTTPError
from urllib.parse import quote

import stream
from library import Track, https_url, key, text
from lyrics import same_artist
from web import steady


DEEZER = "https://api.deezer.com"
# Deezer's front refuses about every second request at random, whatever the pace: a refusal is
# asked again this many times, this many seconds apart.
ATTEMPTS = 8
PAUSE = 0.5
# How long the services are waited for; what has not answered by then is left out.
PATIENCE = 22
# How much the word of a service weighs, and whose spelling of a track is kept when several have it.
WEIGHT = {"Deezer": 1.0, "YouTube": 1.0, "SoundCloud": 0.6}
SPELLING = ("Deezer", "YouTube", "SoundCloud")
# SoundCloud's station is believed after an upload played at least this many times.
TRUSTED_PLAYS = 50_000
# A track shorter or longer than this (seconds) is an intro, a skit, a set or a whole album.
SHORTEST, LONGEST = 60, 600
VERSIONS = re.compile(r"\b(" + "|".join(re.escape(word) for word in stream.VERSIONS +
                                        ("mashup", "tiktok", "edit", "speed", "концерт", "concert", "acoustic", "акустика")) + r")\b")
JOINED = re.compile(r"\s*(?:,|&|;|\bfeat\.?|\bft\.?|\bfeaturing\b|\sx\s|\sх\s|\swith\s|/)\s*", re.I)
DASH = re.compile(r"\s+-\s+|\s*[–—]\s*")
NOISE = re.compile(r"\s*[(\[][^)\]]*(official|video|audio|lyric|prod|премьера|клип|mood|visual|subtitles|\b(19|20)\d\d\b|\bhd\b|\b4k\b)"
                   r"[^)\]]*[)\]]", re.I)
CHANNEL = re.compile(r"\s*(-\s*topic|vevo|official\s*fanpage|official|music)\s*$", re.I)


class Nothing(Exception):
    """No service had anything close to the track. The message is worded for the user."""


class Unavailable(Exception):
    """A service could not be asked or answered in a way that was not expected."""


@dataclass
class Pick:
    """A track found close to the seed, with the picture its service has for it."""
    track: Track
    artwork: str = ""
    seconds: int = 0


@dataclass
class Found:
    pick: Pick
    artist: str            # voice() of its main artist
    song: str              # song_key() of it
    source: str
    points: float = 0.0
    sources: set = field(default_factory=set)


def main_artist(name):
    """The first of the artists a line names: "A & B", "A feat. B", "A, B"."""
    first = JOINED.split(name.strip(), maxsplit=1)[0].strip()
    return first or name.strip()


voice = stream.voice      # a name by its sound, the same for either alphabet


def song_key(artist, title):
    """What makes two entries the same song whichever service and spelling they come from. What
    stands in brackets after the title, (feat. …) or (Акустика), is not part of it."""
    plain = re.sub(r"\s*[(\[][^)\]]*[)\]]", " ", title)
    return voice(main_artist(artist)) + "\n" + (voice(stream.clean(plain)) or voice(stream.clean(title)) or key(title))


def mentions(artist, *places):
    """Whether an artist is named in any of the places, by sound: «МС ХОВАНСКИЙ» names MC Khovansky."""
    wanted = voice(main_artist(artist))
    heard = " ".join(voice(place) for place in places)
    there = set(heard.split())
    return bool(wanted) and (wanted in heard or any(len(word) >= 5 and word in there for word in wanted.split()))


def russian(title):
    return bool(re.search("[а-яё]", title.lower()))


def tidy(title):
    """A title without what uploaders hang on it: (Official Video), [Lyric Video, 2025], 16+."""
    title = NOISE.sub(" ", title)
    title = re.sub(r"\s*\b1[68]\+\s*$", "", title)
    return " ".join(title.split()).strip(" -–—|")


def named(shown, uploader):
    """(artist, title) of an upload: "FACE - Бургер (prod. by X)" by anybody, or «Бургер» by FACE."""
    shown = re.sub(r"^\d{1,2}[.)]\s+", "", tidy(shown))
    parts = DASH.split(shown, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        artist, title = parts[0].strip(), parts[1].strip()
        # «Ленинград — Вояж / Leningrad — Voyage»: the same once more in another language.
        halves = title.split(" / ", 1)
        if len(halves) == 2 and DASH.search(halves[1]):
            title = halves[0].strip()
        return artist, title
    return CHANNEL.sub("", uploader).strip() or uploader.strip(), shown


def names_of(track):
    """The artist and the title of a track as people know them. A SoundCloud track is kept the way
    its uploader named it, which is often "Artist - Title" under the name of whoever uploaded it."""
    if track.source in ("SoundCloud", "YouTube"):
        return named(track.title, track.artist)
    return track.artist, track.title


def rows(data):
    found = data.get("data") if isinstance(data, dict) else None
    return [row for row in found if isinstance(row, dict)] if isinstance(found, list) else []


def ask(path, cancelled=lambda: False):
    """What Deezer holds at a path of its API."""
    for attempt in range(ATTEMPTS):
        if cancelled():
            raise Unavailable("cancelled")
        try:
            data = json.loads(steady(f"{DEEZER}/{path}", 8 * 1024 * 1024))
            break
        except HTTPError as error:
            error.close()
            if error.code not in (403, 429) or attempt + 1 == ATTEMPTS:
                raise Unavailable(f"HTTP {error.code}") from error
        except (OSError, ValueError) as error:
            raise Unavailable(str(error)) from error
        time.sleep(PAUSE)
    if not isinstance(data, dict) or data.get("error"):
        raise Unavailable(path)
    return data


def singer(row):
    artist = row.get("artist")
    return artist if isinstance(artist, dict) else {}


def deezer_artist(artist, title, cancelled=lambda: False):
    """(number, name) of the artist on Deezer, or None. The track is searched for first: namesakes
    are many ("LSP" is two artists there, "Face" seven), and the track tells which one is meant."""
    wanted = main_artist(artist)
    queries = [f"{wanted} {title}"]
    if not re.search("[а-яё]", wanted.lower()):
        # Spotify spells Russian artists in Latin letters, Deezer in Russian ones: My is «МЫ».
        queries.append(f"{stream.to_cyrillic(wanted)} {title}")
    wanted_title = voice(stream.clean(title))
    for query in queries:
        found = [row for row in rows(ask(f"search?q={quote(query)}&limit=10", cancelled))
                 if same_artist(wanted, text(singer(row).get("name"))) and isinstance(singer(row).get("id"), int)]
        exact = [row for row in found if voice(stream.clean(text(row.get("title")))) == wanted_title]
        for row in exact or found:
            return singer(row)["id"], text(singer(row).get("name"))
    known = [row for row in rows(ask(f"search/artist?q={quote(wanted)}&limit=10", cancelled))
             if same_artist(wanted, text(row.get("name"))) and isinstance(row.get("id"), int)
             and isinstance(row.get("nb_fan"), int) and row["nb_fan"] >= 500]
    best = max(known, key=lambda row: row["nb_fan"], default=None)
    return (best["id"], text(best.get("name"))) if best else None


def deezer_pick(row):
    album = row.get("album") if isinstance(row.get("album"), dict) else {}
    seconds = row.get("duration") if isinstance(row.get("duration"), int) else 0
    return Pick(Track(text(row.get("title")), text(singer(row).get("name")), "Deezer", https_url(row.get("link"))),
                https_url(album.get("cover_xl")) or https_url(album.get("cover_big")), seconds)


def together(*jobs):
    """Runs the jobs at once on daemon threads and returns what each gave, or its exception."""
    results = [None] * len(jobs)

    def run(place, job):
        try:
            results[place] = job()
        except Exception as error:
            results[place] = error
    threads = [threading.Thread(target=run, args=(place, job), daemon=True) for place, job in enumerate(jobs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


class Lane:
    """One daemon thread that does jobs in turn. SoundCloud is asked through a yt-dlp session that
    belongs to its thread and takes seconds to set up, so its questions all go through this one."""

    def __init__(self):
        self.jobs = queue.Queue()
        self.thread = None

    def run(self, job):
        """Starts the job and returns a function that waits for its result (or raises what it raised)."""
        if self.thread is None:
            self.thread = threading.Thread(target=self.work, daemon=True)
            self.thread.start()
        done, box = threading.Event(), []
        self.jobs.put((job, done, box))

        def result(timeout):
            if not done.wait(timeout):
                raise Unavailable("no answer in time")
            if isinstance(box[0], Exception):
                raise box[0]
            return box[0]
        return result

    def work(self):
        while True:
            job, done, box = self.jobs.get()
            try:
                box.append(job())
            except Exception as error:
                box.append(error)
            done.set()


def blend(seed, lists, near=(), taste=(), count=40, skip=(), avoid=None):
    """The answers of the services as one list of Pick, closest first, without the seed itself.
    lists: {service: [Pick, …] in the order the service gave}; near: voices of the artists said to
    be close to the seed's; taste: voices of the artists the listener already has; skip: song keys
    to leave out; avoid: {voice of an artist: how many more times the listener switched them off
    than listened to them}: such an artist goes down, and from the fourth time is left out."""
    avoid = avoid or {}
    seed_artist, seed_title = names_of(seed)
    own = voice(main_artist(seed_artist))
    seed_song = song_key(seed_artist, seed_title)
    allowed = set(VERSIONS.findall(key(seed_title)))
    skip = set(skip) | {seed_song}
    merged = {}
    for source in SPELLING:
        found = lists.get(source) or []
        for place, pick in enumerate(found):
            artist, title = names_of(pick.track)
            if not artist or not title:
                continue
            song = song_key(artist, title)
            if song in skip or set(VERSIONS.findall(key(pick.track.title))) - allowed:
                continue
            if avoid.get(voice(main_artist(artist)), 0) >= 4:
                continue
            if pick.seconds and not SHORTEST <= pick.seconds <= LONGEST:
                continue
            entry = merged.get(song)
            if entry is None:
                entry = merged[song] = Found(pick, voice(main_artist(artist)), song, source)
            elif russian(pick.track.title) and not russian(entry.pick.track.title):
                # Deezer has some Russian songs under transliterated titles ("Telo"): the title in
                # its own letters is the one a search finds.
                entry.pick = pick
            if source in entry.sources:
                continue        # one service listing a song twice (two uploads of it) says it once
            entry.sources.add(source)
            entry.points += WEIGHT[source] * (1 - 0.6 * place / len(found))
    heard_in = {}
    for entry in merged.values():
        heard_in.setdefault(entry.artist, set()).update(entry.sources)
    near, taste = set(near), set(taste)
    for entry in merged.values():
        entry.points += 0.25 * (len(heard_in[entry.artist]) > 1) + 0.35 * (entry.artist in near) + 0.2 * (entry.artist in taste)
        entry.points -= 0.3 * min(3, avoid.get(entry.artist, 0))
    waiting = sorted(merged.values(), key=lambda entry: -entry.points)
    most_own, most_each = max(2, round(count * 0.12)), max(2, round(count * 0.075))
    chosen, places = [], Counter()
    while waiting and len(chosen) < count:
        lately = {entry.artist for entry in chosen[-2:]}
        entry = next((entry for entry in waiting if entry.artist not in lately), waiting[0])
        waiting.remove(entry)
        if places[entry.artist] >= (most_own if entry.artist == own else most_each):
            continue
        places[entry.artist] += 1
        chosen.append(entry)
    return [entry.pick for entry in chosen]


class Similar:
    def __init__(self, resolver):
        self.resolver = resolver
        self.soundcloud_lane = Lane()
        self.numbers = {}        # voice of an artist → what deezer_artist() found, while the app runs

    # ---- the services ----

    def deezer(self, seed, cancelled):
        """([Pick] of the artist's radio, {voice: number} of the artists next to them)."""
        artist, title = names_of(seed)
        name = voice(main_artist(artist))
        if name not in self.numbers:
            self.numbers[name] = deezer_artist(artist, title, cancelled)
        if not self.numbers[name]:
            return [], {}
        number = self.numbers[name][0]
        radio, related = together(lambda: ask(f"artist/{number}/radio?limit=60", cancelled),
                                  lambda: ask(f"artist/{number}/related?limit=20", cancelled))
        if isinstance(radio, Exception):
            raise radio
        near = {} if isinstance(related, Exception) else {voice(text(row.get("name"))): row["id"] for row in rows(related)
                                                          if isinstance(row.get("id"), int) and text(row.get("name"))}
        return [deezer_pick(row) for row in rows(radio) if text(row.get("title"))], near

    def tops(self, numbers, cancelled):
        """The most played tracks of several Deezer artists, a few of each, taken in turn."""
        found = together(*(lambda number=number: rows(ask(f"artist/{number}/top?limit=4", cancelled)) for number in numbers))
        lists = [[deezer_pick(row) for row in part if text(row.get("title"))] for part in found if not isinstance(part, Exception)]
        return [picks[place] for place in range(4) for picks in lists if place < len(picks)]

    def youtube(self, seed):
        """The mix YouTube makes for the track, as [Pick]."""
        if not find_spec("yt_dlp"):
            return []
        import yt_dlp
        artist, title = names_of(seed)
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True,
                               "socket_timeout": 15, "playlistend": 50}) as session:
            found = (session.extract_info(f"ytsearch3:{main_artist(artist)} {title}", download=False) or {}).get("entries") or []
            wanted = voice(stream.clean(title))
            video = next((entry for entry in found if entry and entry.get("id")
                          and wanted in voice(stream.clean(entry.get("title") or ""))
                          and mentions(artist, entry.get("title") or "", entry.get("channel") or entry.get("uploader") or "")
                          and not set(VERSIONS.findall(key(entry.get("title") or ""))) - set(VERSIONS.findall(key(title)))), None)
            if video is None:
                return []
            mix = (session.extract_info(f"https://www.youtube.com/watch?v={video['id']}&list=RD{video['id']}", download=False)
                   or {}).get("entries") or []
        picks = []
        for entry in mix:
            if not entry or not entry.get("title") or not entry.get("id") or entry["id"] == video["id"]:
                continue
            singer_, song = named(entry["title"], entry.get("channel") or entry.get("uploader") or "")
            if singer_ and song:
                picks.append(Pick(Track(song, singer_, "YouTube", f"https://www.youtube.com/watch?v={entry['id']}"), "",
                                  int(entry.get("duration") or 0)))
        return picks

    def soundcloud(self, seed):
        """What SoundCloud's station plays after the track, as [Pick]: only uploads people do play."""
        resolver = self.resolver
        if seed.source == "SoundCloud" and seed.url:
            item = resolver.api("resolve", url=seed.url)
        else:
            page = resolver.remembered(stream.track_name(seed.artist, seed.title))
            item = resolver.api("resolve", url=page) if page else resolver.search(seed.artist, seed.title)
        plays = item.get("playback_count") or 0
        if seed.source != "SoundCloud" and plays < TRUSTED_PLAYS:
            return []
        least = min(30_000, max(500, plays // 4))
        picks = []
        for entry in resolver.api(f"tracks/{item['id']}/related", limit=40).get("collection") or []:
            if entry.get("kind") != "track" or entry.get("policy") in ("SNIP", "BLOCK") or not stream.open_streams(entry):
                continue
            if (entry.get("playback_count") or 0) < least or not entry.get("title") or not entry.get("permalink_url"):
                continue
            artwork = (entry.get("artwork_url") or "").replace("-large.", "-t500x500.")
            picks.append(Pick(Track(entry["title"], (entry.get("user") or {}).get("username") or "", "SoundCloud", entry["permalink_url"]),
                              artwork, int((entry.get("full_duration") or entry.get("duration") or 0) / 1000)))
        return picks

    # ---- the whole ----

    def tracks(self, seed, count=40, skip=(), taste=(), avoid=None, cancelled=lambda: False):
        """Up to count Picks close to the seed, closest first, without the seed and without the
        songs whose keys are in skip. Raises Nothing when no service had an answer."""
        started = time.monotonic()
        from_soundcloud = self.soundcloud_lane.run(lambda: self.soundcloud(seed))
        from_deezer, from_youtube = together(lambda: self.deezer(seed, cancelled), lambda: self.youtube(seed))
        lists, near = {}, {}
        if not isinstance(from_deezer, Exception):
            lists["Deezer"], near = from_deezer
        if not isinstance(from_youtube, Exception):
            lists["YouTube"] = from_youtube
        try:
            lists["SoundCloud"] = from_soundcloud(max(1.0, PATIENCE - (time.monotonic() - started)))
        except Exception:
            pass
        picks = blend(seed, lists, near, taste, count, skip, avoid)
        if len(picks) < count * 0.6 and near and not cancelled():
            # Too few: the best known tracks of the artists next to the seed's fill the list up.
            busy = Counter(voice(main_artist(names_of(pick.track)[0])) for pick in picks)
            spare = [number for name, number in near.items() if busy[name] < 2][:8]
            if spare:
                lists["Deezer"] = (lists.get("Deezer") or []) + self.tops(spare, cancelled)
                picks = blend(seed, lists, near, taste, count, skip, avoid)
        if not picks:
            if all(isinstance(part, Exception) for part in (from_deezer, from_youtube)) and "SoundCloud" not in lists:
                raise Nothing("Не удалось спросить сервисы о похожих треках. Проверьте интернет и попробуйте снова.")
            raise Nothing("Похожих треков не нашлось: этот трек слишком мало кто знает.")
        return picks
