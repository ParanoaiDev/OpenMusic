"""How stream.py chooses among the uploads a search returns, how mixes.py gathers artists into
circles, and the skips userdata.py keeps. No network."""
import tempfile
import unittest
from pathlib import Path

import mixes
import stream
import userdata
from library import Track
from similar import Pick, blend, voice


def upload(title, uploader, plays, seconds=200):
    return dict(title=title, uploader=uploader, plays=plays, duration=seconds)


def chosen(artist, title, *uploads):
    """The upload the search would take: the best of those that are the track at all."""
    scored = [(stream.score(item, artist, title), item) for item in uploads]
    best = max(scored, key=lambda pair: pair[0])
    return best[1]["uploader"] if best[0] >= 1 else None


class Choice(unittest.TestCase):
    def test_the_original_beats_a_cover_in_another_language(self):
        self.assertEqual(chosen("Feduk & Allj", "Розовое вино",
                                upload("Feduk & Allj - Розовое вино - (po polsku)", "cotytutajrobisz", 1478),
                                upload("Розовое вино (feat. FEDUK)", "Элджей", 11_726_601)), "Элджей")

    def test_the_artist_in_russian_letters_is_the_artist(self):
        self.assertEqual(chosen("Monetochka", "Нимфоманка",
                                upload("Бисквитное Мюзле - Нимфоманка (Monetochka cover)", "Бисквитное Мюзле", 466),
                                upload("Нимфоманка", "Монеточка", 4_553_916)), "Монеточка")
        self.assertEqual(chosen("Max Korzh", "Слово пацана",
                                upload("Макс Корж - Слово Пацана (Viau Luminex Remix)", "Viau Luminex", 3058),
                                upload("Слово пацана", "Макс Корж", 121_479)), "Макс Корж")

    def test_a_version_the_track_is_not_loses(self):
        self.assertEqual(chosen("PHARAOH & Boulevard Depo", "5 Минут Назад",
                                upload("PHARAOH, Boulevard Depo - 5 Минут Назад (gdespryatal Blend)", "gdespryatal", 23_951),
                                upload("5 минут назад", "Boulevard Depo", 6_260_618)), "Boulevard Depo")
        self.assertEqual(chosen("My", "Возможно",
                                upload("мы - возможно (opium + speed  /// by lowblue)", "yaytso", 5701, 101),
                                upload("МЫ - Возможно", "Исповедую пути господни", 4_677_028, 136)), "Исповедую пути господни")

    def test_a_remix_is_found_when_a_remix_is_asked_for(self):
        self.assertEqual(chosen("LSP", "Бэйби (Remix)", upload("Бэйби", "ЛСП", 900_000), upload("Бэйби (Remix)", "ЛСП", 300_000)), "ЛСП")
        self.assertGreater(stream.score(upload("Бэйби (Remix)", "ЛСП", 300_000), "LSP", "Бэйби (Remix)"),
                           stream.score(upload("Бэйби (Remix)", "ЛСП", 300_000), "LSP", "Бэйби"))

    def test_a_song_of_the_same_name_by_someone_else_loses(self):
        self.assertEqual(chosen("Земфира", "НЕ ОТПУСКАЙ",
                                upload("Не Отпускай - kamazz", "MBlade", 6_457_335),
                                upload("Земфира - не отпускай", "polina", 12_000)), "polina")

    def test_the_label_with_millions_beats_a_fan_page(self):
        self.assertEqual(chosen("Lizer", "False Mirror",
                                upload("LIZER & FLESH - FALSE MIRROR (Prod. by Taz Taylor)", "ЗАКАТ 99.1", 15_212_143, 142),
                                upload("LIZER & FLESH - FALSE MIRROR (Prod. By Taz Taylor)", "LIZER FAN", 40_483, 142)), "ЗАКАТ 99.1")

    def test_the_artists_own_page_beats_a_reupload_of_the_same_size(self):
        self.assertEqual(chosen("MORGENSHTERN", "Вот так",
                                upload("MORGENSHTERN - Вот Так", "Rap Factory", 241_304, 126),
                                upload("Вот так", "MORGENSHTERN", 13_807, 126)), "MORGENSHTERN")

    def test_a_broadcast_or_a_preview_is_not_the_track(self):
        self.assertIsNone(chosen("Prāta Vētra", "На заре", upload("B гостях на Radio Skonto Plus группа Prāta Vētra на заре", "Radio Skonto Plus", 1121, 2680)))
        self.assertIsNone(chosen("FACE", "Бургер", upload("FACE - Бургер", "FACE", 5_000_000, 30)))

    def test_another_song_is_not_the_track(self):
        self.assertIsNone(chosen("FACE", "Бургер", upload("FACE - Юморист", "FACE", 12_000_000)))

    def test_a_transliterated_title_finds_the_russian_one(self):
        self.assertGreaterEqual(stream.score(upload("ЛСП - Тело", "ЛСП", 2_000_000), "LSP", "Telo"), stream.GOOD)

    def test_artists_named_by_sound_and_as_whole_words(self):
        self.assertTrue(stream.same_artist("MC Khovansky", "МС ХОВАНСКИЙ - Батя в Здании"))
        self.assertTrue(stream.same_artist("Feduk & Allj", "Розовое вино (feat. FEDUK)"))
        self.assertFalse(stream.same_artist("My", "My Chemical Romance - Helena".replace("My ", "Mylo ")))
        self.assertFalse(stream.same_artist("FACE", "Facebook jingle"))


class Circles(unittest.TestCase):
    NEXT = {"face": {"pharaoh", "kizaru", "lizer"}, "pharaoh": {"face", "kizaru", "boulevard"}, "lizer": {"face", "flesh", "kizaru"},
            "monetochka": {"grechka", "noize", "mi"}, "mi": {"monetochka", "grechka", "luna"},
            "leningrad": {"splin", "zveri"}}

    def test_artists_that_go_together_end_up_together(self):
        groups = sorted(sorted(group) for group in mixes.circles(list(self.NEXT), self.NEXT))
        self.assertEqual(groups, [["face", "lizer", "pharaoh"], ["leningrad"], ["mi", "monetochka"]])

    def test_strangers_stay_apart(self):
        self.assertEqual(mixes.closeness("face", "leningrad", self.NEXT), 0)
        self.assertGreater(mixes.closeness("face", "pharaoh", self.NEXT), mixes.closeness("pharaoh", "lizer", self.NEXT))

    def test_signature_follows_the_artists_not_the_tracks(self):
        one = [Track("А", "FACE", "Spotify", ""), Track("Б", "Max Korzh", "Spotify", "")]
        self.assertEqual(mixes.signature(one), mixes.signature(one + [Track("В", "Макс Корж", "Deezer", "")]))
        self.assertNotEqual(mixes.signature(one), mixes.signature(one + [Track("В", "LSP", "Spotify", "")]))

    def test_mix_takes_own_and_new_tracks_in_turn(self):
        def item(title, artist="A"):
            return dict(title=title, artist=artist, source="Deezer", url="", artwork="https://e.example/1.jpg")
        built = dict(circles=[dict(artists=["FACE", "PHARAOH", "Lizer"], own=[item(f"свой {n}", "FACE") for n in range(30)],
                                   new=[item(f"новый {n}", "Kizaru") for n in range(6)])])
        (tracks, names, artwork), = mixes.arrange(built, day=5)
        self.assertEqual(names, ["FACE", "PHARAOH", "Lizer"])
        self.assertEqual([track.artist for track in tracks[:6]], ["FACE", "Kizaru"] * 3)
        self.assertEqual(sum(track.artist == "Kizaru" for track in tracks), 6)
        self.assertEqual(len(tracks), mixes.OWN + 6)
        self.assertEqual(len({track.title for track in tracks}), len(tracks))
        self.assertEqual(artwork[("Kizaru", "новый 0")], "https://e.example/1.jpg")
        again, other = mixes.arrange(built, day=5)[0][0], mixes.arrange(built, day=6)[0][0]
        self.assertEqual(tracks, again)
        self.assertNotEqual([track.title for track in tracks], [track.title for track in other])


class Skips(unittest.TestCase):
    def test_skips_are_counted_by_track(self):
        with tempfile.TemporaryDirectory() as folder:
            data = userdata.UserData(Path(folder) / "user.sqlite3")
            one, other = Track("Раз", "Артист", "Deezer", ""), Track("Два", "Артист", "Deezer", "")
            for track in (one, one, other):
                data.skipped(track)
            self.assertEqual(sorted((track.title, count) for track, count in data.skips()), [("Два", 1), ("Раз", 2)])
            self.assertEqual(data.skips(since=4_000_000_000), [])

    def test_an_artist_switched_off_goes_down_and_then_out(self):
        seed = Track("Гоша рубчинский", "FACE", "Spotify", "")
        lists = {"Deezer": [Pick(Track("Раз", "Нелюбимый", "Deezer", ""), "", 180), Pick(Track("Два", "Другой", "Deezer", ""), "", 180)]}
        self.assertEqual(blend(seed, lists)[0].track.artist, "Нелюбимый")
        self.assertEqual(blend(seed, lists, avoid={voice("Нелюбимый"): 2})[0].track.artist, "Другой")
        self.assertEqual([pick.track.artist for pick in blend(seed, lists, avoid={voice("Нелюбимый"): 4})], ["Другой"])


if __name__ == "__main__":
    unittest.main()
