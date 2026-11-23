"""Pictures as the Qt Quick screens take them: file addresses of covers, artist photos and icons,
with drawn stand-ins saved once into the cache folder."""
import hashlib
from pathlib import Path

from PySide6.QtCore import QUrl

from . import covers
from .art import avatar, cover as drawn, initial, logo_mark

CACHE = Path(".")


def setup(folder):
    global CACHE
    CACHE = Path(folder) / "cache"
    CACHE.mkdir(parents=True, exist_ok=True)


def local(path):
    return QUrl.fromLocalFile(str(path)).toString()


def digest(text):
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def cover(track):
    store = covers.STORE
    if store:
        path = store.store.path(track.artist, track.title)
        if path.exists():
            return local(path)
    path = CACHE / f"drawn-{digest(covers.seed(track))}.png"
    if not path.exists():
        drawn(covers.seed(track), 200).save(str(path))
    return local(path)


def artist(name):
    store = covers.STORE
    if store:
        path = store.store.artist_path(name)
        if path.exists():
            return local(path)
    path = CACHE / f"avatar-{digest(name)}.png"
    if not path.exists():
        avatar(name, 200, initial(name)).save(str(path))
    return local(path)


def colour(track):
    return covers.STORE.colour(track).name() if covers.STORE else "#a0a0a0"


def icon(name, tint="#ffffff"):
    path = CACHE / f"icon-{name}-{tint.lstrip('#')}.png"
    if not path.exists():
        from .icons import pixmap
        pixmap(name, 48, tint).save(str(path))
    return local(path)


def logo(size=96):
    path = CACHE / ("logo-mark.png" if size == 96 else f"logo-mark-{size}.png")
    if not path.exists():
        logo_mark(size).save(str(path))
    return local(path)
