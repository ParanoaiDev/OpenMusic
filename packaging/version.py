"""Prints the version of the app, for the build scripts."""
import re
from pathlib import Path

print(re.search(r'VERSION = "(.+?)"', (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8"))[1])
