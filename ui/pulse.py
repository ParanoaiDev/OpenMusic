"""How loud the music is right now, from the audio the player plays, for visuals that move with it.

Qt hands over each decoded buffer; a few hundred samples of it are enough for the loudness and
for a rough bass level (a smoothed copy of the signal). Values ease, so the visuals breathe
instead of flickering, and fall back to rest when the music stops."""
import array
import math

from PySide6.QtCore import QObject
from PySide6.QtMultimedia import QAudioBufferOutput, QAudioFormat


class Pulse(QObject):
    """Listens either to the player's decoded buffers itself, or, when the app's own audio engine
    plays the sound, to the blocks the engine passes on (take_block)."""

    def __init__(self, media, parent, engine=None):
        super().__init__(parent)
        self.level = 0.0
        self.bass = 0.0
        self.peak = 0.02
        self.low = 0.0
        if engine is not None and engine.available:
            engine.listeners.append(self.take_block)
        else:
            self.output = QAudioBufferOutput(self)
            media.setAudioBufferOutput(self.output)
            self.output.audioBufferReceived.connect(self.take)

    def take_block(self, block):
        mono = block[::4].mean(axis=1)
        if not len(mono):
            return
        rms = float((mono ** 2).mean() ** 0.5)
        low = self.low
        smooth = []
        for value in mono[::2]:
            low += (float(value) - low) * 0.15
            smooth.append(low)
        self.low = low
        bass = (sum(value * value for value in smooth) / max(1, len(smooth))) ** 0.5 * 3
        self.feed(rms, bass)

    def feed(self, rms, bass):
        self.peak = max(rms, self.peak * 0.995, 0.02)
        level = min(1.0, rms / self.peak)
        self.level += (level - self.level) * (0.5 if level > self.level else 0.12)
        bass = min(1.0, bass / self.peak)
        self.bass += (bass - self.bass) * (0.6 if bass > self.bass else 0.1)

    def take(self, buffer):
        sample_format = buffer.format().sampleFormat()
        data = bytes(buffer.constData())
        if sample_format == QAudioFormat.SampleFormat.Float:
            samples, scale = array.array("f"), 1.0
        elif sample_format == QAudioFormat.SampleFormat.Int16:
            samples, scale = array.array("h"), 1 / 32768
        elif sample_format == QAudioFormat.SampleFormat.Int32:
            samples, scale = array.array("i"), 1 / 2147483648
        else:
            return
        usable = len(data) - len(data) % samples.itemsize
        samples.frombytes(data[:usable])
        step = max(1, len(samples) // 600)
        picked = samples[::step]
        if not picked:
            return
        energy, bass_energy, low = 0.0, 0.0, self.low
        for value in picked:
            value *= scale
            energy += value * value
            low += (value - low) * 0.08
            bass_energy += low * low
        self.low = low
        rms = math.sqrt(energy / len(picked))
        bass = math.sqrt(bass_energy / len(picked)) * 3
        self.peak = max(rms, self.peak * 0.995, 0.02)
        level = min(1.0, rms / self.peak)
        self.level += (level - self.level) * (0.5 if level > self.level else 0.12)
        bass = min(1.0, bass / self.peak)
        self.bass += (bass - self.bass) * (0.6 if bass > self.bass else 0.1)

    def rest(self):
        """Eases toward silence; called by visuals each frame while nothing plays."""
        self.level *= 0.9
        self.bass *= 0.9
