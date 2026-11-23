"""Listing the entries of a playlist page with yt-dlp. Nothing is downloaded."""
import json
import shutil
import subprocess
import sys
import tempfile
from importlib.util import find_spec

from library import ImportFailed


class Refused(Exception):
    """yt-dlp gave up. The text is what it printed, for the caller to word for the user."""


def listing(link, fields, cancelled, purpose):
    """One dict per entry of the page at `link`, holding the fields asked for. `purpose` says, in the
    message shown when yt-dlp is missing, what it is needed for."""
    program = shutil.which("yt-dlp")
    if program:
        command = [program]
    elif find_spec("yt_dlp"):
        command = [sys.executable, "-m", "yt_dlp"]
    else:
        raise ImportFailed(f"Для {purpose} нужна программа yt-dlp. Установите её и повторите импорт.")
    command += ["--ignore-config", "--no-warnings", "--flat-playlist", "--socket-timeout", "15",
                "--print", "%(.{" + ",".join(fields) + "})j", "--", link]
    # Output goes to files so that waiting can watch for cancellation instead of blocking on a pipe.
    with tempfile.TemporaryFile() as printed, tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(command, stdout=printed, stderr=errors, stdin=subprocess.DEVNULL)
        except OSError as error:
            raise ImportFailed("Не удалось запустить yt-dlp.") from error
        with process:
            while True:
                try:
                    process.wait(0.1)
                    break
                except subprocess.TimeoutExpired:
                    if cancelled():
                        process.kill()
                        raise ImportFailed("Импорт отменён.")
        if process.returncode:
            errors.seek(0)
            raise Refused(errors.read().decode("utf-8", "replace"))
        printed.seek(0)
        lines = printed.read().decode("utf-8", "replace").splitlines()
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows
