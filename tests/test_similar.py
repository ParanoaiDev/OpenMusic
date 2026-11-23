"""similar.py without the network: how names are compared, how uploads are read, how the answers of
the services are blended into one list; and the jams userdata.py keeps."""
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import similar
import userdata
from library import Track
from similar import Pick, blend, named, song_key, voice


def picks(source, *names, seconds=180):
    return [Pick(Track(title, artist, source, f"https://{source.lower()}.example/{number}"), "", seconds)
            for number, (artist, title) in enumerate(names)]


SEED = Track("Гоша рубчинский", "FACE", "Spotify", "")


class Names(unittest.TestCase):
    def test_one_artist_in_two_alphabets(self):
        for latin, russian in (("Max Korzh", "Макс Корж"), ("Skryptonite", "Скриптонит"), ("Scriptonite", "Скриптонит"),
                               ("Oxxxymiron", "Оксимирон"), ("Poshlaya Molly", "Пошлая Молли"), ("Tima Belorusskih", "Тима Белорусских"),
                               ("Eldzhey", "Элджей"), ("MC Khovansky", "МС ХОВАНСКИЙ"), ("Monetochka", "Монеточка"), ("My", "МЫ"),
                               ("LSP", "ЛСП"), ("Nervy", "Нервы"), ("Electroforez", "Электрофорез"), ("FACE", "Face")):
            self.assertEqual(voice(latin), voice(russian), (latin, russian))

    def test_different_artists_stay_different(self):
        names = ("FACE", "Pharaoh", "Kizaru", "LSP", "Monetochka", "Morgenshtern", "Max Korzh", "Leningrad", "Feduk", "Lizer")
        self.assertEqual(len({voice(name) for name in names}), len(names))

    def test_first_of_several_artists(self):
        for line in ("PHARAOH & Boulevard Depo", "PHARAOH feat. Boulevard Depo", "PHARAOH, Boulevard Depo", "PHARAOH x Boulevard Depo"):
            self.assertEqual(similar.main_artist(line), "PHARAOH")
        self.assertEqual(similar.main_artist("Oxxxymiron"), "Oxxxymiron")

    def test_same_song_whatever_the_spelling(self):
        self.assertEqual(song_key("LSP", "Telo"), song_key("ЛСП", "Тело"))
        self.assertEqual(song_key("Би-2", "Серебро (Акустика)"), song_key("Би-2", "Серебро"))
        self.assertEqual(song_key("Big Baby Tape", "ВЛЮБИЛАСЬ"), song_key("Big Baby Tape", "Влюбилась (feat. Молодой Платон)"))
        self.assertNotEqual(song_key("FACE", "Бургер"), song_key("FACE", "Юморист"))

    def test_upload_read_as_artist_and_title(self):
        for shown, uploader, expected in (
                ("FACE - Гоша Рубчинский (prod. by Tommy Kruise)", "FACE", ("FACE", "Гоша Рубчинский")),
                ("Forever Young", "FACE", ("FACE", "Forever Young")),
                ("Ленинград — Вояж / Leningrad — Voyage", "Ленинград", ("Ленинград", "Вояж")),
                ("Макс Корж - Малый повзрослел (official video)", "Max Korzh", ("Макс Корж", "Малый повзрослел")),
                ("T-Fest - Одно я знал / Выдох", "T-Fest", ("T-Fest", "Одно я знал / Выдох")),
                ("MORGENSHTERN - КРАСНЫЙ ФЛАГ (Lyric Video, 2025)", "MORGENSHTERN", ("MORGENSHTERN", "КРАСНЫЙ ФЛАГ")),
                ("Ленинград — Ёж (Премьера клипа 2025) 16+", "Ленинград", ("Ленинград", "Ёж")),
                ("08. Kozak System - Така Спокуслива", "ukrmusic7", ("Kozak System", "Така Спокуслива")),
                ("Батя в здании", "МС Хованский - Topic", ("МС Хованский", "Батя в здании"))):
            self.assertEqual(named(shown, uploader), expected)

    def test_soundcloud_track_is_named_by_its_title(self):
        self.assertEqual(similar.names_of(Track("FACE - СПАСАТЕЛЬНЫЙ КРУГ", "RIOto", "SoundCloud", "")), ("FACE", "СПАСАТЕЛЬНЫЙ КРУГ"))
        self.assertEqual(similar.names_of(Track("90", "Monetochka", "Spotify", "")), ("Monetochka", "90"))

    def test_artist_heard_in_a_video(self):
        self.assertTrue(similar.mentions("MC Khovansky", "МС ХОВАНСКИЙ - Батя в Здании", "Юрий Хованский"))
        self.assertTrue(similar.mentions("FACE", "FACE - Гоша Рубчинский", "FACE"))
        self.assertFalse(similar.mentions("FACE", "Pharaoh - Black Siemens", "Dead Dynasty"))


class Blend(unittest.TestCase):
    def test_seed_and_skipped_songs_are_left_out(self):
        lists = {"Deezer": picks("Deezer", ("Face", "Гоша Рубчинский"), ("Pharaoh", "Caramel"), ("Kizaru", "Дежавю"))}
        found = blend(SEED, lists, skip={song_key("Kizaru", "Дежавю")})
        self.assertEqual([pick.track.title for pick in found], ["Caramel"])

    def test_versions_the_seed_is_not_are_left_out(self):
        lists = {"YouTube": picks("YouTube", ("Pharaoh", "Caramel (Remix)"), ("Pharaoh", "Caramel slowed + reverb"),
                                  ("Kizaru", "Дежавю (Live)"), ("Lizer", "Пачка сигарет"))}
        self.assertEqual([pick.track.title for pick in blend(SEED, lists)], ["Пачка сигарет"])
        remix = Track("Бэйби (Remix)", "LSP", "Spotify", "")
        self.assertIn("Caramel (Remix)", [pick.track.title for pick in blend(remix, lists)])

    def test_skits_and_whole_albums_are_left_out(self):
        lists = {"Deezer": picks("Deezer", ("Pharaoh", "Интро"), seconds=40) + picks("Deezer", ("Kizaru", "Весь альбом"), seconds=3000)
                 + picks("Deezer", ("Lizer", "Улица"))}
        self.assertEqual([pick.track.title for pick in blend(SEED, lists)], ["Улица"])

    def test_what_two_services_agree_on_comes_first(self):
        lists = {"Deezer": picks("Deezer", ("Kizaru", "Дежавю"), ("Lizer", "Улица"), ("Pharaoh", "Caramel")),
                 "YouTube": picks("YouTube", ("Yanix", "Москва"), ("T-Fest", "Улети"), ("PHARAOH", "Caramel (Official Video)"))}
        found = blend(SEED, lists)
        self.assertEqual(found[0].track.title, "Caramel")
        self.assertEqual(len(found), 5)        # the same song from two services is one entry

    def test_an_artist_gets_a_few_places_only(self):
        own = [("FACE", f"Трек {number}") for number in range(30)]
        other = [("Pharaoh", f"Песня {number}") for number in range(30)]
        rest = [(f"Артист {number}", "Одна") for number in range(40)]
        found = blend(SEED, {"SoundCloud": picks("SoundCloud", *own), "Deezer": picks("Deezer", *other, *rest)}, count=40)
        places = Counter(voice(pick.track.artist) for pick in found)
        self.assertEqual(len(found), 40)
        self.assertEqual(places[voice("FACE")], 5)
        self.assertEqual(places[voice("Pharaoh")], 3)

    def test_the_same_artist_does_not_play_twice_in_a_row(self):
        lists = {"Deezer": picks("Deezer", *[("Pharaoh", f"Песня {n}") for n in range(3)], *[("Kizaru", f"Трек {n}") for n in range(3)],
                                 *[("Lizer", f"Вещь {n}") for n in range(3)])}
        artists = [pick.track.artist for pick in blend(SEED, lists, count=9)]
        self.assertTrue(all(one != other for one, other in zip(artists, artists[1:])), artists)

    def test_near_and_familiar_artists_go_up(self):
        lists = {"Deezer": picks("Deezer", ("Чужой", "Раз"), ("Сосед", "Два"), ("Знакомый", "Три"))}
        self.assertEqual(blend(SEED, lists, near={voice("Сосед")})[0].track.artist, "Сосед")
        self.assertEqual(blend(SEED, lists, taste={voice("Знакомый")}, near={voice("Знакомый")})[0].track.artist, "Знакомый")

    def test_russian_spelling_of_a_title_is_kept(self):
        lists = {"Deezer": picks("Deezer", ("LSP", "Telo")), "YouTube": picks("YouTube", ("ЛСП", "Тело"))}
        found = blend(SEED, lists)
        self.assertEqual([(pick.track.artist, pick.track.title) for pick in found], [("ЛСП", "Тело")])

    def test_one_service_listing_a_song_twice_says_it_once(self):
        lists = {"SoundCloud": picks("SoundCloud", ("FACE", "Юморист"), ("FACE", "ЮМОРИСТ"), ("Kizaru", "Дежавю")),
                 "Deezer": picks("Deezer", ("Lizer", "Улица"))}
        found = blend(SEED, lists)
        self.assertEqual(sorted(pick.track.title.lower() for pick in found), ["дежавю", "улица", "юморист"])
        self.assertEqual(found[0].track.title, "Улица")

    def test_nothing_from_nothing(self):
        self.assertEqual(blend(SEED, {}), [])


class Jams(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.data = userdata.UserData(Path(self.folder.name) / "user.sqlite3")

    def tearDown(self):
        self.folder.cleanup()

    def tracks(self, name, count):
        return [Track(f"{name} {number}", "Артист", "Deezer", "") for number in range(count)]

    def test_jam_is_kept_in_order(self):
        tracks = self.tracks("Трек", 5)
        jam = self.data.save_jam(tracks)
        self.assertEqual(self.data.jam_tracks(jam), tracks)
        self.assertEqual(self.data.jams(), [(jam, tracks[0], 5)])

    def test_jam_from_the_same_track_replaces_the_old_one(self):
        first = self.tracks("Трек", 3)
        self.data.save_jam(first)
        jam = self.data.save_jam([first[0], *self.tracks("Другой", 6)])
        self.assertEqual([(number, count) for number, _, count in self.data.jams()], [(jam, 7)])

    def test_only_the_latest_jams_are_kept(self):
        for number in range(userdata.UserData.JAMS + 5):
            self.data.save_jam(self.tracks(f"Джем {number}", 2))
        jams = self.data.jams()
        self.assertEqual(len(jams), userdata.UserData.JAMS)
        self.assertEqual(jams[0][1].title, f"Джем {userdata.UserData.JAMS + 4} 0")

    def test_deleted_jam_takes_its_tracks_along(self):
        jam = self.data.save_jam(self.tracks("Трек", 4))
        self.data.delete_jam(jam)
        self.assertEqual(self.data.jams(), [])
        self.assertEqual(self.data.jam_tracks(jam), [])

    def test_unfinished_jam_is_gone_after_a_restart(self):
        self.data.save_jam(self.tracks("Один", 1))
        whole = self.data.save_jam(self.tracks("Целый", 3))
        again = userdata.UserData(self.data.path)
        self.assertEqual([number for number, _, _ in again.jams()], [whole])


if __name__ == "__main__":
    unittest.main()
