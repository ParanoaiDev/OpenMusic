"""Run from the project folder: python3 -m unittest discover tests. Nothing here uses the network."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import lyrics
from lyrics import Cache, Line, LyricsFailed, Word, best, parse_lrc


def http_error(code, said):
    error = HTTPError("u", code, said, None, None)
    # Python warns about an HTTPError that is dropped unclosed; its code outlives the closing.
    error.close()
    return error


def record(number, artist, title, seconds, synced=True, plain=True, instrumental=False):
    return {"id": number, "artistName": artist, "trackName": title, "duration": seconds, "instrumental": instrumental,
            "syncedLyrics": "[00:01.00] first\n[00:03.00] second" if synced else None,
            "plainLyrics": "first\nsecond" if plain else None}


class ParseLrc(unittest.TestCase):
    def test_lines_end_where_the_next_begins(self):
        lines = parse_lrc("[ar:Somebody]\n[00:00.15] Раз два\n[00:02.63]Three\nnot timed\n[01:06.5] end", 70000)
        self.assertEqual([(line.start_ms, line.end_ms, line.text) for line in lines],
                         [(150, 2630, "Раз два"), (2630, 66500, "Three"), (66500, 70000, "end")])

    def test_words_share_the_line_evenly(self):
        (line, _) = parse_lrc("[00:10.00] one two  three four\n[00:12.00] next")
        self.assertEqual(line.text, "one two three four")
        self.assertEqual(line.words, [Word(10000, 10500, "one"), Word(10500, 11000, "two"),
                                      Word(11000, 11500, "three"), Word(11500, 12000, "four")])

    def test_a_break_after_a_line_does_not_stretch_its_words(self):
        (line, _) = parse_lrc("[00:10.00] one two\n[00:40.00] after the solo")
        self.assertEqual((line.end_ms, line.words[-1].end_ms), (40000, 12000))

    def test_a_lone_mark_rides_with_the_word_before_it(self):
        (line,) = parse_lrc("[00:01.00] Я — как Гоша", 4000)
        self.assertEqual(line.text, "Я — как Гоша")
        self.assertEqual(line.words, [Word(1000, 2000, "Я —"), Word(2000, 3000, "как"), Word(3000, 4000, "Гоша")])

    def test_empty_stamp_is_a_pause(self):
        lines = parse_lrc("[00:01.00] sung\n[00:04.00]\n[00:09.00] again\n[00:11.00] ")
        self.assertEqual([(line.start_ms, line.end_ms, line.text) for line in lines], [(1000, 4000, "sung"), (9000, 11000, "again")])

    def test_last_line_without_a_known_end(self):
        self.assertEqual(parse_lrc("[00:01.00] only")[0].end_ms, 1000 + lyrics.LAST_LINE_MS)

    def test_offset_moves_everything(self):
        sooner = parse_lrc("[offset:+500]\n[00:01.00] a\n[00:02.00] b")
        later = parse_lrc("[00:01.00] a\n[00:02.00] b\n[offset: -250]")
        clamped = parse_lrc("[offset:5000]\n[00:01.00] a\n[00:09.00] b")
        self.assertEqual([line.start_ms for line in sooner], [500, 1500])
        self.assertEqual([line.start_ms for line in later], [1250, 2250])
        self.assertEqual([line.start_ms for line in clamped], [0, 4000])

    def test_repeated_stamps_repeat_the_line(self):
        lines = parse_lrc("[00:10.00][00:30.00] chorus\n[00:20.00] verse")
        self.assertEqual([(line.start_ms, line.end_ms, line.text) for line in lines],
                         [(10000, 20000, "chorus"), (20000, 30000, "verse"), (30000, 35000, "chorus")])

    def test_stamp_spellings(self):
        lines = parse_lrc("[0:05] a\n[00:06:50] b\n[00:07.123] c\n[100:00.00] d")
        self.assertEqual([line.start_ms for line in lines], [5000, 6500, 7123, 6000000])

    def test_enhanced_words_keep_their_own_times(self):
        (line, after) = parse_lrc("[00:10.00] <00:10.00> Hold <00:13.00> me now <00:14.00>\n[00:20.00] <00:20.50>late <00:21.00>start")
        self.assertEqual((line.start_ms, line.end_ms, line.text), (10000, 20000, "Hold me now"))
        self.assertEqual(line.words, [Word(10000, 13000, "Hold"), Word(13000, 13500, "me"), Word(13500, 14000, "now")])
        # No closing stamp: the last word is a guess and gets the usual limit.
        self.assertEqual(after.words, [Word(20500, 21000, "late"), Word(21000, 22000, "start")])

    def test_enhanced_words_follow_offset_and_repeats(self):
        lines = parse_lrc("[offset:1000]\n[00:10.00][00:50.00] <00:10.00>la <00:11.00>la <00:12.00>")
        self.assertEqual([line.words for line in lines], [[Word(9000, 10000, "la"), Word(10000, 11000, "la")],
                                                         [Word(49000, 50000, "la"), Word(50000, 51000, "la")]])

    def test_text_without_stamps_has_no_timed_lines(self):
        self.assertEqual(parse_lrc("just\nwords"), [])
        self.assertEqual(parse_lrc(""), [])


class BestMatch(unittest.TestCase):
    def test_right_length_wins_over_search_order(self):
        found = [record(1, "Eldzhey", "Розовое вино", 247), record(2, "Eldzhey", "Розовое вино", 202), record(3, "Eldzhey", "Розовое вино", 92)]
        self.assertEqual(best(found, "Eldzhey", "Розовое вино", 203500)["id"], 2)
        self.assertEqual(best(found, "Eldzhey", "Розовое вино")["id"], 1)

    def test_timing_wins_among_equal_lengths(self):
        found = [record(1, "A", "Song", 200, synced=False), record(2, "A", "Song", 201)]
        self.assertEqual(best(found, "A", "Song", 200000)["id"], 2)

    def test_fitting_words_win_over_timing_of_another_length(self):
        found = [record(1, "A", "Song", 100), record(2, "A", "Song", 200, synced=False)]
        self.assertEqual(best(found, "A", "Song", 200000)["id"], 2)

    def test_closest_length_when_none_fits(self):
        found = [record(1, "A", "Song", 100), record(2, "A", "Song", 190)]
        self.assertEqual(best(found, "A", "Song", 200000)["id"], 2)

    def test_other_tracks_and_artists_are_not_matches(self):
        found = [record(1, "Somebody Else", "Song", 200), record(2, "A", "Another Song", 200), "junk", {"trackName": None}]
        self.assertIsNone(best(found, "A", "Song", 200000))
        self.assertIsNone(best([], "A", "Song"))

    def test_title_notes_and_joint_artists(self):
        found = [record(1, "FEDUK & Eldzhey", "Розовое вино (Remix)", 200), record(2, "Feduk, eldzhey", "РОЗОВОЕ ВИНО", 200)]
        self.assertEqual(best(found, "Eldzhey", "Розовое вино", 200000)["id"], 2)
        self.assertEqual(best(found[:1], "Eldzhey", "Розовое вино - Radio Edit", 200000)["id"], 1)

    def test_records_without_text_are_skipped(self):
        found = [record(1, "A", "Song", 200, synced=False, plain=False), record(2, "A", "Song", 200, synced=False)]
        self.assertEqual(best(found, "A", "Song", 200000)["id"], 2)
        self.assertEqual(best([record(3, "A", "Song", 200, False, False, instrumental=True)], "A", "Song")["id"], 3)


class Reading(unittest.TestCase):
    def test_synced(self):
        text = lyrics.reading(record(1, "A", "Song", 10), 10000)
        self.assertTrue(text.synced)
        self.assertEqual(text.lines[-1], Line(3000, 10000, "second", [Word(3000, 4000, "second")]))

    def test_another_length_keeps_only_the_words(self):
        text = lyrics.reading(record(1, "A", "Song", 100), 200000)
        self.assertEqual((text.synced, text.lines), (False, [Line(None, None, "first"), Line(None, None, "second")]))
        stripped = lyrics.reading(record(1, "A", "Song", 100, plain=False), 200000)
        self.assertEqual([line.text for line in stripped.lines], ["first", "second"])

    def test_a_slightly_different_length_keeps_the_timing_as_approximate(self):
        longer = lyrics.reading(record(1, "A", "Song", 205), 221000)
        self.assertEqual((longer.synced, longer.approximate, longer.lines[0].start_ms), (True, True, 1000))
        self.assertFalse(lyrics.reading(record(1, "A", "Song", 205), 206000).approximate)
        self.assertFalse(lyrics.reading(record(1, "A", "Song", 205), 230000).synced)

    def test_plain_and_instrumental_and_empty(self):
        plain = lyrics.reading({"plainLyrics": "one\n\n  two  \n", "syncedLyrics": None})
        self.assertEqual((plain.synced, plain.instrumental, [line.text for line in plain.lines]), (False, False, ["one", "two"]))
        self.assertEqual(lyrics.reading({"instrumental": True, "plainLyrics": None}), lyrics.Lyrics(False, [], True))
        self.assertIsNone(lyrics.reading({"plainLyrics": "", "syncedLyrics": None}))


class Names(unittest.TestCase):
    def test_alphabets(self):
        self.assertEqual((lyrics.latin("ЛСП"), lyrics.latin("Монеточка"), lyrics.latin("Король и Шут")), ("lsp", "monetochka", "korolishut"))
        self.assertEqual((lyrics.to_cyrillic("LSP"), lyrics.to_cyrillic("Monetochka"), lyrics.to_cyrillic("Morgenshtern")),
                         ("лсп", "монеточка", "моргенштерн"))
        self.assertTrue(lyrics.cyrillic("Вояж") and lyrics.cyrillic("Әнім") and not lyrics.cyrillic("Voyage 90"))

    def test_same_artist_in_any_alphabet(self):
        self.assertTrue(lyrics.same_artist("Leningrad", "Ленинград"))
        self.assertTrue(lyrics.same_artist("Scriptonite", "Скриптонит & 104"))
        self.assertTrue(lyrics.same_artist("MORGENSHTERN", "Morgenshtern feat. LSP"))
        self.assertFalse(lyrics.same_artist("Leningrad", "Ленин"))
        self.assertFalse(lyrics.same_artist("Kino", "Кони"))
        self.assertFalse(lyrics.same_artist("A", "B"))

    def test_bare_title(self):
        self.assertEqual(lyrics.bare("Song (feat. B) [Remastered 2011]"), "Song")
        self.assertEqual(lyrics.bare("Песня prod. by Somebody"), "Песня")
        self.assertEqual(lyrics.bare("Песня ft. Кто-то"), "Песня")
        self.assertEqual(lyrics.bare("Song - Live at Wembley"), "Song")
        self.assertEqual(lyrics.bare("(Intro)"), "(Intro)")


class Paced(unittest.TestCase):
    def test_lines_are_spread_by_their_length(self):
        lines = [Line(None, None, "short"), Line(None, None, "a line that is a good deal longer"), Line(None, None, "end")]
        timed = lyrics.paced(lines, 100000)
        self.assertEqual([line.text for line in timed], ["short", "a line that is a good deal longer", "end"])
        self.assertEqual((timed[0].start_ms, timed[-1].end_ms), (7000, 94000))
        self.assertEqual([line.end_ms for line in timed[:-1]], [line.start_ms for line in timed[1:]])
        self.assertGreater(timed[1].end_ms - timed[1].start_ms, 2 * (timed[0].end_ms - timed[0].start_ms))

    def test_no_length_no_timing(self):
        lines = [Line(None, None, "one")]
        self.assertEqual(lyrics.paced(lines, None), lines)
        self.assertEqual(lyrics.paced([], 1000), [])


class Lookup(unittest.TestCase):
    """lyrics() against a pretend LRCLIB: self.answers maps a request to its reply."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.cache = Cache(Path(self.folder.name) / "data" / "lyrics.sqlite3")
        self.asked = []
        self.answers = {}
        patcher = patch("lyrics.fetch", side_effect=self.reply)
        patcher.start()
        self.addCleanup(patcher.stop)

    def reply(self, method, **query):
        self.asked.append((method, query.get("artist_name"), query.get("track_name"), query.get("duration")))
        answer = self.answers.get(self.asked[-1], [] if method == "search" else None)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def test_exact_recording_is_asked_first(self):
        self.answers[("get", "A", "Song", 200)] = record(1, "A", "Song", 200)
        self.assertTrue(lyrics.lyrics("A", "Song", 200400).synced)
        self.assertEqual(self.asked, [("get", "A", "Song", 200)])

    def test_search_when_the_length_is_unknown(self):
        self.answers[("search", "A", "Song", None)] = [record(1, "A", "Song", 200)]
        self.assertTrue(lyrics.lyrics(" A ", "Song").synced)
        self.assertEqual(self.asked, [("search", "A", "Song", None)])

    def test_title_notes_are_dropped_for_a_second_search(self):
        self.answers[("search", "A", "Song", None)] = [record(1, "A", "Song", 200)]
        self.assertTrue(lyrics.lyrics("A", "Song (feat. B) [Remastered 2011]").synced)
        self.assertEqual([request[2] for request in self.asked], ["Song (feat. B) [Remastered 2011]", "Song"])

    def test_soundcloud_title_holds_the_artist(self):
        self.answers[("search", "Real Artist", "Song", None)] = [record(1, "Real Artist", "Song", 200)]
        self.assertTrue(lyrics.lyrics("some-uploader", "Real Artist - Song (prod. X)").synced)

    def test_found_text_is_remembered(self):
        self.answers[("search", "A", "Song", None)] = [record(1, "A", "Song", 200)]
        first = lyrics.lyrics("A", "Song", cache=self.cache)
        again = lyrics.lyrics("a", " SONG ", cache=Cache(self.cache.path))
        self.assertEqual((first, len(self.asked)), (again, 1))

    def test_nothing_found_is_remembered_for_a_while_and_can_be_forgotten(self):
        # Each look is three requests: the artist as given, as written in Russian, then the title alone.
        self.assertIsNone(lyrics.lyrics("A", "Song", cache=self.cache))
        self.assertIsNone(lyrics.lyrics("A", "Song", cache=self.cache))
        self.assertEqual(self.asked, [("search", "A", "Song", None), ("search", "а", "Song", None), ("search", None, "Song", None)])
        self.cache.forget("A", "song")
        self.assertIsNone(lyrics.lyrics("A", "Song", cache=self.cache))
        self.assertEqual(len(self.asked), 6)
        with patch("lyrics.time.time", return_value=lyrics.time.time() + lyrics.MISS_SECONDS + 1):
            lyrics.lyrics("A", "Song", cache=self.cache)
        self.assertEqual(len(self.asked), 9)

    def test_nothing_found_by_the_older_way_of_looking_is_asked_again(self):
        with patch("lyrics.time.time", return_value=lyrics.MISSES_SINCE - 60):
            self.assertIsNone(lyrics.lyrics("A", "Song", cache=self.cache))
        self.answers[("search", "A", "Song", None)] = [record(1, "A", "Song", 200)]
        self.assertTrue(lyrics.lyrics("A", "Song", cache=self.cache).synced)

    def test_artist_spelled_in_latin_letters_is_found_as_written(self):
        self.answers[("search", "лсп", "Монетка", None)] = [record(1, "ЛСП", "Монетка", 200)]
        self.assertTrue(lyrics.lyrics("LSP", "Монетка").synced)
        self.assertEqual(self.asked, [("search", "LSP", "Монетка", None), ("search", "лсп", "Монетка", None)])
        self.answers[("search", "монеточка", "90", None)] = [record(2, "Монеточка", "90", 202)]
        self.assertTrue(lyrics.lyrics("Monetochka", "90").synced)

    def test_title_alone_finds_the_same_artist_in_another_alphabet(self):
        self.answers[("search", None, "Каждый раз", None)] = [record(1, "Кто-то другой", "Каждый раз", 200),
                                                              record(2, "Монеточка", "Каждый раз", 200)]
        found = lyrics.lookup("Monetochka", "Каждый раз (Live)")
        self.assertEqual(found["id"], 2)
        self.answers[("search", None, "Song", None)] = [record(3, "Somebody Else", "Song", 200)]
        self.assertIsNone(lyrics.lookup("A", "Song"))

    def test_another_recording_is_looked_up_once_when_the_length_becomes_known(self):
        self.answers[("search", "A", "Song", None)] = [record(1, "A", "Song", 247), record(2, "A", "Song", 202)]
        self.assertTrue(lyrics.lyrics("A", "Song", cache=self.cache).synced)
        self.answers[("get", "A", "Song", 202)] = record(2, "A", "Song", 202)
        self.assertTrue(lyrics.lyrics("A", "Song", 202000, cache=self.cache).synced)
        self.assertTrue(lyrics.lyrics("A", "Song", 202900, cache=self.cache).synced)
        self.assertEqual(len(self.asked), 2)
        # A length nothing fits is asked about once and then served as plain words.
        self.assertFalse(lyrics.lyrics("A", "Song", 100000, cache=self.cache).synced)
        asked = len(self.asked)
        self.assertFalse(lyrics.lyrics("A", "Song", 100000, cache=self.cache).synced)
        self.assertEqual(len(self.asked), asked)

    def test_failure_is_raised_and_not_remembered(self):
        self.answers[("search", "A", "Song", None)] = LyricsFailed("нет связи")
        with self.assertRaises(LyricsFailed):
            lyrics.lyrics("A", "Song", cache=self.cache)
        self.answers[("search", "A", "Song", None)] = [record(1, "A", "Song", 200)]
        self.assertTrue(lyrics.lyrics("A", "Song", cache=self.cache).synced)

    def test_unusable_cache_file_only_costs_the_memory(self):
        self.answers[("search", "A", "Song", None)] = [record(1, "A", "Song", 200)]
        broken = Cache(Path(self.folder.name) / "file")
        broken.path.write_text("not a database at all, just some text to break sqlite" * 20)
        self.assertTrue(lyrics.lyrics("A", "Song", cache=broken).synced)
        broken.forget("A", "Song")

    def test_empty_names_ask_nothing(self):
        self.assertIsNone(lyrics.lyrics("", "Song"))
        self.assertIsNone(lyrics.lyrics("A", None))
        self.assertEqual(self.asked, [])


class Fetch(unittest.TestCase):
    def test_network_trouble_becomes_lyrics_failed(self):
        for trouble in (URLError("no route"), TimeoutError(), ValueError("not json"), http_error(500, "down")):
            with patch("lyrics.page", side_effect=trouble), self.assertRaises(LyricsFailed):
                lyrics.fetch("search", artist_name="A", track_name="Song")

    def test_a_dropped_connection_is_tried_once_more(self):
        with patch("lyrics.page", side_effect=[ConnectionResetError(), "[]"]) as page:
            self.assertEqual(lyrics.fetch("search", artist_name="A", track_name="Song"), [])
        self.assertEqual(page.call_count, 2)
        with patch("lyrics.page", side_effect=TimeoutError()) as page, self.assertRaises(LyricsFailed):
            lyrics.fetch("search", artist_name="A", track_name="Song")
        self.assertEqual(page.call_count, 2)

    def test_unknown_track_and_refusals_are_not_retried(self):
        with patch("lyrics.page", side_effect=http_error(404, "no")) as page:
            self.assertIsNone(lyrics.fetch("get", artist_name="A", track_name="Song"))
        self.assertEqual(page.call_count, 1)
        with patch("lyrics.page", side_effect=http_error(429, "slow down")) as page:
            with self.assertRaisesRegex(LyricsFailed, "ограничил"):
                lyrics.fetch("get", artist_name="A", track_name="Song")
        self.assertEqual(page.call_count, 1)

    def test_request_shape(self):
        with patch("lyrics.page", return_value="[]") as page:
            self.assertEqual(lyrics.fetch("search", artist_name="Грибы", track_name="Тает лёд"), [])
        url, _, _, agent = page.call_args.args
        self.assertTrue(url.startswith("https://lrclib.net/api/search?artist_name=%D0%93"))
        self.assertEqual(agent, "OpenMusic/0.1")


if __name__ == "__main__":
    unittest.main()
