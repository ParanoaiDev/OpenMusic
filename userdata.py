"""What the listener makes in OpenMusic itself: liked tracks, playlists and the history of plays.
Kept in its own SQLite file next to the library. No Qt here."""
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from library import Track, key


def track_key(track):
    return f"{key(track.artist)}\n{key(track.title)}"


class UserData:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS likes (
                    track TEXT PRIMARY KEY, title TEXT NOT NULL, artist TEXT NOT NULL,
                    source TEXT NOT NULL, url TEXT NOT NULL, added REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    position REAL NOT NULL, title TEXT NOT NULL, artist TEXT NOT NULL,
                    source TEXT NOT NULL, url TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS history (
                    played REAL NOT NULL, title TEXT NOT NULL, artist TEXT NOT NULL,
                    source TEXT NOT NULL, url TEXT NOT NULL, listened_ms INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS jams (
                    id INTEGER PRIMARY KEY, track TEXT NOT NULL UNIQUE, made REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jam_tracks (
                    jam INTEGER NOT NULL REFERENCES jams(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL, title TEXT NOT NULL, artist TEXT NOT NULL,
                    source TEXT NOT NULL, url TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skips (
                    skipped REAL NOT NULL, title TEXT NOT NULL, artist TEXT NOT NULL,
                    source TEXT NOT NULL, url TEXT NOT NULL
                );
                -- A jam left with its first track alone was being collected when the app closed.
                DELETE FROM jams WHERE (SELECT count(*) FROM jam_tracks WHERE jam = jams.id) < 2;
            """)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA foreign_keys = ON")
        return db

    # ---- likes ----

    def liked(self, track):
        with closing(self.connect()) as db:
            return db.execute("SELECT 1 FROM likes WHERE track = ?", (track_key(track),)).fetchone() is not None

    def set_liked(self, track, liked):
        with closing(self.connect()) as db, db:
            if liked:
                db.execute("INSERT OR REPLACE INTO likes VALUES (?, ?, ?, ?, ?, ?)",
                           (track_key(track), track.title, track.artist, track.source, track.url, time.time()))
            else:
                db.execute("DELETE FROM likes WHERE track = ?", (track_key(track),))

    def likes(self):
        with closing(self.connect()) as db:
            return [Track(title, artist, source, url) for title, artist, source, url in
                    db.execute("SELECT title, artist, source, url FROM likes ORDER BY added DESC")]

    # ---- playlists ----

    def playlists(self):
        """(id, name, number of tracks), newest first."""
        with closing(self.connect()) as db:
            return db.execute("""SELECT playlists.id, name, count(playlist_tracks.playlist) FROM playlists
                                 LEFT JOIN playlist_tracks ON playlists.id = playlist_tracks.playlist
                                 GROUP BY playlists.id ORDER BY created DESC""").fetchall()

    def create_playlist(self, name):
        with closing(self.connect()) as db, db:
            return db.execute("INSERT INTO playlists (name, created) VALUES (?, ?)", (name.strip() or "Плейлист", time.time())).lastrowid

    def rename_playlist(self, playlist, name):
        with closing(self.connect()) as db, db:
            db.execute("UPDATE playlists SET name = ? WHERE id = ?", (name.strip() or "Плейлист", playlist))

    def delete_playlist(self, playlist):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM playlists WHERE id = ?", (playlist,))

    def add_to_playlist(self, playlist, tracks):
        with closing(self.connect()) as db, db:
            last = db.execute("SELECT coalesce(max(position), 0) FROM playlist_tracks WHERE playlist = ?", (playlist,)).fetchone()[0]
            present = {(key(title), key(artist)) for title, artist in
                       db.execute("SELECT title, artist FROM playlist_tracks WHERE playlist = ?", (playlist,))}
            added = 0
            for track in tracks:
                if (key(track.title), key(track.artist)) in present:
                    continue
                present.add((key(track.title), key(track.artist)))
                last += 1
                added += 1
                db.execute("INSERT INTO playlist_tracks VALUES (?, ?, ?, ?, ?, ?)",
                           (playlist, last, track.title, track.artist, track.source, track.url))
            return added

    def remove_from_playlist(self, playlist, track):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM playlist_tracks WHERE playlist = ? AND title = ? AND artist = ?",
                       (playlist, track.title, track.artist))

    def playlist_tracks(self, playlist):
        with closing(self.connect()) as db:
            return [Track(title, artist, source, url) for title, artist, source, url in
                    db.execute("SELECT title, artist, source, url FROM playlist_tracks WHERE playlist = ? ORDER BY position",
                               (playlist,))]

    # ---- jams ----
    # A jam is a list made for the listener from one track: the track itself, then tracks close to
    # it. Only the latest JAMS are kept; one worth keeping is saved as a playlist.

    JAMS = 20

    def save_jam(self, tracks):
        """Keeps a jam, its first track being the one it is made from; a jam made from the same
        track before is replaced. Returns its number."""
        seed = tracks[0]
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM jams WHERE track = ?", (track_key(seed),))
            jam = db.execute("INSERT INTO jams (track, made) VALUES (?, ?)", (track_key(seed), time.time())).lastrowid
            db.executemany("INSERT INTO jam_tracks VALUES (?, ?, ?, ?, ?, ?)",
                           [(jam, place, track.title, track.artist, track.source, track.url) for place, track in enumerate(tracks)])
            db.execute("DELETE FROM jams WHERE id NOT IN (SELECT id FROM jams ORDER BY made DESC LIMIT ?)", (self.JAMS,))
        return jam

    def jams(self):
        """(number, the track it is made from, number of tracks), newest first."""
        with closing(self.connect()) as db:
            rows = db.execute("""SELECT jams.id, first.title, first.artist, first.source, first.url,
                                        (SELECT count(*) FROM jam_tracks WHERE jam = jams.id)
                                 FROM jams JOIN jam_tracks AS first ON first.jam = jams.id AND first.position = 0
                                 ORDER BY made DESC""").fetchall()
        return [(jam, Track(title, artist, source, url), count) for jam, title, artist, source, url, count in rows]

    def jam_tracks(self, jam):
        with closing(self.connect()) as db:
            return [Track(title, artist, source, url) for title, artist, source, url in
                    db.execute("SELECT title, artist, source, url FROM jam_tracks WHERE jam = ? ORDER BY position", (jam,))]

    def delete_jam(self, jam):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM jams WHERE id = ?", (jam,))

    # ---- skips ----
    # A track switched off in its first seconds: a sign that it, and maybe its artist, is not wanted.

    def skipped(self, track):
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO skips VALUES (?, ?, ?, ?, ?)", (time.time(), track.title, track.artist, track.source, track.url))

    def skips(self, since=0.0):
        """[(track, how many times it was skipped)] since a moment."""
        with closing(self.connect()) as db:
            rows = db.execute("""SELECT title, artist, source, url, count(*) FROM skips WHERE skipped >= ?
                                 GROUP BY lower(title), lower(artist)""", (since,)).fetchall()
        return [(Track(title, artist, source, url), count) for title, artist, source, url, count in rows]

    # ---- history ----

    def played(self, track, listened_ms):
        """Notes a play once it has lasted long enough to count."""
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO history VALUES (?, ?, ?, ?, ?, ?)",
                       (time.time(), track.title, track.artist, track.source, track.url, int(listened_ms)))

    def recent(self, limit=30):
        """Tracks played lately, newest first, each once."""
        with closing(self.connect()) as db:
            rows = db.execute("""SELECT title, artist, source, url, max(played) AS last FROM history
                                 GROUP BY lower(title), lower(artist) ORDER BY last DESC LIMIT ?""", (limit,)).fetchall()
        return [Track(title, artist, source, url) for title, artist, source, url, _ in rows]

    def history(self, limit=200):
        """(when, track, listened ms), newest first."""
        with closing(self.connect()) as db:
            rows = db.execute("SELECT played, title, artist, source, url, listened_ms FROM history ORDER BY played DESC LIMIT ?",
                              (limit,)).fetchall()
        return [(played, Track(title, artist, source, url), listened) for played, title, artist, source, url, listened in rows]

    def totals(self, since=0.0):
        """(listened ms, plays, different tracks) since a moment."""
        with closing(self.connect()) as db:
            listened, plays, tracks = db.execute("""SELECT coalesce(sum(listened_ms), 0), count(*),
                                                    count(DISTINCT lower(title) || char(10) || lower(artist))
                                                    FROM history WHERE played >= ?""", (since,)).fetchone()
        return int(listened), int(plays), int(tracks)

    def top_tracks(self, since=0.0, limit=5):
        """The tracks played most since a moment: [(track, plays, listened ms)]."""
        with closing(self.connect()) as db:
            rows = db.execute("""SELECT title, artist, source, url, count(*), sum(listened_ms) FROM history WHERE played >= ?
                                 GROUP BY lower(title), lower(artist) ORDER BY count(*) DESC, sum(listened_ms) DESC LIMIT ?""",
                              (since, limit)).fetchall()
        return [(Track(title, artist, source, url), plays, int(listened)) for title, artist, source, url, plays, listened in rows]

    def stats(self, since=0.0):
        """Listening time and plays by artist since a moment: [(artist, ms, plays)], most first."""
        with closing(self.connect()) as db:
            return db.execute("""SELECT artist, sum(listened_ms), count(*) FROM history WHERE played >= ?
                                 GROUP BY lower(artist) ORDER BY sum(listened_ms) DESC""", (since,)).fetchall()
