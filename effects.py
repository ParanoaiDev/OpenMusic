"""Sound effects for OpenMusic, applied to the decoded audio block by block (ui/audio_engine.py
feeds it). numpy only, no Qt. Every effect keeps its own state between blocks, so the sound is
continuous; the whole chain stays well under a millisecond or two per 23 ms block.

Chain: speed → equalizer (5 to 31 bands, bass and clarity shelves, low and high cut, all one
filter) → voice removal → tape warmth → lo-fi → cassette wow → vinyl → chorus → flanger → echo →
8D → stereo width, balance, swap → headphone crossfeed → space (reverb) → compressor → even
loudness → limiter."""
import math

import numpy as np

BANDS = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
# The equalizer in 5, 10, 15 or 31 bands: the same curve, drawn with fewer or more points.
LAYOUTS = {
    5: (60, 230, 910, 3600, 14000),
    10: BANDS,
    15: (25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000, 16000),
    31: (20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500,
         3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000),
}
# Ready-made curves, each written for the ten bands above and fitted to the other layouts.
PRESETS = {
    "Без изменений": (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    "Больше баса": (7, 6, 4.5, 2, 0, 0, 0, 0, 0, 0),
    "Глубокий бас": (9, 6.5, 2.5, 0, -1, 0, 0, 0, 0, 0),
    "Больше высоких": (0, 0, 0, 0, 0, 0.5, 2, 4, 5.5, 6),
    "Вокал": (-3, -2, -1, 1, 3, 4, 3.5, 2, 0, -1),
    "Улыбка": (6, 5, 3, 0.5, -2, -2.5, -0.5, 2.5, 5, 6),
    "Середина": (-3, -2, 0, 2, 4, 4.5, 3.5, 1.5, -1, -2.5),
    "Ярче": (-1, -1, 0, 0, 0, 1, 2.5, 4, 4.5, 4),
    "Мягче": (1, 1.5, 1.5, 1, 0, -0.5, -1.5, -3, -4.5, -6),
    "Тихая громкость": (8, 6, 3.5, 1, 0, 0, 0.5, 2, 4, 5.5),
    "Хип-хоп": (5.5, 5, 2, 1, -1, -1, 0.5, 1, 2, 2.5),
    "Рэп": (5, 4.5, 1.5, 0, -0.5, 1.5, 3, 2.5, 1.5, 1),
    "Фонк": (8, 7, 3.5, -1, -2.5, -1, 1, 3, 4, 3),
    "Рок": (4.5, 3.5, 2, -1, -2, -0.5, 2, 3, 4, 4.5),
    "Метал": (5, 4, 0, -2.5, -3.5, -1, 2.5, 4.5, 5, 4),
    "Поп": (-1, 0, 2, 3.5, 4, 3, 1, 0, -0.5, -1),
    "Инди": (2, 2.5, 1.5, 0, 1, 2, 1.5, 2.5, 3, 2),
    "Электроника": (5, 4, 1.5, 0, -1.5, 1, 0.5, 2, 4, 5),
    "Танцевальная": (6.5, 5.5, 2.5, 0, -1, -2, -0.5, 2, 4, 4.5),
    "R&B": (4, 6, 4.5, 1, -1.5, -1, 1.5, 2, 2.5, 3),
    "Регги": (0, 0, -0.5, -2.5, 0, 3.5, 3.5, 0.5, 0, 0),
    "Латино": (3.5, 2.5, 0, 0, -1.5, -1.5, -1, 0.5, 3, 4.5),
    "Джаз": (3, 2, 1, 2, -1.5, -1.5, 0, 1.5, 3, 3.5),
    "Классика": (4, 3, 2.5, 1, -1, -1, 0, 2, 3, 4),
    "Акустика": (3.5, 3, 2, 0.5, 1, 1, 2.5, 3, 2.5, 1.5),
    "Lo-fi": (3, 3.5, 2.5, 1, 0, -1, -2.5, -4.5, -7, -10),
    "Ночь": (-5, -3.5, -1.5, 0, 1, 1.5, 1, 0, -1, -2),
    "Вечеринка": (6, 5.5, 3, 0, 0, 0, 0.5, 2.5, 4.5, 5),
    "Спокойно": (1.5, 1.5, 1, 0.5, 0, -0.5, -1, -2, -3, -3.5),
    "Речь и подкасты": (-8, -5, -2, 0.5, 2.5, 4, 4.5, 3, 0, -3),
    "Кино": (5, 4, 2, 0, -0.5, 1, 2.5, 3, 3, 2.5),
    "Вкладыши": (5, 4.5, 3, 1, 0, 0, -1, 0.5, 2, 2.5),
    "Большие наушники": (2, 1.5, 0.5, 0, -0.5, 0, 1, 2, 2.5, 2),
    "Ноутбук": (-9, -4, 3, 4.5, 2.5, 0.5, 1, 2.5, 3.5, 3),
    "Маленькая колонка": (-6, 0, 4.5, 4, 1.5, 0, 0.5, 2, 3, 2.5),
    "Телефон": (-10, -6, 0, 3.5, 3, 1, 1.5, 3, 3, 1),
    "Автомобиль": (4.5, 4, 1, -1.5, -1, 0, 1, 2, 3, 3.5),
    "Телевизор": (-2, 1, 3, 2, 0.5, 1.5, 3, 3, 1.5, 0),
}
# How the panel lays the presets out.
GROUPS = {
    "Основные": ("Без изменений", "Больше баса", "Глубокий бас", "Больше высоких", "Вокал", "Улыбка", "Середина", "Ярче",
                 "Мягче", "Тихая громкость"),
    "Жанры": ("Хип-хоп", "Рэп", "Фонк", "Рок", "Метал", "Поп", "Инди", "Электроника", "Танцевальная", "R&B", "Регги",
              "Латино", "Джаз", "Классика", "Акустика", "Lo-fi"),
    "Настроение": ("Ночь", "Вечеринка", "Спокойно", "Речь и подкасты", "Кино"),
    "Устройства": ("Вкладыши", "Большие наушники", "Ноутбук", "Маленькая колонка", "Телефон", "Автомобиль", "Телевизор"),
}
# Rooms: how long the sound rings in each, in seconds.
SPACES = {"Студия": 0.3, "Комната": 0.55, "Клуб": 1.0, "Зал": 1.7, "Стадион": 2.6, "Собор": 3.6, "Пещера": 4.4}
# What sets some rooms apart: how fast the ringing darkens (40 for the rest) and an echo off a far wall, in seconds.
SHAPES = {"Студия": dict(dark=25), "Клуб": dict(dark=95), "Стадион": dict(slap=0.17), "Пещера": dict(dark=130, slap=0.11)}


def centres(count):
    """The band frequencies for a number of gains: a known layout, or that many spread evenly in pitch."""
    return LAYOUTS.get(count) or tuple(float(value) for value in np.geomspace(31, 16000, max(2, count)))


def refit(gains, count):
    """The same curve on another number of bands."""
    gains = [float(value) for value in gains]
    if len(gains) == count:
        return gains
    if len(gains) < 2:
        return [gains[0] if gains else 0.0] * count
    fitted = np.interp(np.log10(centres(count)), np.log10(centres(len(gains))), gains)
    return [round(float(value) * 2) / 2 for value in fitted]


class Equalizer:
    """The bands as one linear-phase FIR filter, applied by fast convolution (overlap-add). The
    filter always runs, flat when all bands are at 0 dB, so turning it on or off never clicks."""

    TAPS = 2047

    def __init__(self, rate):
        self.rate = rate
        self.gains = [0.0] * len(BANDS)
        self.bass = self.treble = self.low_cut = self.high_cut = 0.0
        self.tail = None
        self.size = 0
        self.spectrum = None

    def set_gains(self, gains, bass=0.0, treble=0.0, low_cut=0.0, high_cut=0.0):
        """The bands in dB (5, 10, 15 or 31 of them), plus a bass shelf (0…1: up to +9 dB under
        100 Hz), a clarity shelf (0…1: up to +7 dB of presence and air above 4 kHz) and two cuts in
        Hz, 0 for none: everything below low_cut and above high_cut falls away at 18 dB an octave.
        All of it is folded into the one filter."""
        self.gains = [float(value) for value in gains] or [0.0] * len(BANDS)
        if len(self.gains) < 2:
            self.gains = self.gains * 2
        self.bass = float(bass)
        self.treble = float(treble)
        self.low_cut = float(low_cut or 0.0)
        self.high_cut = float(high_cut or 0.0)
        self.spectrum = None

    def curve(self, frequencies):
        """The response in dB at these frequencies: the bands, the two shelves on top, the cuts."""
        frequencies = np.maximum(frequencies, 1.0)
        decibels = np.interp(np.log10(np.maximum(frequencies, 10.0)), np.log10(centres(len(self.gains))), self.gains)
        if self.bass:
            decibels = decibels + self.bass * 9 / (1 + (frequencies / 100) ** 2)
        if self.treble:
            ratio = (frequencies / 4500) ** 2
            decibels = decibels + self.treble * 7 * ratio / (1 + ratio)
        if self.low_cut > 0:
            decibels = decibels - 10 * np.log10(1 + (self.low_cut / frequencies) ** 6)
        if self.high_cut > 0:
            decibels = decibels - 10 * np.log10(1 + (frequencies / self.high_cut) ** 6)
        return np.maximum(decibels, -80.0)

    def design(self, size):
        bins = size // 2 + 1
        frequencies = np.linspace(0, self.rate / 2, bins)
        decibels = self.curve(frequencies)
        magnitude = 10 ** (decibels / 20)
        impulse = np.fft.irfft(magnitude, size)
        impulse = np.roll(impulse, self.TAPS // 2)[: self.TAPS] * np.hanning(self.TAPS)
        self.spectrum = np.fft.rfft(impulse, size)
        self.size = size

    def process(self, block):
        frames = len(block)
        size = 1 << int(math.ceil(math.log2(frames + self.TAPS - 1)))
        if self.spectrum is None or self.size != size:
            self.design(size)
        out = np.fft.irfft(np.fft.rfft(block, size, axis=0) * self.spectrum[:, None], size, axis=0)
        if self.tail is not None:
            length = min(len(self.tail), len(out))
            out[:length] += self.tail[:length]
        self.tail = out[frames:frames + self.TAPS - 1].copy()
        return out[:frames]


class Space:
    """A room, hall or cathedral: the sound convolved with a made-up impulse response (early
    reflections, then a decaying, darkening tail, different on the left and the right), by uniformly
    partitioned convolution so that a long tail costs little per block."""

    def __init__(self, rate, block=1024):
        self.rate = rate
        self.block = block
        self.kind = None
        self.mix = 0.0
        self.partitions = None
        self.history = None
        self.previous = np.zeros((block, 2), dtype=np.float32)

    def set(self, kind, mix):
        self.mix = float(mix)
        if kind != self.kind:
            self.kind = kind
            self.partitions = self.impulse(SPACES[kind], **SHAPES.get(kind, {})) if kind in SPACES else None
            self.history = None

    def impulse(self, seconds, dark=40, slap=0.0):
        rng = np.random.default_rng(11)
        length = int(seconds * self.rate)
        t = np.arange(length) / self.rate
        decay = np.exp(-6.9 * t / seconds)
        noise = rng.standard_normal((length, 2)) * decay[:, None]
        # Darker as it fades: a running mean over a window that grows along the tail.
        smooth = np.cumsum(noise, axis=0)
        width = (1 + dark * t / seconds).astype(int)
        index = np.arange(length)
        start = np.maximum(index - width, 0)
        noise = (smooth[index] - smooth[start]) / width[:, None]
        for delay, gain in ((0.011, 0.8), (0.019, 0.6), (0.027, 0.5), (0.041, 0.35)):
            at = int(delay * self.rate * (0.6 + 0.4 * seconds))
            if at < length:
                noise[at, 0] += gain
                noise[min(length - 1, int(at * 1.13)), 1] += gain
        if slap:
            # The far wall of a big place answers once, clearly, a little later on one side.
            for channel, delay in ((0, slap), (1, slap * 1.31)):
                at = int(delay * self.rate)
                if at < length:
                    noise[at, channel] += 0.55
        noise /= np.sqrt(np.sum(noise ** 2, axis=0, keepdims=True)) + 1e-9
        pieces = -(-length // self.block)
        padded = np.zeros((pieces * self.block, 2))
        padded[:length] = noise
        parts = padded.reshape(pieces, self.block, 2)
        return np.fft.rfft(parts, 2 * self.block, axis=1)

    def process(self, block):
        """Takes blocks of any length: they are cut into the partition size, with what is left over
        carried to the next call (so the reverb adds one block of delay, 23 ms, only while on)."""
        if self.partitions is None or self.mix <= 0:
            self.carry = None
            return block
        if getattr(self, "carry", None) is not None and len(self.carry):
            block = np.concatenate([self.carry, block])
        out = []
        while len(block) >= self.block:
            out.append(self.process_one(block[:self.block]))
            block = block[self.block:]
        self.carry = block
        if not out:
            return np.zeros((0, 2))
        return np.concatenate(out)

    def process_one(self, block):
        pieces = len(self.partitions)
        if self.history is None:
            self.history = np.zeros_like(self.partitions)
        spectrum = np.fft.rfft(np.concatenate([self.previous, block]), 2 * self.block, axis=0)
        self.history = np.roll(self.history, 1, axis=0)
        self.history[0] = spectrum
        wet = np.fft.irfft(np.sum(self.history * self.partitions, axis=0), 2 * self.block, axis=0)[self.block:]
        self.previous = block
        return block * (1 - 0.35 * self.mix) + wet * self.mix * 0.9


class Orbit:
    """8D: the sound circles around the head. The middle of the mix pans around with a slow LFO,
    the far ear hears it a little later and darker; the sides of the mix stay where they are."""

    def __init__(self, rate):
        self.rate = rate
        self.on = False
        self.speed = 0.12
        self.phase = 0.0
        self.last = np.zeros(2)

    def process(self, block):
        if not self.on:
            return block
        frames = len(block)
        t = self.phase + np.arange(frames) * (2 * math.pi * self.speed / self.rate)
        self.phase = float(t[-1] + 2 * math.pi * self.speed / self.rate) % (2 * math.pi)
        pan = np.sin(t)
        mid = block.mean(axis=1)
        side = (block[:, 0] - block[:, 1]) * 0.5
        left = mid * np.cos((pan + 1) * math.pi / 4) * 1.25 + side * 0.4
        right = mid * np.sin((pan + 1) * math.pi / 4) * 1.25 - side * 0.4
        # Behind the head (cosine of the phase < 0) the sound is a little duller.
        dull = 0.5 * (1 - np.cos(t)) * 0.35
        out = np.stack([left, right], axis=1)
        smoothed = np.empty_like(out)
        smoothed[0] = self.last * 0.5 + out[0] * 0.5
        smoothed[1:] = (out[1:] + out[:-1]) * 0.5
        self.last = out[-1]
        return out * (1 - dull[:, None]) + smoothed * dull[:, None]


class Vinyl:
    """An old record: crackle and a little hiss, the top and bottom of the range rolled off."""

    def __init__(self, rate):
        self.rate = rate
        self.amount = 0.0
        self.rng = np.random.default_rng(5)
        self.kernel = np.hanning(9) / np.hanning(9).sum()
        self.tail = np.zeros((len(self.kernel) - 1, 2))

    def process(self, block):
        if self.amount <= 0:
            return block
        frames = len(block)
        padded = np.concatenate([self.tail, block])
        dull = np.stack([np.convolve(padded[:, channel], self.kernel, mode="valid") for channel in range(2)], axis=1)
        self.tail = padded[-(len(self.kernel) - 1):]
        out = block * (1 - self.amount * 0.7) + dull * (self.amount * 0.7)
        out -= np.mean(out, axis=0) * 0.0
        crackle = np.zeros(frames)
        clicks = self.rng.poisson(14 * self.amount * frames / self.rate)
        for _ in range(clicks):
            at = self.rng.integers(0, frames)
            length = min(frames - at, int(self.rng.integers(8, 60)))
            crackle[at:at + length] += self.rng.uniform(0.05, 0.25) * np.exp(-np.arange(length) / 6) * self.rng.choice((-1, 1))
        hiss = self.rng.standard_normal(frames) * 0.004
        noise = (crackle + hiss) * self.amount
        return out + noise[:, None]


class Speed:
    """Plays faster or slower by resampling, so the pitch goes with the speed, as a record turning
    faster: "Nightcore" up, "Slowed" down. Linear interpolation, continuous across blocks."""

    def __init__(self):
        self.rate = 1.0
        self.phase = 0.0
        self.last = np.zeros(2)

    def process(self, block):
        if abs(self.rate - 1.0) < 1e-3:
            self.last = block[-1].copy() if len(block) else self.last
            self.phase = 0.0
            return block
        source = np.concatenate([self.last[None, :], block])
        span = len(source) - 1
        positions = np.arange(self.phase, span, self.rate)
        if not len(positions):
            return block[:0]
        out = np.stack([np.interp(positions, np.arange(len(source)), source[:, channel]) for channel in range(2)], axis=1)
        self.phase = positions[-1] + self.rate - span
        self.last = block[-1].copy()
        return out


class Stage:
    """Stereo width (0 is mono, 1 as recorded, 2 twice as wide), balance (-1 left … 1 right), and
    the two sides changed over for headphones put on the wrong way round."""

    def __init__(self):
        self.width = 1.0
        self.balance = 0.0
        self.swap = False

    def process(self, block):
        if self.swap:
            block = block[:, ::-1]
        if abs(self.width - 1) < 1e-3 and abs(self.balance) < 1e-3:
            return block
        mid = (block[:, 0] + block[:, 1]) * 0.5
        side = (block[:, 0] - block[:, 1]) * 0.5 * self.width
        left = (mid + side) * min(1.0, 1 - self.balance)
        right = (mid - side) * min(1.0, 1 + self.balance)
        # A wider image is louder at the sides; it is brought back so it never only sounds louder.
        scale = 1 / (1 + max(0.0, self.width - 1) * 0.35)
        return np.stack([left, right], axis=1) * scale


class Crossfeed:
    """For headphones: each ear hears a little of the other side, later and darker, as from
    speakers in a room. Hard-panned old recordings stop tiring the ears."""

    def __init__(self, rate):
        self.on = False
        self.delay = max(1, int(0.0003 * rate))
        self.kernel = np.hanning(17) / np.hanning(17).sum()
        self.tail = np.zeros((len(self.kernel) - 1 + self.delay, 2))

    def process(self, block):
        if not self.on:
            return block
        frames = len(block)
        padded = np.concatenate([self.tail, block])
        self.tail = padded[-len(self.tail):]
        dark = np.stack([np.convolve(padded[:, channel], self.kernel, mode="valid")[:frames] for channel in range(2)], axis=1)
        crossed = dark[:, ::-1]
        return (block + crossed * 0.32) / 1.18


class Leveler:
    """Even loudness: quiet tracks a little up, loud ones a little down, slowly, so a playlist from
    different years plays at one level. Up to 9 dB either way; silence is left alone."""

    TARGET = 0.11

    def __init__(self):
        self.on = False
        self.gain = 1.0

    def process(self, block):
        if not self.on or not len(block):
            self.gain = 1.0
            return block
        rms = float(np.sqrt(np.mean(block ** 2))) + 1e-9
        wanted = self.gain if rms < 0.004 else min(2.8, max(0.35, self.TARGET / rms))
        # Down quickly when it gets loud, up slowly when it gets quiet.
        step = 0.3 if wanted < self.gain else 0.03
        new = self.gain + (wanted - self.gain) * step
        ramp = np.linspace(self.gain, new, len(block))
        self.gain = new
        return block * ramp[:, None]


class Voice:
    """Takes the singer out, the way karaoke machines do: whatever is the same in both ears between
    200 Hz and 7 kHz, where the voice stands in most mixes, is removed; the bass, the air and
    everything at the sides stay. Works on what was mixed in the middle, so a voice with wide
    reverb leaves a shadow. The sound comes 6 ms later while it is on."""

    TAPS = 511

    def __init__(self, rate):
        self.amount = 0.0
        index = np.arange(self.TAPS) - self.TAPS // 2
        def low(cut):
            return 2 * cut / rate * np.sinc(2 * cut / rate * index)
        self.kernel = (low(7000) - low(200)) * np.hamming(self.TAPS)
        self.delay = self.TAPS // 2
        self.tail = np.zeros((self.TAPS - 1, 2))

    def process(self, block):
        if self.amount <= 0:
            return block
        frames = len(block)
        padded = np.concatenate([self.tail, block])
        self.tail = padded[-(self.TAPS - 1):]
        voice = np.convolve(padded.mean(axis=1), self.kernel, mode="valid")
        start = self.TAPS - 1 - self.delay
        return padded[start:start + frames] - voice[:, None] * self.amount


class Drive:
    """The warmth of tape and valves: loud moments are rounded off softly, which thickens the sound
    with harmonics. The loudness is kept where it was, so more of it never just sounds louder."""

    def __init__(self):
        self.amount = 0.0
        self.made_for = None
        self.gain = self.makeup = 1.0

    def process(self, block):
        if self.amount <= 0:
            return block
        if self.made_for != self.amount:
            self.made_for = self.amount
            self.gain = 1 + 7 * self.amount
            probe = np.random.default_rng(3).standard_normal(4096) * 0.16
            self.makeup = float(np.sqrt(np.mean(probe ** 2) / np.mean(np.tanh(probe * self.gain) ** 2)))
        return np.tanh(block * self.gain) * self.makeup


class Crush:
    """Lo-fi: the sound as an old sampler or a cheap player gives it. Only every few samples are
    kept and held, and the steps of loudness get coarse."""

    def __init__(self):
        self.amount = 0.0
        self.phase = 0
        self.held = np.zeros(2)

    def process(self, block):
        if self.amount <= 0 or not len(block):
            self.phase = 0
            return block
        step = 1 + int(round(self.amount * 9))
        levels = 2 ** (14 - 9 * self.amount)
        frames = len(block)
        index = np.arange(frames) + self.phase
        # Where the sample each one repeats lies in this block; before its start, it is the one held over.
        source = index - index % step - self.phase
        out = np.where((source >= 0)[:, None], block[np.maximum(source, 0)], self.held)
        self.held = out[-1].copy()
        self.phase = (self.phase + frames) % step
        return np.round(out * levels) / levels


class Swirl:
    """A copy of the sound that runs a little late, by an amount that sways. Mixed with the sound
    it is a chorus (one voice becomes several); with a very short delay, a flanger (a jet passing
    overhead); and heard alone it is the wow of a worn cassette, the pitch drifting up and down."""

    def __init__(self, rate, base_ms, depth_ms, speed, wet=0.5, alone=False, flutter=0.0):
        self.rate = rate
        self.base = base_ms / 1000 * rate
        self.depth = depth_ms / 1000 * rate
        self.speed = speed
        self.wet = wet
        self.alone = alone
        self.flutter = flutter
        self.amount = 0.0
        self.phase = 0.0
        self.keep = int(self.base + self.depth * (1 + flutter)) + 4
        self.past = np.zeros((self.keep, 2))

    def process(self, block):
        if self.amount <= 0 or not len(block):
            return block
        frames = len(block)
        padded = np.concatenate([self.past, block])
        self.past = padded[-self.keep:]
        turn = 2 * math.pi * self.speed / self.rate
        t = self.phase + np.arange(frames) * turn
        self.phase = float(t[-1] + turn) % (2 * math.pi * 1000)
        places = np.arange(frames) + self.keep
        depth = self.depth * (self.amount if self.alone else 1.0)
        out = np.empty((frames, 2))
        for channel, ahead in ((0, 0.0), (1, math.pi / 2)):
            sway = np.sin(t + ahead)
            if self.flutter:
                sway = sway + self.flutter * np.sin(t * 9.7 + ahead)
            at = places - (self.base + depth * sway)
            lower = np.floor(at).astype(int)
            share = at - lower
            out[:, channel] = padded[lower, channel] * (1 - share) + padded[lower + 1, channel] * share
        if self.alone:
            return out
        mix = self.wet * self.amount
        return block * (1 - mix * 0.4) + out * mix


class Echo:
    """The sound comes back after a while, quieter each time, from the left and the right in turn."""

    def __init__(self, rate):
        self.rate = rate
        self.mix = 0.0
        self.time = 0.32
        self.feedback = 0.35
        self.line = None

    def process(self, block):
        if self.mix <= 0 or not len(block):
            self.line = None
            return block
        length = max(64, int(self.time * self.rate))
        if self.line is None:
            self.line = np.zeros((length, 2))
        elif len(self.line) > length:
            self.line = self.line[-length:]
        elif len(self.line) < length:
            self.line = np.concatenate([np.zeros((length - len(self.line), 2)), self.line])
        out = np.empty_like(block)
        done = 0
        while done < len(block):
            count = min(length, len(block) - done)
            piece = block[done:done + count]
            late = self.line[:count]
            out[done:done + count] = piece + late * self.mix
            # What goes round again: the middle of the sound into one ear, and what came back
            # crossing over to the other, so the echoes walk from side to side.
            fed = late[:, ::-1] * self.feedback
            fed[:, 0] += piece.mean(axis=1)
            self.line = np.concatenate([self.line[count:], fed])
            done += count
        return out


class Squeeze:
    """A compressor: loud moments are turned down and the whole is turned up after, so quiet
    details come forward and nothing jumps out. For listening at night or at low volume."""

    HOP = 64

    def __init__(self, rate):
        self.rate = rate
        self.amount = 0.0
        self.reduction = 0.0
        self.attack = 1 - math.exp(-self.HOP / (0.004 * rate))
        self.release = 1 - math.exp(-self.HOP / (0.18 * rate))

    def process(self, block):
        frames = len(block)
        if self.amount <= 0 or frames < self.HOP:
            self.reduction = 0.0
            return block
        threshold = -10 - 20 * self.amount
        slope = 1 - 1 / (2 + 4 * self.amount)
        hops = -(-frames // self.HOP)
        loud = np.zeros(hops * self.HOP)
        loud[:frames] = np.abs(block).max(axis=1)
        peaks = loud.reshape(hops, self.HOP).max(axis=1)
        wanted = np.maximum(0.0, 20 * np.log10(peaks + 1e-9) - threshold) * slope
        gains = np.empty(hops + 1)
        gains[0] = reduction = self.reduction
        for index in range(hops):
            reduction += (wanted[index] - reduction) * (self.attack if wanted[index] > reduction else self.release)
            gains[index + 1] = reduction
        self.reduction = float(reduction)
        makeup = -threshold * slope * 0.55
        decibels = makeup - np.interp(np.arange(frames), np.arange(hops + 1) * self.HOP, gains)
        return block * (10 ** (decibels / 20))[:, None]


class Tone:
    """The balance of a track between low and high, for the automatic equalizer: the power in
    bands a third of an octave wide, averaged over the last ten seconds or so of what played
    (before the effects)."""

    SIZE = 4096
    EDGES = np.geomspace(35, 16000, 28)

    def __init__(self, rate):
        self.rate = rate
        self.window = np.hanning(self.SIZE)
        frequencies = np.fft.rfftfreq(self.SIZE, 1 / rate)
        self.places = np.searchsorted(frequencies, self.EDGES)
        self.middles = np.sqrt(self.EDGES[:-1] * self.EDGES[1:])
        self.reset()

    def reset(self):
        self.pending = np.zeros(0)
        self.power = None
        self.heard = 0.0

    def feed(self, block):
        self.pending = np.concatenate([self.pending, block.mean(axis=1)])
        while len(self.pending) >= self.SIZE:
            piece, self.pending = self.pending[:self.SIZE], self.pending[self.SIZE:]
            if float(np.mean(piece ** 2)) < 1e-6:
                continue
            power = np.abs(np.fft.rfft(piece * self.window)) ** 2
            bands = np.array([power[start:max(start + 1, end)].sum() for start, end in zip(self.places[:-1], self.places[1:])])
            seconds = self.SIZE / self.rate
            share = max(seconds / 10, seconds / (self.heard + seconds))
            self.power = bands if self.power is None else self.power + (bands - self.power) * share
            self.heard += seconds

    # How loud each band is, in dB against the middle, in music that sounds balanced today:
    # (Hz, dB) measured over a few dozen finished tracks of different kinds. Strong below 100 Hz,
    # even through the middle, falling gently above 1 kHz and steeply above 10 kHz.
    USUAL = ((35, 8.5), (60, 6.5), (100, 4.0), (150, 2.3), (250, 2.2), (500, 3.0), (1000, 0.8), (2000, -1.3), (4000, -3.6),
             (9000, -4.3), (12000, -6.5), (16000, -11.0))

    def usual(self):
        places, levels = zip(*self.USUAL)
        return np.interp(np.log10(self.middles), np.log10(places), levels)

    def gains(self, count, strength=0.65, most=5.0):
        """The curve that brings what played closer to that balance, on count bands, or None when
        too little has played to tell."""
        if self.power is None or self.heard < 1.5:
            return None
        measured = 10 * np.log10(self.power + 1e-12)
        apart = measured - self.usual()
        middle = (self.middles >= 100) & (self.middles <= 8000)
        apart = apart - apart[middle].mean()
        # Narrow peaks belong to the song; only the broad shape is evened out.
        padded = np.concatenate([apart[:1], apart[:1], apart, apart[-1:], apart[-1:]])
        broad = np.convolve(padded, np.ones(5) / 5, mode="valid")
        fix = np.clip(-broad * strength, -most, most)
        fitted = np.interp(np.log10(centres(count)), np.log10(self.middles), fix)
        return [round(float(value) * 2) / 2 for value in fitted]


def spectrum(samples, rate, count=48):
    """Loudness of the sound in bands spread evenly in pitch from 30 Hz to 16 kHz, 0…1, for the
    analyser behind the equalizer."""
    if len(samples) < 256:
        return [0.0] * count
    window = np.hanning(len(samples))
    power = np.abs(np.fft.rfft(samples * window)) ** 2
    frequencies = np.fft.rfftfreq(len(samples), 1 / rate)
    edges = np.geomspace(30, 16000, count + 1)
    places = np.searchsorted(frequencies, edges)
    result = []
    for index in range(count):
        start, end = places[index], max(places[index] + 1, places[index + 1])
        level = float(power[start:end].mean()) if end <= len(power) else 0.0
        # Music is quieter the higher it goes; a tilt of 3 dB an octave shows it evenly, as analysers do.
        middle = math.sqrt(edges[index] * edges[index + 1])
        decibels = 10 * math.log10(level + 1e-12) + 3 * math.log2(middle / 1000)
        result.append(max(0.0, min(1.0, (decibels + 10) / 70)))
    return result


def limit(block, ceiling=0.95):
    """Keeps boosted bands and reverb from clipping: soft above the ceiling, never past 1."""
    magnitude = np.abs(block)
    over = magnitude > ceiling
    if over.any():
        soft = ceiling + (1 - ceiling) * np.tanh((magnitude[over] - ceiling) / (1 - ceiling))
        block = block.copy()
        block[over] = np.sign(block[over]) * soft
    return block


class Chain:
    """All effects with their settings; process() takes and gives float32 (frames, 2)."""

    def __init__(self, rate=44100, block=1024):
        self.rate = rate
        self.equalizer = Equalizer(rate)
        self.vinyl = Vinyl(rate)
        self.orbit = Orbit(rate)
        self.space = Space(rate, block)
        self.speed = Speed()
        self.stage = Stage()
        self.crossfeed = Crossfeed(rate)
        self.leveler = Leveler()
        self.voice = Voice(rate)
        self.drive = Drive()
        self.crush = Crush()
        self.wobble = Swirl(rate, 5.0, 1.6, 0.6, alone=True, flutter=0.12)
        self.chorus = Swirl(rate, 18.0, 5.0, 0.55, wet=0.5)
        self.flanger = Swirl(rate, 2.2, 1.8, 0.22, wet=0.7)
        self.echo = Echo(rate)
        self.squeeze = Squeeze(rate)
        self.enabled = True
        self.preamp = 1.0

    def configure(self, settings):
        def amount(name, default=0.0):
            try:
                return float(settings.get(name) or default)
            except (TypeError, ValueError):
                return default
        self.enabled = settings.get("enabled", True)
        gains = settings.get("bands") or [0] * len(BANDS)
        bass, treble = amount("bass"), amount("treble")
        self.equalizer.set_gains(gains, bass, treble, amount("low_cut"), amount("high_cut"))
        self.voice.amount = amount("voice")
        self.drive.amount = amount("drive")
        self.crush.amount = amount("crush")
        self.wobble.amount = amount("wobble")
        self.chorus.amount = amount("chorus")
        self.flanger.amount = amount("flanger")
        self.echo.mix = amount("echo")
        self.echo.time = min(1.2, max(0.05, amount("echo_time", 0.32)))
        self.echo.feedback = min(0.85, max(0.0, amount("echo_feedback", 0.35)))
        self.squeeze.amount = amount("compress")
        self.stage.swap = bool(settings.get("swap", False))
        # Boosts would clip; the whole sound is lowered by the largest boost, as players do, then
        # raised or lowered by the listener's own preamp.
        peak = float(np.max(self.equalizer.curve(np.geomspace(20, 20000, 200))))
        self.preamp = 10 ** (-max(0.0, peak) / 20 * 0.7) * 10 ** (float(settings.get("preamp", 0.0)) / 20)
        self.stage.width = float(settings.get("width", 1.0))
        self.stage.balance = float(settings.get("balance", 0.0))
        self.crossfeed.on = bool(settings.get("crossfeed", False))
        self.leveler.on = bool(settings.get("level", False))
        self.vinyl.amount = float(settings.get("vinyl", 0.0))
        self.orbit.on = bool(settings.get("orbit", False))
        self.orbit.speed = float(settings.get("orbit_speed", 0.12))
        self.space.set(settings.get("space"), float(settings.get("space_mix", 0.35)))

    def reset(self):
        """Forgets the tails after a seek, so the sound from before does not ring on."""
        self.equalizer.tail = None
        self.space.history = None
        self.space.previous = np.zeros_like(self.space.previous)
        self.voice.tail[:] = 0
        self.echo.line = None
        self.squeeze.reduction = 0.0
        for swirl in (self.wobble, self.chorus, self.flanger):
            swirl.past[:] = 0

    def process(self, block):
        block = self.speed.process(block.astype(np.float64))
        if not len(block):
            return block.astype(np.float32)
        block = self.equalizer.process(block * (self.preamp if self.enabled else 1.0))
        if self.enabled:
            block = self.voice.process(block)
            block = self.drive.process(block)
            block = self.crush.process(block)
            block = self.wobble.process(block)
            block = self.vinyl.process(block)
            block = self.chorus.process(block)
            block = self.flanger.process(block)
            block = self.echo.process(block)
            block = self.orbit.process(block)
            block = self.stage.process(block)
            block = self.crossfeed.process(block)
            block = self.space.process(block)
            block = self.squeeze.process(block)
            block = self.leveler.process(block)
        return limit(block).astype(np.float32)
