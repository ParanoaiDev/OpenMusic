"""Outside programs the app runs (ffmpeg, ffprobe, yt-dlp): where they are, and how to start them
quietly. A build of the app may carry its own copies in a "bin" folder next to the code; on Windows
a console program started from a windowed app would flash a black window without the flag here."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Passed to subprocess.run and Popen: nothing on Linux, "no console window" on Windows.
QUIET = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
FROZEN = bool(getattr(sys, "frozen", False))


def program(name):
    """The path of a program: the copy that comes with the app if there is one, else the system's."""
    own = ROOT / "bin" / (name + (".exe" if sys.platform == "win32" else ""))
    return str(own) if own.is_file() else shutil.which(name)
