"""Song text with timing, from LRCLIB (https://lrclib.net). Nothing here touches Qt: lyrics() waits
on the network, so call it from a worker thread."""
import json
import re
import sqlite3
import time
from contextlib import closing
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode

from library import key, text
from web import page


API = "https://lrclib.net/api"
AGENT = "OpenMusic/0.1"
# LRCLIB counts two recordings as the same when their lengths differ by no more than this.
SLACK_MS = 2000
# How long the last line lasts when neither the text nor the caller says where the track ends.
LAST_LINE_MS = 5000
# LRCLIB times lines, not words. A line lasts until the next one, and that can include a break
# nobody sings through, so a word spread over a line never gets longer than this.
WORD_MS = 1000
# Timing made for a recording this much longer or shorter than the one that plays is still shown,
# marked approximate: most often the difference is silence or an outro at the end.
NEAR_MS = 20000
# A track without text is asked about again after this long: LRCLIB keeps growing.
MISS_SECONDS = 7 * 24 * 3600
# "Nothing found" remembered before this moment came from an older, weaker way of looking (it
# missed artists that Spotify spells in Latin letters), so it is asked about again.
MISSES_SINCE = 1795431087
# Text without timing is paced over the track: this share of it passes before the first line and
# after the last one, where most songs have no singing.
INTRO_SHARE, OUTRO_SHARE = 0.07, 0.06

STAMP = r"(\d+):(\d{1,2})(?:[.:](\d{1,3}))?"
LINE_STAMP = re.compile(rf"\s*\[{STAMP}\]")
WORD_STAMP = re.compile(rf"<{STAMP}>")
DASH = r"\s+[-–—]\s+"


class LyricsFailed(Exception):
    """LRCLIB could not be asked. The message is worded for the user."""


@dataclass(frozen=True)
class Word:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class Line:
    start_ms: int | None
    end_ms: int | None
    text: str
    words: list = field(default_factory=list)


@dataclass(frozen=True)
class Lyrics:
    synced: bool
    lines: list
    instrumental: bool = False
    # The timing was made for a recording of a slightly different length: it may run apart.
    approximate: bool = False


def milliseconds(stamp):
    minutes, seconds, fraction = stamp.groups()
    return int(minutes) * 60000 + int(seconds) * 1000 + int((fraction or "").ljust(3, "0"))


def spread(body, start, end, longest=WORD_MS):
    """The words of a stretch of text, each given an equal share of the time."""
    parts = []
    for part in body.split():
        # A dash or other mark standing alone is not sung, so it rides with the word before it.
        if parts and not any(char.isalnum() for char in part):
            parts[-1] += " " + part
        else:
            parts.append(part)
    step = min((end - start) / len(parts), longest) if parts else 0
    return [Word(round(start + step * index), round(start + step * (index + 1)), part) for index, part in enumerate(parts)]


def parse_lrc(source, duration_ms=None):
    """The timed lines of an LRC text, in order. A stamp with no text is a pause: it ends the line
    before it and is not a line itself. duration_ms tells where the last line ends."""
    offset = re.search(r"^\s*\[offset:\s*([+-]?\d+)\s*\]\s*$", source, re.I | re.M)
    # A positive offset makes the text come sooner.
    shift = -int(offset[1]) if offset else 0
    rows = []
    for row in source.splitlines():
        stamps = []
        position = 0
        while stamp := LINE_STAMP.match(row, position):
            stamps.append(milliseconds(stamp))
            position = stamp.end()
        # A line repeated in the song carries one stamp per repeat; word stamps belong to the first.
        rows += [(max(0, start + shift), start - stamps[0], row[position:].strip()) for start in stamps]
    rows.sort(key=lambda row: row[0])
    lines = []
    for index, (start, repeat, body) in enumerate(rows):
        if index + 1 < len(rows):
            end = rows[index + 1][0]
        else:
            end = duration_ms if duration_ms and duration_ms > start else start + LAST_LINE_MS
        marks = list(WORD_STAMP.finditer(body))
        if not marks:
            if body:
                lines.append(Line(start, end, " ".join(body.split()), spread(body, start, end)))
            continue
        # Enhanced LRC: each <stamp> starts the words after it, and a last one with nothing after it ends the line.
        pieces = [(start, body[:marks[0].start()])] + [
            (max(0, milliseconds(mark) + shift + repeat), body[mark.end():following.start() if following else len(body)])
            for mark, following in zip(marks, marks[1:] + [None])]
        words = []
        for (began, piece), following in zip(pieces, pieces[1:] + [None]):
            # Between two word stamps the length is given; only after the last one is it a guess.
            ended, longest = (following[0], float("inf")) if following else (end, WORD_MS)
            words += spread(piece, began, max(began, ended), longest)
        if words:
            lines.append(Line(start, end, " ".join(word.text for word in words), words))
    return lines


def fits(record, duration_ms, slack=SLACK_MS):
    seconds = record.get("duration")
    return not duration_ms or (isinstance(seconds, (int, float)) and abs(seconds * 1000 - duration_ms) <= slack)


def reading(record, duration_ms=None):
    """The Lyrics an LRCLIB record holds, or None when it holds no text. Timing made for a recording
    of another length would run apart from the music, so then only the words are kept."""
    if record.get("instrumental") is True:
        return Lyrics(False, [], True)
    seconds = record.get("duration")
    length = duration_ms or (round(seconds * 1000) if isinstance(seconds, (int, float)) else None)
    timed = parse_lrc(text(record.get("syncedLyrics")), length)
    if timed and fits(record, duration_ms):
        return Lyrics(True, timed)
    if timed and fits(record, duration_ms, NEAR_MS):
        return Lyrics(True, timed, approximate=True)
    rows = text(record.get("plainLyrics")).splitlines() or [line.text for line in timed]
    lines = [Line(None, None, " ".join(row.split())) for row in rows if row.strip()]
    return Lyrics(False, lines) if lines else None


def paced(lines, duration_ms):
    """Lines without timing with a guessed one: spread over the track by their length, so that the
    screen can scroll the text along with the music. Not when a line is sung, only about where."""
    lines = [line for line in lines if line.text]
    if not lines or not duration_ms or duration_ms <= 0:
        return lines
    start = duration_ms * INTRO_SHARE
    span = duration_ms * (1 - INTRO_SHARE - OUTRO_SHARE)
    # A short line still takes a breath to sing, so every line weighs a little besides its letters.
    weights = [12 + len(line.text) for line in lines]
    whole = sum(weights)
    result, passed = [], 0
    for line, weight in zip(lines, weights):
        begin = round(start + span * passed / whole)
        passed += weight
        result.append(Line(begin, round(start + span * passed / whole), line.text))
    return result


def bare(title):
    """A title without what services append to it: (feat. X), [Remastered], - Live at Wembley,
    prod. by Somebody."""
    short = re.sub(r"\s*[(\[][^)\]]*[)\]]", "", title)
    short = re.sub(r"\s+(?:prod\.?(?:\s+by)?|feat\.?|ft\.?)\s+\S.*$", "", short, flags=re.I)
    return re.split(DASH, short)[0].strip() or title


def artists(name):
    return {part for part in re.split(r"\s*(?:,|&|;|\bfeat\.?|\bft\.?|\bx\b)\s*", key(name)) if part}


LATIN = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюяәғқңөұүһіїєґ",
                 ("a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f",
                  "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya", "a", "g", "k", "n", "o", "u", "u", "h", "i", "i",
                  "e", "g")))
CYRILLIC = (("shch", "щ"), ("zh", "ж"), ("kh", "х"), ("ts", "ц"), ("ch", "ч"), ("sh", "ш"), ("yu", "ю"), ("ya", "я"), ("yo", "ё"),
            ("a", "а"), ("b", "б"), ("c", "к"), ("d", "д"), ("e", "е"), ("f", "ф"), ("g", "г"), ("h", "х"), ("i", "и"), ("j", "дж"),
            ("k", "к"), ("l", "л"), ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"), ("q", "к"), ("r", "р"), ("s", "с"), ("t", "т"),
            ("u", "у"), ("v", "в"), ("w", "в"), ("x", "кс"), ("y", "й"), ("z", "з"))


def cyrillic(name):
    return bool(re.search("[а-яёәғқңөұүһіїєґ]", name.casefold()))


def latin(name):
    """A name in Latin letters and digits only, the way services spell Russian artists: ЛСП → lsp."""
    return "".join(LATIN.get(char, char) for char in key(name) if char.isalnum())


def to_cyrillic(name):
    """A guess at how a name spelled in Latin letters is written in Russian: Monetochka → монеточка."""
    result = key(name)
    for letters, char in CYRILLIC:
        result = result.replace(letters, char)
    return result


def same_artist(wanted, given):
    """Whether two artist lines name somebody in common, in whichever alphabet each is written."""
    one, other = artists(wanted), artists(given)
    if one & other:
        return True
    for first in one:
        for second in other:
            a, b = latin(first), latin(second)
            if a and b and (a == b or (min(len(a), len(b)) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.8)):
                return True
    return False


def best(records, artist, title, duration_ms=None):
    """The search result to show for a track, or None when none of them is that track. A recording
    of the right length comes first, then one with timing, then one titled exactly alike."""
    wanted = key(bare(title))
    same = [record for record in records if isinstance(record, dict) and reading(record)
            and key(bare(text(record.get("trackName")))) == wanted and same_artist(artist, text(record.get("artistName")))]
    def distance(record):
        seconds = record.get("duration")
        return abs(seconds * 1000 - duration_ms) if duration_ms and isinstance(seconds, (int, float)) else 0
    return min(same, default=None, key=lambda record: (
        not fits(record, duration_ms), not text(record.get("syncedLyrics")),
        key(text(record.get("trackName"))) != key(title), distance(record)))


def fetch(method, **query):
    """What LRCLIB answers, or None where it knows no such track."""
    url = f"{API}/{method}?{urlencode(query)}"
    try:
        try:
            return json.loads(page(url, 4 * 1024 * 1024, 10, AGENT))
        except HTTPError:
            raise
        except OSError:
            # A connection that drops once usually works the second time.
            return json.loads(page(url, 4 * 1024 * 1024, 10, AGENT))
    except HTTPError as error:
        if error.code == 404:
            return None
        if error.code == 429:
            raise LyricsFailed("Сервис текстов LRCLIB временно ограничил число запросов. Попробуйте позже.") from error
        raise LyricsFailed(f"Сервис текстов LRCLIB вернул ошибку HTTP {error.code}.") from error
    except OSError as error:
        raise LyricsFailed("Не удалось связаться с сервисом текстов LRCLIB. Проверьте интернет.") from error
    except ValueError as error:
        raise LyricsFailed("Сервис текстов LRCLIB ответил в неожиданном виде.") from error


def lookup(artist, title, duration_ms=None):
    """The LRCLIB record for a track, or None. Asks for the exact recording first, then searches."""
    if duration_ms:
        record = fetch("get", artist_name=artist, track_name=title, duration=round(duration_ms / 1000))
        if isinstance(record, dict) and reading(record):
            return record
    attempts = [(artist, title)]
    if bare(title) != title:
        attempts.append((artist, bare(title)))
    # A SoundCloud upload is often titled "Artist - Song" under the name of whoever uploaded it.
    halves = re.split(DASH, title, maxsplit=1)
    if len(halves) == 2:
        attempts.append((halves[0], bare(halves[1])))
    # Spotify spells Russian artists in Latin letters (LSP, Monetochka); LRCLIB has them as they
    # are written, and its search does not see one in the other.
    if not cyrillic(artist) and cyrillic(to_cyrillic(artist)):
        attempts.append((to_cyrillic(artist), bare(title)))
    # Last, by the title alone: best() still takes only a record of the same artist, in any alphabet.
    by_title = (None, bare(halves[1]) if len(halves) == 2 else bare(title))
    asked = set()
    for by, name in attempts + [by_title]:
        if not name or (by, name) in asked:
            continue
        asked.add((by, name))
        found = fetch("search", artist_name=by, track_name=name) if by else fetch("search", track_name=name)
        for wanted in ([by] if by else [artist] + halves[:1] * (len(halves) == 2)):
            record = best(found if isinstance(found, list) else [], wanted, name, duration_ms)
            if record:
                return record
    return None


class Cache:
    """What LRCLIB answered, kept in an SQLite file of its own so that a track is asked about once.
    A file that cannot be read or written only costs the memory: nothing here raises."""

    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(self.path)
        try:
            db.execute("""
                CREATE TABLE IF NOT EXISTS lyrics (
                    artist TEXT NOT NULL, title TEXT NOT NULL,
                    checked INTEGER NOT NULL, asked_ms INTEGER, record TEXT,
                    PRIMARY KEY (artist, title)
                ) WITHOUT ROWID
            """)
        except sqlite3.Error:
            db.close()
            raise
        return db

    def get(self, artist, title):
        """(record, the duration it was looked up with), where record is False for a track known
        to have no text. None when nothing is remembered."""
        try:
            with closing(self.connect()) as db:
                row = db.execute("SELECT checked, asked_ms, record FROM lyrics WHERE artist = ? AND title = ?",
                                 (key(artist), key(title))).fetchone()
            if row is None:
                return None
            checked, asked_ms, record = row
            if record is None:
                return (False, asked_ms) if time.time() - checked < MISS_SECONDS and checked >= MISSES_SINCE else None
            return json.loads(record), asked_ms
        except (OSError, ValueError, sqlite3.Error):
            return None

    def put(self, artist, title, record, asked_ms=None):
        try:
            with closing(self.connect()) as db, db:
                db.execute("INSERT OR REPLACE INTO lyrics VALUES (?, ?, ?, ?, ?)",
                           (key(artist), key(title), int(time.time()), asked_ms, json.dumps(record) if record else None))
        except (OSError, sqlite3.Error):
            pass

    def forget(self, artist, title):
        """Drops what is remembered about one track, so that the next lyrics() asks LRCLIB again."""
        try:
            with closing(self.connect()) as db, db:
                db.execute("DELETE FROM lyrics WHERE artist = ? AND title = ?", (key(artist), key(title)))
        except (OSError, sqlite3.Error):
            pass


def lyrics(artist, title, duration_ms=None, cache=None):
    """The text of a track: Lyrics, or None when LRCLIB has none. Raises LyricsFailed, and nothing
    else, when LRCLIB could not be asked. With a Cache the answer is remembered between runs."""
    artist, title = text(artist), text(title)
    if not artist or not title:
        return None
    known = cache.get(artist, title) if cache else None
    if known:
        record, asked_ms = known
        # Remembered for a recording of another length: look once for the one that is playing now.
        stale = record and not fits(record, duration_ms) and not fits({"duration": (asked_ms or 0) / 1000}, duration_ms)
        if not stale:
            return reading(record, duration_ms) if record else None
    record = lookup(artist, title, duration_ms)
    if cache:
        cache.put(artist, title, record, duration_ms)
    return reading(record, duration_ms) if record else None
