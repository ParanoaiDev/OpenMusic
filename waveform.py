"""The shape of a track's sound for the scrubber: the loudness of a few hundred stretches of a
downloaded track, decoded by ffmpeg. Kept as a small file next to the audio. No Qt here."""
import array
import json
import math
import shutil
import subprocess
from pathlib import Path


def peaks(path, count=220, store=None):
    """0..1 loudness of `count` equal stretches of an audio file, or None when it cannot be read.
    The result is kept next to the file, or in `store` (a folder) for files that are not ours."""
    path = Path(path)
    if store:
        import hashlib
        Path(store).mkdir(parents=True, exist_ok=True)
        stored = Path(store) / (hashlib.blake2b(str(path).encode("utf-8"), digest_size=12).hexdigest() + ".peaks.json")
    else:
        stored = path.with_suffix(".peaks.json")
    if stored.exists():
        try:
            values = json.loads(stored.read_text())
            if len(values) == count:
                return values
        except (OSError, ValueError):
            pass
    program = shutil.which("ffmpeg")
    if not program or not path.exists():
        return None
    try:
        raw = subprocess.run([program, "-v", "error", "-i", str(path), "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                             capture_output=True, timeout=60, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        import numpy as np
        data = np.frombuffer(raw[: len(raw) - len(raw) % 2], dtype=np.int16).astype(np.float32)
        if not len(data):
            return None
        size = max(1, len(data) // count)
        data = data[: size * count].reshape(count, size) if len(data) >= size * count else np.resize(data, (count, size))
        values = list(np.sqrt((data ** 2).mean(axis=1)).astype(float))
    except ImportError:
        samples = array.array("h")
        samples.frombytes(raw[: len(raw) - len(raw) % 2])
        if not samples:
            return None
        size = max(1, len(samples) // count)
        values = []
        for index in range(count):
            chunk = samples[index * size:(index + 1) * size]
            values.append(math.sqrt(sum(value * value for value in chunk[::4]) / max(1, len(chunk[::4]))) if chunk else 0.0)
    top = max(values) or 1.0
    # Plain floats: numpy's would reach the screen as opaque objects and draw nothing.
    values = [round(float(min(1.0, value / top)) ** 0.8, 3) for value in values]
    try:
        stored.write_text(json.dumps(values))
    except OSError:
        pass
    return values
