"""Run from the project folder: python3 -m unittest discover tests. The sound effects (effects.py)
are checked by what they do to simple signals: tones, clicks and noise."""
import unittest

try:
    import numpy as np
    import effects
except ImportError:
    np = None

RATE = 44100


def tone(frequency, seconds=1.0, left=1.0, right=1.0, level=0.3):
    wave = np.sin(2 * np.pi * frequency * np.arange(int(RATE * seconds)) / RATE) * level
    return np.stack([wave * left, wave * right], axis=1)


def rms(block):
    return float(np.sqrt(np.mean(block ** 2)))


def in_pieces(effect, sound, size=1000):
    return np.concatenate([effect.process(sound[start:start + size]) for start in range(0, len(sound), size)])


def decibels(ratio):
    return 20 * np.log10(ratio + 1e-12)


@unittest.skipIf(np is None, "numpy is not installed")
class Bands(unittest.TestCase):
    def test_layouts_and_presets(self):
        self.assertEqual({count: len(bands) for count, bands in effects.LAYOUTS.items()}, {5: 5, 10: 10, 15: 15, 31: 31})
        self.assertTrue(all(len(gains) == 10 and max(map(abs, gains)) <= 12 for gains in effects.PRESETS.values()))
        grouped = [name for names in effects.GROUPS.values() for name in names]
        self.assertEqual(sorted(grouped), sorted(effects.PRESETS))

    def test_refit_keeps_the_curve(self):
        rock = list(effects.PRESETS["Рок"])
        self.assertEqual(effects.refit(rock, 10), rock)
        wide = effects.refit(rock, 31)
        self.assertEqual(len(wide), 31)
        back = effects.refit(wide, 10)
        self.assertLess(max(abs(a - b) for a, b in zip(back, rock)), 1.01)
        self.assertEqual(effects.refit([3.0], 5), [3.0] * 5)
        self.assertEqual(effects.refit([], 5), [0.0] * 5)

    def test_equalizer_follows_the_bands_in_any_layout(self):
        for count in (5, 10, 15, 31):
            equalizer = effects.Equalizer(RATE)
            gains = [0.0] * count
            place = list(effects.LAYOUTS[count]).index(min(effects.LAYOUTS[count], key=lambda f: abs(f - 1000)))
            gains[place] = 6.0
            equalizer.set_gains(gains)
            sound = tone(effects.LAYOUTS[count][place])
            out = in_pieces(equalizer, sound)
            self.assertAlmostEqual(decibels(rms(out[8000:30000]) / rms(sound[8000:30000])), 6.0, delta=0.4)

    def test_cuts(self):
        equalizer = effects.Equalizer(RATE)
        equalizer.set_gains([0.0] * 10, low_cut=300, high_cut=3400)
        def passed(frequency):
            sound = tone(frequency)
            return decibels(rms(in_pieces(equalizer, sound)[8000:30000]) / rms(sound[8000:30000]))
        self.assertLess(passed(60), -30)
        self.assertLess(passed(12000), -25)
        self.assertGreater(passed(1000), -0.5)


@unittest.skipIf(np is None, "numpy is not installed")
class Effects(unittest.TestCase):
    def test_voice_takes_out_the_middle_and_keeps_the_rest(self):
        def left_after(sound):
            voice = effects.Voice(RATE)
            voice.amount = 1.0
            return decibels(rms(in_pieces(voice, sound)[4000:30000]) / rms(sound[4000:30000]))
        self.assertLess(left_after(tone(1000)), -25)                       # a voice in the middle
        self.assertGreater(left_after(tone(1000, right=-1.0)), -0.5)       # an instrument at the sides
        self.assertGreater(left_after(tone(70)), -1.5)                     # the bass
        self.assertGreater(left_after(tone(1000, right=0.0)), -7)          # hard left: half of it is "middle"

    def test_drive_keeps_the_loudness_and_adds_harmonics(self):
        drive = effects.Drive()
        drive.amount = 0.5
        noise = np.random.default_rng(1).standard_normal((RATE, 2)) * 0.16
        self.assertAlmostEqual(decibels(rms(drive.process(noise)) / rms(noise)), 0.0, delta=0.6)
        out = drive.process(tone(1000, level=0.5))[:, 0]
        spectrum = np.abs(np.fft.rfft(out * np.hanning(len(out))))
        self.assertGreater(decibels(spectrum[3000] / spectrum[1000]), -30)
        self.assertLessEqual(float(np.abs(out).max()), 1.0)

    def test_blocks_of_any_size_give_the_same_sound(self):
        sound = np.random.default_rng(2).standard_normal((20000, 2)) * 0.2
        def make(kind):
            if kind == "crush":
                effect = effects.Crush(); effect.amount = 0.6
            elif kind == "wobble":
                effect = effects.Swirl(RATE, 5.0, 1.6, 0.6, alone=True, flutter=0.12); effect.amount = 0.8
            elif kind == "chorus":
                effect = effects.Swirl(RATE, 18.0, 5.0, 0.55); effect.amount = 1.0
            elif kind == "echo":
                effect = effects.Echo(RATE); effect.mix = 0.5; effect.time = 0.07
            elif kind == "voice":
                effect = effects.Voice(RATE); effect.amount = 1.0
            else:
                effect = effects.Squeeze(RATE); effect.amount = 0.7
            return effect
        for kind in ("crush", "wobble", "chorus", "echo", "voice"):
            whole = make(kind).process(sound)
            self.assertLess(float(np.abs(whole - in_pieces(make(kind), sound, 777)).max()), 1e-9, kind)
        # The compressor follows the loudness in steps of its own, so pieces only come close.
        whole = make("squeeze").process(sound)
        self.assertLess(float(np.abs(whole - in_pieces(make("squeeze"), sound, 1024)).max()), 1e-9)

    def test_crush_holds_samples_and_coarsens_levels(self):
        crush = effects.Crush()
        crush.amount = 1.0
        out = crush.process(tone(440, 0.1))
        self.assertTrue(np.all(out[:10] == out[0]))
        self.assertLessEqual(len(np.unique(out[:, 0])), 2 ** 5 + 1)

    def test_wobble_bends_the_pitch_without_changing_the_level(self):
        wobble = effects.Swirl(RATE, 5.0, 1.6, 0.6, alone=True, flutter=0.12)
        wobble.amount = 1.0
        sound = tone(1000, 3.0)
        out = wobble.process(sound)
        self.assertAlmostEqual(rms(out[2000:]) / rms(sound[2000:]), 1.0, delta=0.02)
        self.assertGreater(float(np.abs(out[2000:] - sound[2000:]).max()), 0.05)

    def test_echo_comes_back_quieter_from_side_to_side(self):
        echo = effects.Echo(RATE)
        echo.mix, echo.time, echo.feedback = 1.0, 0.1, 0.5
        click = np.zeros((RATE, 2))
        click[0] = 1.0
        out = echo.process(click)
        first, second, third = (out[int(RATE * 0.1 * n)] for n in (1, 2, 3))
        np.testing.assert_allclose(first, [1.0, 0.0], atol=1e-9)
        np.testing.assert_allclose(second, [0.0, 0.5], atol=1e-9)
        np.testing.assert_allclose(third, [0.25, 0.0], atol=1e-9)
        self.assertEqual(float(np.abs(out[10:int(RATE * 0.1) - 10]).max()), 0.0)

    def test_squeeze_brings_loud_and_quiet_closer(self):
        def through(level):
            squeeze = effects.Squeeze(RATE)
            squeeze.amount = 0.8
            return rms(in_pieces(squeeze, tone(500, level=level), 1024)[20000:])
        loud, quiet = through(0.8), through(0.02)
        self.assertLess(decibels(loud / quiet), decibels(0.8 / 0.02) - 12)
        self.assertGreater(quiet, 0.02 * 0.7071)

    def test_swap_changes_the_sides_over(self):
        stage = effects.Stage()
        stage.swap = True
        out = stage.process(tone(440, 0.1, left=1.0, right=0.0))
        self.assertEqual((rms(out[:, 0]), round(rms(out[:, 1]), 3)), (0.0, round(rms(tone(440, 0.1)[:, 0]), 3)))

    def test_every_space_rings_for_its_time(self):
        for name, seconds in effects.SPACES.items():
            space = effects.Space(RATE)
            space.set(name, 1.0)
            click = np.zeros((int(RATE * (seconds + 1.5)), 2))
            click[0] = 1.0
            out = in_pieces(space, click, 1024)
            self.assertTrue(np.isfinite(out).all(), name)
            late = rms(out[int(RATE * (seconds + 0.5)):])
            early = rms(out[int(RATE * 0.05):int(RATE * seconds * 0.5)])
            self.assertGreater(early, 0, name)
            self.assertLess(late, early * 0.05, name)


@unittest.skipIf(np is None, "numpy is not installed")
class Automatic(unittest.TestCase):
    def test_too_little_sound_gives_no_curve(self):
        heard = effects.Tone(RATE)
        self.assertIsNone(heard.gains(10))
        heard.feed(np.zeros((RATE * 3, 2)))
        self.assertIsNone(heard.gains(10))

    def test_bright_sound_is_turned_down_at_the_top_and_dull_sound_up(self):
        rng = np.random.default_rng(4)
        white = rng.standard_normal((RATE * 4, 2)) * 0.1
        heard = effects.Tone(RATE)
        for start in range(0, len(white), 1024):
            heard.feed(white[start:start + 1024])
        bright = heard.gains(10)
        self.assertEqual(len(bright), 10)
        self.assertGreater(bright[1], bright[8] + 4)
        self.assertTrue(all(-5 <= value <= 5 for value in bright))
        # The same noise shaped the way finished music is balanced needs next to nothing.
        spectrum = np.fft.rfft(white, axis=0)
        frequencies = np.maximum(np.fft.rfftfreq(len(white), 1 / RATE), 20)
        places, levels = zip(*effects.Tone.USUAL)
        # White noise has ever more power in each higher band (3 dB an octave); that is taken out first.
        shape = np.interp(np.log10(frequencies), np.log10(places), levels) - 10 * np.log10(frequencies / 1000)
        shaped = np.fft.irfft(spectrum * (10 ** (shape / 20))[:, None], len(white), axis=0)
        level = effects.Tone(RATE)
        level.feed(shaped / np.abs(shaped).max() * 0.5)
        fair = level.gains(31)
        self.assertEqual(len(fair), 31)
        self.assertLess(max(abs(value) for value in fair), 1.01)

    def test_a_new_track_starts_from_nothing(self):
        heard = effects.Tone(RATE)
        heard.feed(np.random.default_rng(5).standard_normal((RATE * 3, 2)) * 0.1)
        self.assertIsNotNone(heard.gains(10))
        heard.reset()
        self.assertIsNone(heard.gains(10))


@unittest.skipIf(np is None, "numpy is not installed")
class WholeChain(unittest.TestCase):
    def test_everything_at_once_stays_sound(self):
        chain = effects.Chain(RATE)
        chain.configure(dict(enabled=True, bands=effects.refit(effects.PRESETS["Фонк"], 31), bass=1.0, treble=1.0, preamp=6,
                             low_cut=40, high_cut=15000, voice=1.0, drive=1.0, crush=0.5, wobble=1.0, chorus=1.0, flanger=1.0,
                             echo=0.8, echo_time=0.2, echo_feedback=0.8, compress=1.0, vinyl=1.0, orbit=True, width=2.0,
                             balance=0.3, swap=True, crossfeed=True, level=True, space="Пещера", space_mix=1.0))
        chain.speed.rate = 1.25
        sound = (np.random.default_rng(6).standard_normal((60000, 2)) * 0.3).astype(np.float32)
        out = [chain.process(sound[start:start + size]) for start, size in ((0, 1024), (1024, 4096), (5120, 333), (5453, 20000))]
        whole = np.concatenate(out)
        self.assertTrue(np.isfinite(whole).all())
        self.assertLessEqual(float(np.abs(whole).max()), 1.0)
        self.assertEqual(whole.dtype, np.float32)
        chain.reset()
        self.assertTrue(np.isfinite(chain.process(sound[:1024])).all())

    def test_settings_of_an_older_version_still_work(self):
        chain = effects.Chain(RATE)
        chain.configure(dict(enabled=True, bands=[0.0] * 10, space="Зал", space_mix=0.35, echo=None, low_cut="x"))
        self.assertTrue(np.isfinite(chain.process(np.zeros((1024, 2), dtype=np.float32))).all())


if __name__ == "__main__":
    unittest.main()
