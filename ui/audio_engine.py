"""OpenMusic's own way to the speakers, so that the sound can be changed on the way.

The player only decodes: it hands every decoded block (QAudioBufferOutput, in real time) here, the
effects (effects.py) work on it, and a QAudioSink plays the result. The volume is applied here too.
The sink keeps a little sound ahead to ride out a busy moment of the window; how much that is,
latency_ms(), is what the screen subtracts so the lyrics match what is heard. Without numpy the
player falls back to Qt's own output, without effects."""
import json
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtMultimedia import QAudioBufferOutput, QAudioFormat, QAudioSink, QMediaDevices

try:
    import numpy as np
    import effects
except ImportError:
    np = None
    effects = None

# The player hands over sound exactly in real time, so the sink only ever holds what was kept back.
# This much is kept back before playing starts, so a busy moment of the window never empties it.
AHEAD_MS = 250


class Volume:
    """What the rest of the app knows as the audio output: a volume to read and set."""

    def __init__(self, engine):
        self.engine = engine

    def volume(self):
        return self.engine.gain

    def setVolume(self, value):
        self.engine.gain = max(0.0, min(1.0, float(value)))


class AudioEngine(QObject):
    def __init__(self, media, settings_path, pulse_target=None, parent=None):
        super().__init__(parent)
        self.media = media
        self.settings_path = Path(settings_path)
        self.gain = 0.75
        self.speed = 1.0
        self.sink = None
        self.device = None
        self.format = None
        self.pending = b""
        self.priming = True
        self.chain = effects.Chain() if effects else None
        # What the track sounds like before the effects, for the automatic equalizer.
        self.tone = effects.Tone(44100) if effects else None
        self.settings = self.load()
        if self.chain:
            self.chain.configure(self.settings)
        self.listeners = []
        # The last moment of sound, for the analyser while the sound panel is open.
        self.watching = False
        self.recent = None
        self.rate = 44100
        self.output = QAudioBufferOutput(self)
        media.setAudioBufferOutput(self.output)
        self.output.audioBufferReceived.connect(self.take)
        media.positionChanged.connect(self.jumped)
        media.playbackStateChanged.connect(self.state_changed)
        media.sourceChanged.connect(lambda _: self.restart())
        media.sourceChanged.connect(lambda _: self.tone and self.tone.reset())
        self.last_position = 0
        self.flusher = QTimer(self)
        self.flusher.setInterval(10)
        self.flusher.timeout.connect(self.flush)
        self.flusher.start()

    @property
    def available(self):
        return self.chain is not None

    # ---- settings ----

    def defaults(self):
        return dict(enabled=True, preset="Без изменений", bands=[0.0] * 10, space=None, space_mix=0.35,
                    orbit=False, orbit_speed=0.12, vinyl=0.0, preamp=0.0, bass=0.0, treble=0.0, width=1.0, balance=0.0,
                    crossfeed=False, level=False, custom={}, low_cut=0.0, high_cut=0.0, voice=0.0, drive=0.0, crush=0.0,
                    wobble=0.0, chorus=0.0, flanger=0.0, echo=0.0, echo_time=0.32, echo_feedback=0.35, compress=0.0,
                    swap=False)

    def load(self):
        settings = self.defaults()
        try:
            settings.update(json.loads(self.settings_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        return settings

    def set_speed(self, rate):
        """Faster or slower: the player decodes at that pace and the engine resamples to real time."""
        self.speed = rate
        self.media.setPlaybackRate(rate)
        if self.chain:
            self.chain.speed.rate = rate

    def update(self, **values):
        if "scene" not in values:
            values["scene"] = None
        self.settings.update(values)
        if self.chain:
            self.chain.configure(self.settings)
        try:
            self.settings_path.write_text(json.dumps(self.settings, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    # ---- sound ----

    def open_sink(self, rate, channels):
        if self.sink is not None:
            self.sink.stop()
        audio_format = QAudioFormat()
        audio_format.setSampleRate(rate)
        audio_format.setChannelCount(2)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Float)
        self.format = (rate, channels)
        self.sink = QAudioSink(QMediaDevices.defaultAudioOutput(), audio_format, self)
        self.sink.setBufferSize(int(rate * 2 * 4 * AHEAD_MS / 1000) * 3)
        self.device = self.sink.start()
        self.pending = b""
        self.priming = True

    def take(self, buffer):
        if not buffer.isValid() or np is None:
            return
        audio_format = buffer.format()
        rate, channels = audio_format.sampleRate(), audio_format.channelCount()
        kind = audio_format.sampleFormat()
        data = bytes(buffer.constData())
        if kind == QAudioFormat.SampleFormat.Float:
            samples = np.frombuffer(data, dtype=np.float32)
        elif kind == QAudioFormat.SampleFormat.Int16:
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768
        elif kind == QAudioFormat.SampleFormat.Int32:
            samples = np.frombuffer(data, dtype=np.int32).astype(np.float32) / 2147483648
        else:
            return
        frames = len(samples) // max(1, channels)
        block = samples[: frames * channels].reshape(frames, channels)
        if channels == 1:
            block = np.repeat(block, 2, axis=1)
        elif channels > 2:
            block = block[:, :2]
        if self.format != (rate, channels) or self.sink is None:
            if self.chain is None or self.chain.rate != rate:
                self.chain = effects.Chain(rate=rate, block=1024)
                self.chain.configure(self.settings)
                self.chain.speed.rate = self.speed
                self.tone = effects.Tone(rate)
            self.open_sink(rate, channels)
        self.tone.feed(block)
        processed = self.chain.process(block)
        if self.watching and len(processed):
            mono = processed.mean(axis=1)
            self.recent = mono[-16384:] if self.recent is None else np.concatenate([self.recent, mono])[-16384:]
            self.rate = rate
        for listener in self.listeners:
            listener(processed)
        self.pending += (processed * self.gain).astype(np.float32).tobytes()
        self.flush()

    def flush(self):
        if not self.pending or self.device is None or self.sink is None:
            return
        if self.priming:
            if len(self.pending) < self.format[0] * 8 * AHEAD_MS // 1000:
                return
            self.priming = False
        free = self.sink.bytesFree()
        if free <= 0:
            return
        chunk = self.pending[: free - free % 8]
        written = self.device.write(chunk)
        if written > 0:
            self.pending = self.pending[written:]
        # Never let more than half a second pile up: if the sink stalls, drop the oldest sound.
        if self.format and len(self.pending) > self.format[0] * 8 // 2:
            self.pending = self.pending[-(self.format[0] * 8 // 4):]

    def jumped(self, position):
        """A seek: the sound already queued belongs to the old place, and so do the effect tails."""
        if abs(position - self.last_position) > 1500 and self.sink is not None:
            self.restart()
        self.last_position = position

    def restart(self):
        """Drops what is queued (a seek or another track) and primes again."""
        self.pending = b""
        self.priming = True
        if self.chain:
            self.chain.reset()
        if self.sink is not None:
            self.sink.reset()
            self.device = self.sink.start()

    def state_changed(self, state):
        """Pausing silences the speakers at once and keeps what is queued for when it plays on."""
        if self.sink is None:
            return
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.sink.resume()
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.sink.suspend()
        else:
            self.restart()

    def spectrum(self, count=48):
        if not self.watching or self.recent is None or effects is None:
            return [0.0] * count
        # What is heard now left the effects a little earlier: it waited in the queue to the speakers.
        queued = 0
        if self.sink is not None:
            queued = (self.sink.bufferSize() - self.sink.bytesFree() + len(self.pending)) // 8
        end = max(2048, len(self.recent) - queued)
        return effects.spectrum(self.recent[end - 2048:end], self.rate, count)

    def auto_bands(self, count):
        """The equalizer curve that evens out the balance of the track that plays, or None when
        too little of it has played to tell."""
        return self.tone.gains(count) if self.tone else None

    def latency_ms(self):
        """How far behind the decoder the speakers are: what waits in the sink and in our queue."""
        if self.sink is None or not self.format:
            return 0
        queued = self.sink.bufferSize() - self.sink.bytesFree() + len(self.pending)
        # Queued sound is played at real time but stands for speed × as much of the track.
        return int(queued / (self.format[0] * 8) * 1000 * self.speed)
