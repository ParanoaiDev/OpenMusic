"""Listing the entries of a playlist page with yt-dlp. Nothing is downloaded."""
import json
import shutil
import subprocess
import sys
import tempfile
from importlib.util import find_spec

import tools
from library import ImportFailed


class Refused(Exception):
    """yt-dlp gave up. The text is what it printed, for the caller to word for the user."""


def listing(link, fields, cancelled, purpose):
    """One dict per entry of the page at `link`, holding the fields asked for. `purpose` says, in the
    message shown when yt-dlp is missing, what it is needed for."""
    if tools.FROZEN:
        return inside(link, fields, cancelled)
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
            process = subprocess.Popen(command, stdout=printed, stderr=errors, stdin=subprocess.DEVNULL, **tools.QUIET)
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


def inside(link, fields, cancelled):
    """The same listing made by yt-dlp inside this process: a build of the app has no Python to start
    it with. The work goes on a thread, so that waiting can watch for cancellation."""
    import threading
    import yt_dlp
    result = {}

    def work():
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True,
                                   "socket_timeout": 15, "ignoreconfig": True}) as session:
                result["info"] = session.extract_info(link, download=False) or {}
        except Exception as error:
            result["error"] = str(error)
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    while thread.is_alive():
        thread.join(0.1)
        if cancelled():
            raise ImportFailed("Импорт отменён.")
    if "error" in result:
        raise Refused(result["error"])
    info = result.get("info") or {}
    entries = info.get("entries")
    entries = [entry for entry in entries if isinstance(entry, dict)] if entries is not None else [info]
    # What the command line prints for each entry also carries the name of the playlist it is in.
    whole = {"playlist_title": info.get("title"), "playlist": info.get("title"), "playlist_id": info.get("id")}
    return [{field: entry.get(field, whole.get(field)) for field in fields if entry.get(field, whole.get(field)) is not None}
            for entry in entries]
