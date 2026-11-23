"""Run from the project folder: python3 -m unittest discover tests. Nothing here uses the network:
the services answer from tests/samples, which are real answers cut down to a few tracks."""
import json
import shutil
import subprocess
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit

import apple
import deezer
import local
import yandex
import youtube
from library import Entry, ImportFailed, Library, artist_and_title
from ytdlp import Refused

SAMPLES = Path(__file__).parent / "samples"


def sample(name):
    return (SAMPLES / name).read_text(encoding="utf-8")


def http_error(code, location=None):
    headers = Message()
    if location:
        headers["Location"] = location
    error = HTTPError("https://example.invalid/", code, "refused", headers, None)
    # Python warns about an HTTPError that is dropped unclosed; its code and headers outlive the closing.
    error.close()
    return error


def pairs(entries):
    return [(entry.artist, entry.title) for entry in entries]


class ArtistAndTitle(unittest.TestCase):
    def test_splits_at_the_first_dash_standing_apart(self):
        self.assertEqual(artist_and_title("Sigur Rós - Hoppípolla"), ("Sigur Rós", "Hoppípolla"))
        self.assertEqual(artist_and_title(" Кино — Группа крови "), ("Кино", "Группа крови"))
        self.assertEqual(artist_and_title("a-ha - Take On Me - Live"), ("a-ha", "Take On Me - Live"))

    def test_no_artist_without_a_dash(self):
        self.assertEqual(artist_and_title("Jay-Z"), ("", "Jay-Z"))
        self.assertEqual(artist_and_title(" - Song"), ("", "- Song"))


class Deezer(unittest.TestCase):
    def setUp(self):
        pause = patch.object(deezer, "PAUSE", 0)
        pause.start()
        self.addCleanup(pause.stop)

    def test_playlist(self):
        with patch("deezer.steady", return_value=sample("deezer_playlist.json")) as asked:
            name, entries = deezer.tracks(" https://www.deezer.com/us/playlist/3155776842?utm_source=copy ")
        self.assertEqual(name, "Top Worldwide")
        self.assertEqual(entries, [Entry("Boston", "STELLA LEFTY", "https://www.deezer.com/track/3895241341"),
                                   Entry("Choosin' Texas", "Ella Langley", "https://www.deezer.com/track/3602074142"),
                                   Entry("BbY WOW", "KAROL G", "https://www.deezer.com/track/4208859922")])
        self.assertEqual([call.args[0] for call in asked.call_args_list], ["https://api.deezer.com/playlist/3155776842"])

    def test_album(self):
        with patch("deezer.steady", return_value=sample("deezer_album.json")) as asked:
            name, entries = deezer.tracks("deezer.com/album/302127")
        self.assertEqual((name, pairs(entries)), ("Discovery", [("Daft Punk", "One More Time"), ("Daft Punk", "Aerodynamic"), ("Daft Punk", "Digital Love")]))
        self.assertEqual(asked.call_args.args[0], "https://api.deezer.com/album/302127")

    def test_long_list_is_read_to_the_end(self):
        answers = [sample("deezer_playlist_part.json"), sample("deezer_tracks_page.json")]
        said = []
        with patch("deezer.steady", side_effect=answers) as asked:
            _, entries = deezer.tracks("https://www.deezer.com/playlist/3155776842", report=said.append)
        self.assertEqual(len(entries), 5)
        self.assertEqual(asked.call_args.args[0], "https://api.deezer.com/playlist/3155776842/tracks?index=3&limit=500")
        self.assertEqual(said, ["Deezer · прочитано треков: 3 из 5"])

    def test_list_that_ends_early_does_not_loop(self):
        with patch("deezer.steady", side_effect=[sample("deezer_playlist_part.json"), '{"data": [], "total": 5}']) as asked:
            _, entries = deezer.tracks("https://www.deezer.com/playlist/3155776842")
        self.assertEqual((len(entries), asked.call_count), (3, 2))

    def test_refusal_is_asked_again(self):
        with patch("deezer.steady", side_effect=[http_error(403), http_error(403), sample("deezer_album.json")]) as asked:
            name, _ = deezer.tracks("https://www.deezer.com/album/302127")
        self.assertEqual((name, asked.call_count), ("Discovery", 3))

    def test_endless_refusal_gives_up(self):
        with patch("deezer.steady", side_effect=http_error(403)) as asked:
            with self.assertRaisesRegex(ImportFailed, "HTTP 403"):
                deezer.tracks("https://www.deezer.com/album/302127")
        self.assertEqual(asked.call_count, deezer.ATTEMPTS)

    def test_other_http_errors_are_not_asked_again(self):
        with patch("deezer.steady", side_effect=http_error(500)) as asked:
            with self.assertRaisesRegex(ImportFailed, "HTTP 500"):
                deezer.tracks("https://www.deezer.com/album/302127")
        self.assertEqual(asked.call_count, 1)

    def test_unknown_and_closed(self):
        with patch("deezer.steady", return_value=sample("deezer_missing.json")):
            with self.assertRaisesRegex(ImportFailed, "не нашёл"):
                deezer.tracks("https://www.deezer.com/playlist/1")
        with patch("deezer.steady", return_value='{"error": {"type": "OAuthException", "message": "x", "code": 200}}'):
            with self.assertRaisesRegex(ImportFailed, "закрыт"):
                deezer.tracks("https://www.deezer.com/playlist/1")

    def test_no_connection_and_nonsense(self):
        with patch("deezer.steady", side_effect=URLError("down")):
            with self.assertRaisesRegex(ImportFailed, "Не удалось связаться"):
                deezer.tracks("https://www.deezer.com/playlist/1")
        for body in ("<html>", "[]"):
            with patch("deezer.steady", return_value=body):
                with self.assertRaisesRegex(ImportFailed, "неожиданном виде"):
                    deezer.tracks("https://www.deezer.com/playlist/1")

    def test_other_links_are_turned_away_without_asking(self):
        with patch("deezer.steady") as asked:
            for link in ("", "https://www.deezer.com/track/3135553", "https://www.deezer.com/us/artist/27",
                         "https://evil.example/www.deezer.com/playlist/1", "https://www.deezer.com/playlist/abc"):
                with self.assertRaisesRegex(ImportFailed, "Вставьте ссылку"):
                    deezer.tracks(link)
        asked.assert_not_called()

    def test_short_link_from_the_app(self):
        answers = [http_error(302, "https://www.deezer.com/us/album/302127?host=0&utm_campaign=share"), sample("deezer_album.json")]
        with patch("deezer.steady", side_effect=answers) as asked:
            name, _ = deezer.tracks("https://link.deezer.com/s/30AbC-dEf")
        self.assertEqual(name, "Discovery")
        self.assertEqual([call.args[0] for call in asked.call_args_list],
                         ["https://link.deezer.com/s/30AbC-dEf", "https://api.deezer.com/album/302127"])

    def test_short_link_that_leads_nowhere(self):
        with patch("deezer.steady", side_effect=http_error(302, "https://www.deezer.com/deezer-links-404")):
            with self.assertRaisesRegex(ImportFailed, "короткая ссылка"):
                deezer.tracks("link.deezer.com/s/30AbCdEf")

    def test_cancelled(self):
        with patch("deezer.steady") as asked:
            with self.assertRaisesRegex(ImportFailed, "отменён"):
                deezer.tracks("https://www.deezer.com/playlist/1", lambda: True)
        asked.assert_not_called()


class Yandex(unittest.TestCase):
    def test_playlist(self):
        with patch("yandex.steady", return_value=sample("yandex_playlist.json")):
            name, entries = yandex.tracks("https://music.yandex.ru/users/music.partners/playlists/2050?utm_medium=copy_link")
        self.assertEqual(name, "Best Russian Rock Songs")
        self.assertEqual(entries, [Entry("Группа крови", "КИНО", "https://music.yandex.ru/album/10100/track/106259"),
                                   Entry("Утро", "Дайте танк (!)", "https://music.yandex.ru/album/12348427/track/34942045"),
                                   # What Yandex prints in grey after the title is kept in brackets.
                                   Entry("Москва (на стихи С. Есенина)", "Монгол Шуудан", "https://music.yandex.ru/album/10423/track/110219")])

    def test_album(self):
        with patch("yandex.steady", return_value=sample("yandex_album.json")):
            name, entries = yandex.tracks("music.yandex.ru/album/3389008")
        self.assertEqual((name, pairs(entries)[0], entries[0].url),
                         ("Amnesiac", ("Radiohead", "Packt Like Sardines in a Crushd Tin Box"), "https://music.yandex.ru/album/3389008/track/333442"))

    def test_each_form_of_link_asks_its_own_address(self):
        forms = {
            "https://music.yandex.ru/users/yamusic-top/playlists/1076": "users/yamusic-top/playlists/1076",
            "https://music.yandex.kz/users/some.body@mail/playlists/3/": "users/some.body%40mail/playlists/3",
            "https://music.yandex.ru/playlists/ch.448df3eb-daee-408a-a60a-252259db2f3b?utm_source=web": "playlist/ch.448df3eb-daee-408a-a60a-252259db2f3b",
            "http://music.yandex.com/album/3389008#x": "albums/3389008/with-tracks",
        }
        for link, path in forms.items():
            with patch("yandex.steady", return_value=sample("yandex_album.json")) as asked:
                yandex.tracks(link)
            self.assertEqual(asked.call_args.args[0], f"https://api.music.yandex.net/{path}", link)

    def test_other_links_are_turned_away_without_asking(self):
        with patch("yandex.steady") as asked:
            for link in ("", "https://music.yandex.ru/album/3389008/track/333442", "https://music.yandex.ru/artist/36800",
                         "https://example.com/users/a/playlists/3", "https://music.yandex.ru/users/a/b/playlists/3"):
                with self.assertRaisesRegex(ImportFailed, "Вставьте ссылку"):
                    yandex.tracks(link)
        asked.assert_not_called()

    def test_track_without_a_page_keeps_no_link(self):
        body = json.dumps({"result": {"title": "Моё", "tracks": [
            {"track": {"id": "2f0ac1c4-uploaded", "title": "Демо", "artists": [{"name": "Я"}], "albums": []}},
            {"track": {"id": 77, "title": "Сингл", "artists": [{"name": "Кто-то"}, {"name": "Гость"}], "albums": []}},
            {"track": {"id": 78, "title": "Подкаст без артиста", "artists": []}},
            {"id": 79}]}})
        with patch("yandex.steady", return_value=body):
            _, entries = yandex.tracks("https://music.yandex.ru/users/me/playlists/3")
        self.assertEqual(entries, [Entry("Демо", "Я", ""), Entry("Сингл", "Кто-то", "https://music.yandex.ru/track/77")])

    def test_failures(self):
        link = "https://music.yandex.ru/users/a/playlists/3"
        cases = ((http_error(404), "не нашла"), (http_error(400), "не нашла"), (http_error(500), "HTTP 500"), (URLError("down"), "Не удалось связаться"))
        for error, said in cases:
            with patch("yandex.steady", side_effect=error):
                with self.assertRaisesRegex(ImportFailed, said):
                    yandex.tracks(link)
        for body in ("<html>captcha", "{}", '{"result": {"tracks": 5}}', '{"result": null}'):
            with patch("yandex.steady", return_value=body):
                with self.assertRaisesRegex(ImportFailed, "неожиданном виде"):
                    yandex.tracks(link)
        with patch("yandex.steady", return_value='{"result": {"title": "Пусто", "tracks": []}}'):
            with self.assertRaisesRegex(ImportFailed, "ни одного трека"):
                yandex.tracks(link)


class Apple(unittest.TestCase):
    def test_playlist(self):
        with patch("apple.steady", return_value=sample("apple_playlist.html")) as asked:
            name, entries = apple.tracks("https://music.apple.com/us/playlist/todays-hits/pl.f4d106fed2bd41149aaacabb233eb5eb")
        self.assertEqual(name, "Today’s Hits")
        self.assertEqual(entries, [
            Entry("stupid song", "Olivia Rodrigo", "https://music.apple.com/us/album/stupid-song/1889992111?i=1889992115"),
            Entry("Housewife", "Tate McRae", "https://music.apple.com/us/album/housewife/6822497770?i=6822497774"),
            Entry("Stop The Wedding!", "Ashe", "https://music.apple.com/us/album/stop-the-wedding/6795697684?i=6795697687")])
        self.assertEqual(asked.call_args.args[0], "https://music.apple.com/us/playlist/pl.f4d106fed2bd41149aaacabb233eb5eb")

    def test_album(self):
        with patch("apple.steady", return_value=sample("apple_album.html")) as asked:
            name, entries = apple.tracks("music.apple.com/KZ/album/discovery/697194953?l=ru")
        self.assertEqual((name, pairs(entries)), ("Discovery", [("Daft Punk", "One More Time"), ("Daft Punk", "Aerodynamic"), ("Daft Punk", "Digital Love")]))
        self.assertEqual(asked.call_args.args[0], "https://music.apple.com/kz/album/697194953")

    def test_link_to_one_song_of_an_album_takes_that_song(self):
        with patch("apple.steady", return_value=sample("apple_album.html")):
            _, entries = apple.tracks("https://music.apple.com/us/album/aerodynamic/697194953?i=697195570")
        self.assertEqual(pairs(entries), [("Daft Punk", "Aerodynamic")])

    def test_first_of_several_artists_is_the_main_one(self):
        row = {"title": "Song", "artistName": "A, B & C", "subtitleLinks": [{"title": "A"}, {"title": "B"}], "contentDescriptor": {"url": "javascript:alert(1)"}}
        self.assertEqual(apple.entry(row), Entry("Song", "A", ""))

    def test_other_links_are_turned_away_without_asking(self):
        with patch("apple.steady") as asked:
            for link in ("", "https://music.apple.com/us/artist/daft-punk/5468295", "https://music.apple.com/us/song/one-more-time/697195462",
                         "https://example.com/us/album/discovery/697194953", "https://music.apple.com/album/discovery/697194953"):
                with self.assertRaisesRegex(ImportFailed, "Вставьте ссылку"):
                    apple.tracks(link)
        asked.assert_not_called()

    def test_failures(self):
        link = "https://music.apple.com/us/album/discovery/697194953"
        for error, said in ((http_error(404), "не нашёл"), (http_error(503), "HTTP 503"), (URLError("down"), "Не удалось связаться")):
            with patch("apple.steady", side_effect=error):
                with self.assertRaisesRegex(ImportFailed, said):
                    apple.tracks(link)
        for body in ("<html></html>", '<script type="application/json" id="serialized-server-data">{"data": []}</script>',
                     '<script type="application/json" id="serialized-server-data">not json</script>'):
            with patch("apple.steady", return_value=body):
                with self.assertRaisesRegex(ImportFailed, "неожиданном виде"):
                    apple.tracks(link)
        empty = '<script type="application/json" id="serialized-server-data">{"data": [{"data": {"sections": []}}]}</script>'
        with patch("apple.steady", return_value=empty):
            with self.assertRaisesRegex(ImportFailed, "ни одного трека"):
                apple.tracks(link)


class YouTube(unittest.TestCase):
    def rows(self):
        return [json.loads(line) for line in sample("youtube_rows.jsonl").splitlines()]

    def test_rows_as_yt_dlp_prints_them(self):
        self.assertEqual(pairs(youtube.entries(self.rows())), [
            ("Lady Gaga", "Die With A Smile"), ("ROSÉ", "APT."), ("manifest", "TRALALA"), ("DJ Snake", "Let Me Love You ft. Justin Bieber"),
            ("Shawn Mendes", "Treat You Better"), ("Passenger", "Let Her Go"), ("BTS (방탄소년단)", "Dynamite"), ("Coldplay", "Sparks"),
            ("Rihanna", "Kiss It Better")])
        self.assertEqual(youtube.entries(self.rows())[0].url, "https://www.youtube.com/watch?v=kPa7bsKwL-c")

    def test_song_on_a_topic_channel_keeps_its_whole_title(self):
        self.assertEqual(youtube.song("Under Pressure - Remastered 2011", "Queen - Topic"), ("Queen", "Under Pressure - Remastered 2011"))

    def test_bare_title_belongs_to_the_channel(self):
        self.assertEqual(youtube.song("Ich wache auf", "Madeline Juno"), ("Madeline Juno", "Ich wache auf"))

    def test_uploader_is_not_the_artist_of_a_titled_video(self):
        self.assertEqual(youtube.song("Coldplay - Sparks", "Somber Sounds"), ("Coldplay", "Sparks"))
        self.assertEqual(youtube.song("Sia - Chandelier (Official Video)", "Siames"), ("Sia", "Chandelier"))
        self.assertEqual(youtube.song("Siames - The Wolf", "Sia"), ("Siames", "The Wolf"))

    def test_channel_named_first_among_the_artists_is_the_main_one(self):
        self.assertEqual(youtube.song("Eurythmics, Annie Lennox, Dave Stewart - Sweet Dreams (Are Made Of This) (Official Video)", "Eurythmics"),
                         ("Eurythmics", "Sweet Dreams (Are Made Of This)"))

    def test_clean_keeps_what_is_part_of_the_song(self):
        self.assertEqual(youtube.clean("We Don't Talk Anymore (feat. Selena Gomez) [Official Video]"), "We Don't Talk Anymore (feat. Selena Gomez)")
        self.assertEqual(youtube.clean("Кукла колдуна (Премьера клипа, 2024) | Remastered"), "Кукла колдуна | Remastered")
        self.assertEqual(youtube.clean("Two Feet (DJ Dark Remix) [4K]"), "Two Feet (DJ Dark Remix)")
        self.assertEqual(youtube.clean("Ring, Ring | Official Video"), "Ring, Ring")

    def test_removed_and_foreign_rows_are_skipped(self):
        rows = [{"url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "title": "[Private video]", "channel": None, "ie_key": "Youtube"},
                {"url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "title": "[Deleted video]", "ie_key": "Youtube"},
                {"url": "https://www.youtube.com/playlist?list=PLzzzzzzzzzz", "title": "Nested - List", "channel": "X", "ie_key": "YoutubeTab"},
                {"url": "https://music.youtube.com/watch?v=ccccccccccc", "title": "Waldbrand", "uploader": "Madeline Juno", "ie_key": "Youtube"}]
        self.assertEqual(youtube.entries(rows), [Entry("Waldbrand", "Madeline Juno", "https://www.youtube.com/watch?v=ccccccccccc")])

    def test_playlist_is_found_in_any_youtube_link(self):
        number = "PLMC9KNkIncKtPzgY-5rmhvj7fax8fdxoj"
        for link in (f"https://www.youtube.com/playlist?list={number}", f"music.youtube.com/playlist?list={number}&si=abc",
                     f" https://m.youtube.com/watch?v=kPa7bsKwL-c&list={number}&index=2 ", f"https://youtu.be/kPa7bsKwL-c?list={number}"):
            self.assertEqual(youtube.playlist_id(link), number, link)
        for link in ("", "https://www.youtube.com/watch?v=kPa7bsKwL-c", "https://www.youtube.com/playlist?list=LL",
                     f"https://example.com/playlist?list={number}", "https://www.youtube.com/playlist?list=--exec%20rm"):
            self.assertEqual(youtube.playlist_id(link), "", link)

    def test_tracks_names_the_playlist_and_asks_for_the_whole_list(self):
        rows = self.rows()
        with patch("youtube.listing", return_value=rows) as asked:
            name, entries = youtube.tracks("https://www.youtube.com/watch?v=kPa7bsKwL-c&list=PLMC9KNkIncKtPzgY-5rmhvj7fax8fdxoj")
        self.assertEqual((name, len(entries)), ("Pop Music Playlist - Timeless Pop Songs (Updated Weekly 2026)", 9))
        self.assertEqual(asked.call_args.args[0], "https://www.youtube.com/playlist?list=PLMC9KNkIncKtPzgY-5rmhvj7fax8fdxoj")
        with patch("youtube.listing", return_value=[dict(rows[0], playlist_title="Album - Waldbrand")]):
            self.assertEqual(youtube.tracks("https://music.youtube.com/playlist?list=OLAK5uy_lGP_zv0vJDUlecQDzugUJmjcF7pvyVNyY")[0], "Waldbrand")

    def test_what_yt_dlp_complains_about_is_worded_for_the_user(self):
        link = "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        cases = (("ERROR: [youtube:tab] PLxxx: YouTube said: The playlist does not exist.", "не нашёл"),
                 ("ERROR: [youtube:tab] RDkPa: This playlist type is unviewable.", "Миксы"),
                 ("ERROR: [youtube] Sign in to confirm you’re not a bot. Use --cookies-from-browser", "просит войти"),
                 ("ERROR: [youtube:tab] PLxxx: This playlist is private, use --cookies", "просит войти"),
                 ("ERROR: unable to download webpage: timed out", "Проверьте интернет"))
        for printed, said in cases:
            with patch("youtube.listing", side_effect=Refused(printed)):
                with self.assertRaisesRegex(ImportFailed, said):
                    youtube.tracks(link)
        with patch("youtube.listing", return_value=[]):
            with self.assertRaisesRegex(ImportFailed, "не найдено открытых видео"):
                youtube.tracks(link)
        with patch("youtube.listing") as asked:
            with self.assertRaisesRegex(ImportFailed, "Вставьте ссылку"):
                youtube.tracks("https://www.youtube.com/watch?v=kPa7bsKwL-c")
        asked.assert_not_called()


class Tags(unittest.TestCase):
    """named() reads what `ffprobe -show_entries format_tags:stream_tags -of json` printed for files made by ffmpeg."""

    def test_mp3_keeps_tags_on_the_file(self):
        probe = {"streams": [{}], "format": {"tags": {"title": "Розовое вино", "artist": "Элджей", "encoder": "Lavf63.1.102"}}}
        self.assertEqual(local.named(probe), {"title": "Розовое вино", "artist": "Элджей"})

    def test_opus_keeps_tags_on_the_stream(self):
        probe = {"streams": [{"tags": {"encoder": "Lavc63.1.102 libopus", "title": "Archangel", "artist": "Burial"}}], "format": {}}
        self.assertEqual(local.named(probe), {"title": "Archangel", "artist": "Burial"})

    def test_flac_names_tags_in_capitals(self):
        probe = {"streams": [{}], "format": {"tags": {"TITLE": "Teardrop", "ARTIST": "Massive Attack", "encoder": "Lavf63.1.102"}}}
        self.assertEqual(local.named(probe), {"title": "Teardrop", "artist": "Massive Attack"})

    def test_album_artist_stands_in_for_a_missing_artist(self):
        self.assertEqual(local.named({"format": {"tags": {"title": "Roygbiv", "album_artist": "Boards of Canada"}}}),
                         {"title": "Roygbiv", "artist": "Boards of Canada"})

    def test_nothing_usable(self):
        for probe in ({}, [], None, {"format": None, "streams": [None, {"tags": []}]}, {"format": {"tags": {"title": 5}}}):
            self.assertEqual(local.named(probe), {"title": "", "artist": ""})

    def test_name_of_a_file(self):
        self.assertEqual(local.from_name("/music/03. Portishead - Roads.mp3"), ("Portishead", "Roads"))
        self.assertEqual(local.from_name("07 - Björk - Jóga.flac"), ("Björk", "Jóga"))
        self.assertEqual(local.from_name("track07.mp3"), ("", "track07"))
        self.assertEqual(local.from_name("1979.mp3"), ("", "1979"))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg and ffprobe")
    def test_real_files(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, codec in (("one.mp3", []), ("two.opus", ["-c:a", "libopus"])):
                subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.2",
                                "-metadata", "title=Тихо", "-metadata", "artist=Никто", *codec, f"{folder}/{name}"], check=True)
            entries, skipped = local.folder(folder)
        self.assertEqual((pairs(entries), skipped), ([("Никто", "Тихо"), ("Никто", "Тихо")], 0))


class Folder(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        for name in ("b/02 two.flac", "b/.hidden/secret.mp3", "a/03. Portishead - Roads.MP3", "a/track07.mp3", "a/cover.jpg", ".trash.mp3", "one.mp3"):
            (self.folder / name).parent.mkdir(parents=True, exist_ok=True)
            (self.folder / name).touch()
        self.known = {"one.mp3": {"title": "Розовое вино", "artist": "Элджей"}, "02 two.flac": {"title": "Teardrop", "artist": ""}}
        self.enterContext(patch("local.shutil.which", return_value="/usr/bin/ffprobe"))
        self.enterContext(patch("local.tags", side_effect=lambda program, path: self.known.get(path.name, {"title": "", "artist": ""})))

    def test_tags_then_names_and_files_without_an_artist_are_counted(self):
        said = []
        entries, skipped = local.folder(self.folder, report=said.append)
        self.assertEqual(entries, [Entry("Розовое вино", "Элджей", (self.folder / "one.mp3").as_uri()),
                                   Entry("Roads", "Portishead", (self.folder / "a/03. Portishead - Roads.MP3").as_uri())])
        self.assertEqual(skipped, 2)
        self.assertEqual(said[-1], "Файлы · читаю теги: 4 из 4")

    def test_link_is_a_file_address_that_leads_back_to_the_file(self):
        entries, _ = local.folder(self.folder)
        self.assertTrue(entries[1].url.startswith("file:///"))
        self.assertEqual(Path(unquote(urlsplit(entries[1].url).path)), self.folder / "a/03. Portishead - Roads.MP3")

    def test_failures(self):
        with self.assertRaisesRegex(ImportFailed, "Выберите папку"):
            local.folder(self.folder / "one.mp3")
        (self.folder / "empty").mkdir()
        with self.assertRaisesRegex(ImportFailed, "нет аудиофайлов"):
            local.folder(self.folder / "empty")
        with self.assertRaisesRegex(ImportFailed, "отменён"):
            local.folder(self.folder, lambda: True)
        with patch("local.shutil.which", return_value=None):
            with self.assertRaisesRegex(ImportFailed, "ffprobe"):
                local.folder(self.folder)


class M3U(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        for name in ("Album/01 one.mp3", "Album/two.flac", "sub/03. Portishead - Roads.mp3", "sub/track07.mp3", "с пробелом.ogg"):
            (self.folder / name).parent.mkdir(parents=True, exist_ok=True)
            (self.folder / name).touch()
        self.known = {"two.flac": {"title": "Teardrop", "artist": "Massive Attack"}}
        self.asked = []
        def read(paths, cancelled, report):
            self.asked += [path.name for path in paths]
            return [self.known.get(path.name, {"title": "", "artist": ""}) for path in paths]
        self.enterContext(patch("local.read", side_effect=read))

    def write(self, text, name="list.m3u8", encoding="utf-8"):
        (self.folder / name).write_bytes(text.encode(encoding))
        return self.folder / name

    def test_extinf_names_the_track_and_the_path_gives_the_link(self):
        entries, skipped = local.playlist(self.write(
            "#EXTM3U\n#EXTINF:213,Элджей - Розовое вино\nAlbum/01 one.mp3\n\n"
            '#EXTINF:-1 tvg-id="x",Radiohead — Reckoner\nhttps://example.com/stream/reckoner.mp3\n'
            "#EXTINF:100,Missing Artist - Missing Song\ngone/away.mp3\n"
            "#EXTINF:5,Plain Http - Stream\nhttp://example.com/a.mp3\n"))
        self.assertEqual(entries, [Entry("Розовое вино", "Элджей", (self.folder / "Album/01 one.mp3").as_uri()),
                                   Entry("Reckoner", "Radiohead", "https://example.com/stream/reckoner.mp3"),
                                   Entry("Missing Song", "Missing Artist", ""),
                                   Entry("Stream", "Plain Http", "")])
        self.assertEqual((skipped, self.asked), (0, []))

    def test_file_without_a_usable_extinf_is_named_by_tags_then_by_its_name(self):
        entries, skipped = local.playlist(self.write(
            "#EXTINF:200,Только название\nAlbum/two.flac\nsub/03. Portishead - Roads.mp3\nsub\\track07.mp3\n"
            f"{(self.folder / 'с пробелом.ogg').as_uri()}\n"))
        self.assertEqual(entries, [Entry("Teardrop", "Massive Attack", (self.folder / "Album/two.flac").as_uri()),
                                   Entry("Roads", "Portishead", (self.folder / "sub/03. Portishead - Roads.mp3").as_uri())])
        self.assertEqual(skipped, 2)
        self.assertEqual(self.asked, ["two.flac", "03. Portishead - Roads.mp3", "track07.mp3", "с пробелом.ogg"])

    def test_paths_from_another_computer_still_name_tracks(self):
        entries, skipped = local.playlist(self.write(
            "C:\\Music\\Björk - Jóga.mp3\n/home/other/07 - Burial - Archangel.flac\nhttp://example.com/Some%20Band%20-%20Some%20Song.mp3\n/home/other/untitled.mp3\n"))
        self.assertEqual((pairs(entries), [entry.url for entry in entries], skipped),
                         ([("Björk", "Jóga"), ("Burial", "Archangel"), ("Some Band", "Some Song")], ["", "", ""], 1))

    def test_old_m3u_in_the_windows_encoding(self):
        entries, _ = local.playlist(self.write("#EXTM3U\r\n#EXTINF:10,Кино - Группа крови\r\nAlbum\\01 one.mp3\r\n", "old.m3u", "cp1251"))
        self.assertEqual(entries, [Entry("Группа крови", "Кино", (self.folder / "Album/01 one.mp3").as_uri())])

    def test_byte_order_mark_and_absolute_paths(self):
        entries, _ = local.playlist(self.write(f"{chr(0xFEFF)}#EXTM3U\n#EXTINF:1,A - B\n{self.folder / 'Album/two.flac'}\n"))
        self.assertEqual(entries, [Entry("B", "A", (self.folder / "Album/two.flac").as_uri())])

    def test_unreadable_playlist(self):
        with self.assertRaisesRegex(ImportFailed, "nothing.m3u\nНе удалось прочитать"):
            local.playlist(self.folder / "nothing.m3u")


class Jobs(unittest.TestCase):
    """Each import in jobs.py stores what its service gave under the service's name."""

    def setUp(self):
        try:
            import jobs
        except ImportError:
            self.skipTest("jobs.py needs PySide6")
        self.jobs = jobs
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.library = Library(self.folder / "library.sqlite3")
        self.said = []

    def run_job(self, operation, cancelled=lambda: False):
        return operation(cancelled, self.said.append)

    def stored(self):
        return sorted((track.source, track.artist, track.title, track.url) for track in self.library.tracks())

    def test_links(self):
        found = ("Сборник", [Entry("Song", "Artist", "https://example.com/1"), Entry("", "Nobody"), Entry("Other", "Artist")])
        cases = ((self.jobs.deezer_link, "deezer.tracks", "Deezer"), (self.jobs.yandex_link, "yandex.tracks", "Яндекс Музыка"),
                 (self.jobs.apple_link, "apple.tracks", "Apple Music"), (self.jobs.youtube_playlist, "youtube.tracks", "YouTube"))
        for make, fetch, source in cases:
            with patch(fetch, return_value=found) as asked:
                result = self.run_job(make(self.library, "https://example.com/list"))
            self.assertEqual(asked.call_args.args[0], "https://example.com/list")
            self.assertEqual(result, f"{source} · «Сборник» · треков добавлено: 2")
            self.assertIn(f"{source} · читаю список треков…", self.said)
        self.assertEqual({source for source, *_ in self.stored()}, {"Deezer", "Яндекс Музыка", "Apple Music", "YouTube"})
        self.assertEqual(len(self.stored()), 8)

    def test_cancelled_import_stores_nothing(self):
        with patch("yandex.tracks", return_value=("Сборник", [Entry("Song", "Artist")])):
            with self.assertRaisesRegex(ImportFailed, "отменён"):
                self.run_job(self.jobs.yandex_link(self.library, "x"), lambda: True)
        self.assertEqual(self.stored(), [])

    def test_failure_of_a_service_reaches_the_caller(self):
        with patch("apple.steady", side_effect=http_error(404)):
            with self.assertRaisesRegex(ImportFailed, "не нашёл"):
                self.run_job(self.jobs.apple_link(self.library, "https://music.apple.com/us/album/x/1"))

    def test_m3u_files(self):
        (self.folder / "a.mp3").touch()
        (self.folder / "one.m3u8").write_text("#EXTINF:1,Кино - Группа крови\na.mp3\n#EXTINF:1,Без артиста\ngone.mp3\n", encoding="utf-8")
        (self.folder / "two.m3u").write_text("#EXTINF:1,Radiohead - Reckoner\nhttps://example.com/r.mp3\n", encoding="utf-8")
        result = self.run_job(self.jobs.m3u_files(self.library, [str(self.folder / "one.m3u8"), str(self.folder / "two.m3u")]))
        self.assertEqual(result, "Файлы · треков добавлено: 2 · пропущено без артиста: 1")
        self.assertEqual(self.stored(), [("Файлы", "Radiohead", "Reckoner", "https://example.com/r.mp3"),
                                         ("Файлы", "Кино", "Группа крови", (self.folder / "a.mp3").resolve().as_uri())])

    def test_m3u_without_tracks(self):
        (self.folder / "empty.m3u").write_text("#EXTM3U\n", encoding="utf-8")
        with self.assertRaisesRegex(ImportFailed, "не найдено треков"):
            self.run_job(self.jobs.m3u_files(self.library, [self.folder / "empty.m3u"]))

    def test_music_folder(self):
        (self.folder / "music").mkdir()
        (self.folder / "music/Portishead - Roads.mp3").touch()
        (self.folder / "music/untitled.mp3").touch()
        with patch("local.shutil.which", return_value="/usr/bin/ffprobe"), patch("local.tags", return_value={"title": "", "artist": ""}):
            result = self.run_job(self.jobs.music_folder(self.library, str(self.folder / "music")))
            self.assertEqual(result, "Файлы · треков добавлено: 1 · пропущено без артиста: 1")
            (self.folder / "music/Portishead - Roads.mp3").unlink()
            with self.assertRaisesRegex(ImportFailed, "нет тегов"):
                self.run_job(self.jobs.music_folder(self.library, self.folder / "music"))
        self.assertEqual(self.stored(), [("Файлы", "Portishead", "Roads", (self.folder / "music/Portishead - Roads.mp3").resolve().as_uri())])


if __name__ == "__main__":
    unittest.main()
