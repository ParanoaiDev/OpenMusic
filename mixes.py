"""The mixes of the home screen. The listener's artists are gathered into circles of artists that
go together, and each circle becomes a mix: the listener's own tracks of those artists topped up
with the best known tracks of the artists next to them. Nothing here touches Qt.

What goes together is what Deezer says (open API, no key): two artists are close when one is among
the artists Deezer lists next to the other, or when the lists next to them overlap. build() asks
about every artist once, which takes a minute, so it is for a worker thread; what it returns is
plain data to keep on disk, and arrange() turns it into the mixes of a given day."""
import hashlib
import random
import threading
from collections import Counter

import similar
from library import Track, key, text
from similar import main_artist, song_key, voice

# How many of the listener's artists are asked about, the ones with most tracks first.
ARTISTS = 60
WORKERS = 4
# Circles are joined while they are at least this close; see closeness().
CLOSE = 0.2
# A circle becomes a mix when the listener has at least this many tracks in it: the rest of a
# small one is filled with new tracks.
SMALLEST = 2
MIXES = 6
# How many artists next to a circle bring their tracks into its mix, and how many tracks each.
NEIGHBOURS, TRACKS_EACH = 8, 2
OWN, LENGTH = 18, 32


def signature(tracks):
    """Changes when the artists of the library change: what is kept on disk is built for one."""
    names = sorted({voice(main_artist(track.artist)) for track in tracks})
    return hashlib.blake2b("\n".join(names).encode("utf-8"), digest_size=10).hexdigest()


def in_turn(jobs, workers=WORKERS, cancelled=lambda: False):
    """Runs the jobs a few at a time on daemon threads; the results in order, an exception in place
    of a job that failed."""
    results, lock, left = [None] * len(jobs), threading.Lock(), list(enumerate(jobs))

    def work():
        while not cancelled():
            with lock:
                if not left:
                    return
                place, job = left.pop(0)
            try:
                results[place] = job()
            except Exception as error:
                results[place] = error
    threads = [threading.Thread(target=work, daemon=True) for _ in range(min(workers, len(jobs)))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def neighbours(artist, title, cancelled=lambda: False):
    """The artists Deezer lists next to one, as [(voice, name, number)]; [] when it does not know them."""
    found = similar.deezer_artist(artist, title, cancelled)
    if not found:
        return []
    related = similar.rows(similar.ask(f"artist/{found[0]}/related?limit=25", cancelled))
    return [(voice(text(row.get("name"))), text(row.get("name")), row["id"]) for row in related
            if isinstance(row.get("id"), int) and text(row.get("name"))]


def closeness(one, other, next_to):
    """How close two artists are, 0…1.6: named next to each other, and sharing neighbours."""
    a, b = next_to.get(one, set()), next_to.get(other, set())
    direct = 0.6 * ((other in a) + (one in b)) / 2 + 0.3 * (other in a or one in b)
    shared = len((a | {one}) & (b | {other})) / max(1, len(a | b | {one, other}))
    return direct + shared


def circles(artists, next_to, close=CLOSE):
    """Gathers artists into circles: the two closest circles are joined, again and again, while
    they are close enough. artists: voices; next_to: {voice: set of voices next to it}."""
    groups = [[artist] for artist in artists]

    def between(first, second):
        return sum(closeness(a, b, next_to) for a in first for b in second) / (len(first) * len(second))
    while len(groups) > 1:
        best, pair = 0.0, None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                value = between(groups[i], groups[j])
                if value > best:
                    best, pair = value, (i, j)
        if pair is None or best < close:
            break
        i, j = pair
        groups[i] += groups.pop(j)
    return groups


def build(tracks, cancelled=lambda: False):
    """What the mixes are made of, for the tracks of the library: plain data to keep on disk, or
    None when Deezer could not be asked. {signature, circles: [{artists: [names], own: [tracks],
    new: [tracks with artwork]}]}, each track a dict."""
    mine = {}
    for track in tracks:
        if track.url.startswith("file://") and not track.artist:
            continue
        mine.setdefault(voice(main_artist(track.artist)), []).append(track)
    ranked = sorted(mine, key=lambda name: -len(mine[name]))[:ARTISTS]
    found = in_turn([lambda name=name: neighbours(mine[name][0].artist, mine[name][0].title, cancelled) for name in ranked],
                    cancelled=cancelled)
    if cancelled() or all(isinstance(part, Exception) for part in found):
        return None
    listed = {name: part for name, part in zip(ranked, found) if not isinstance(part, Exception) and part}
    next_to = {name: {row[0] for row in part} for name, part in listed.items()}
    numbers = {row[0]: (row[1], row[2]) for part in listed.values() for row in part}
    groups = [group for group in circles(list(listed), next_to) if sum(len(mine[name]) for name in group) >= SMALLEST]
    groups.sort(key=lambda group: -sum(len(mine[name]) for name in group))
    result = []
    owned = {song_key(track.artist, track.title) for track in tracks}
    for group in groups[:MIXES]:
        # The artists most of the circle is next to, and whom the listener does not have yet.
        votes = Counter(name for artist in group for name in next_to[artist] if name not in mine)
        wanted = [name for name, _ in votes.most_common(NEIGHBOURS)]
        tops = in_turn([lambda name=name: similar.rows(similar.ask(f"artist/{numbers[name][1]}/top?limit=6", cancelled))
                        for name in wanted], cancelled=cancelled)
        new = []
        for part in tops:
            taken = 0
            # Deezer keeps some Russian songs under transliterated titles ("Po glazam"): of an
            # artist's tracks the ones titled in Russian letters go first.
            for row in [] if isinstance(part, Exception) else sorted(part, key=lambda row: not similar.russian(text(row.get("title")))):
                pick = similar.deezer_pick(row)
                name = song_key(pick.track.artist, pick.track.title)
                if not pick.track.title or name in owned or similar.VERSIONS.findall(key(pick.track.title)) or taken == TRACKS_EACH:
                    continue
                owned.add(name)
                taken += 1
                new.append(dict(title=pick.track.title, artist=pick.track.artist, source=pick.track.source, url=pick.track.url,
                                artwork=pick.artwork))
        group.sort(key=lambda name: -len(mine[name]))
        result.append(dict(artists=[mine[name][0].artist for name in group],
                           own=[dict(title=track.title, artist=track.artist, source=track.source, url=track.url)
                                for name in group for track in mine[name]], new=new))
    return dict(signature=signature(tracks), circles=result,
                next_to={mine[name][0].artist: sorted(numbers[other][0] for other in next_to[name]) for name in listed})


def arrange(built, day=0):
    """The mixes of a day from what build() returned: [(tracks, artist names, {(artist, title):
    artwork})]. A mix starts with a track of the listener's own, then theirs and new ones take
    turns; the order changes with the day."""
    mixes = []
    for number, circle in enumerate(built.get("circles") or []):
        order = random.Random(day * 31 + number)
        own = [Track(item["title"], item["artist"], item["source"], item["url"]) for item in circle.get("own") or []]
        new = [Track(item["title"], item["artist"], item["source"], item["url"]) for item in circle.get("new") or []]
        artwork = {(item["artist"], item["title"]): item.get("artwork") or "" for item in circle.get("new") or []}
        order.shuffle(own)
        order.shuffle(new)
        own = own[:OWN]
        tracks = []
        while (own or new) and len(tracks) < LENGTH:
            if own:
                tracks.append(own.pop(0))
            if new and len(tracks) < LENGTH:
                tracks.append(new.pop(0))
        if tracks:
            mixes.append((tracks, list(circle.get("artists") or []), artwork))
    return mixes
