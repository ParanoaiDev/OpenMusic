import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import delete

from library import Library

ROOT = Path(__file__).resolve().parent
VERSION = "0.9.0"


def fonts():
    """The interface is set in Inter, with one serif italic in the title of the home screen. The
    copies in assets/fonts make it look the same on a computer that has neither."""
    for path in sorted((ROOT / "assets" / "fonts").glob("*.tt[fc]")):
        QFontDatabase.addApplicationFont(str(path))
    if "C059" not in QFontDatabase.families():
        QFont.insertSubstitution("C059", "Liberation Serif")


def watched(path):
    """Writes what Qt and Python complain about into a file: a windowed build has no console to say
    it in, and the check of a build reads this file."""
    from PySide6.QtCore import qInstallMessageHandler
    import traceback
    log = open(path, "a", encoding="utf-8", buffering=1)

    def note(kind, context, text):
        log.write(f"{kind.name}: {text}\n")

    def failed(kind, error, trace):
        log.write("".join(traceback.format_exception(kind, error, trace)))
    qInstallMessageHandler(note)
    sys.excepthook = failed
    return log


def main():
    # A windowed build on Windows has no console: what would be printed goes nowhere instead of failing.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w"))
    if sys.platform == "win32":
        import ctypes
        try:                                    # its own button on the taskbar, with its own icon
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OpenMusic.OpenMusic")
        except (AttributeError, OSError):
            pass
    log = watched(os.environ["OPENMUSIC_LOG"]) if os.environ.get("OPENMUSIC_LOG") else None
    app = QApplication(sys.argv)
    app.setApplicationName("OpenMusic")
    app.setApplicationVersion(VERSION)
    app.setApplicationDisplayName("OpenMusic")
    app.setDesktopFileName("OpenMusic")
    app.setWindowIcon(QIcon(str(ROOT / "assets" / "icon.png")))
    # The island and the tray outlive the window when it hides; the app ends when the window closes.
    app.setQuitOnLastWindowClosed(False)
    QQuickStyle.setStyle("Basic")
    # Text drawn the way the system draws it: crisp at every size, where Qt Quick's own way blurs small text.
    QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)
    fonts()
    data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    # The app was called Music Open at first; its library moves to the new name once.
    earlier = data.parent / "Music Open"
    if earlier.is_dir() and not data.exists():
        earlier.rename(data)
    try:
        library = Library(data / "library.sqlite3")
    except (OSError, sqlite3.Error):
        QMessageBox.critical(None, "OpenMusic", "Не удалось открыть локальную медиатеку.")
        return 1
    from ui.shell import App
    state = App(library)
    engine = QQmlApplicationEngine()
    from ui.pictures import Pictures
    pictures = Pictures()
    engine.addImageProvider("art", pictures)
    context = engine.rootContext()
    context.setContextProperty("app", state)
    context.setContextProperty("home", state.home.bridge)
    context.setContextProperty("np", state.now.bridge)
    context.setContextProperty("island", state.island)
    context.setContextProperty("artist", state.artist)
    engine.load(QUrl.fromLocalFile(str(ROOT / "ui" / "qml" / "Shell.qml")))
    if not engine.rootObjects():
        return 1
    state.window = engine.rootObjects()[0]
    engine.load(QUrl.fromLocalFile(str(ROOT / "ui" / "qml" / "Island.qml")))
    if len(engine.rootObjects()) > 1:
        state.island.attach(engine.rootObjects()[1])
    shot = os.environ.get("OPENMUSIC_SMOKE")
    if shot:
        # The check of a build: the window is drawn, a picture of it is saved, and the app ends.
        state.playback.audio.setVolume(0.0)
        wanted = os.environ.get("OPENMUSIC_SMOKE_TRACK", "")        # "artist|title": also check that a track is found and plays

        def play():
            from library import Track
            artist, _, title = wanted.partition("|")
            state.playback.problem.connect(lambda message: log and log.write(f"SMOKE problem: {message}\n"))
            state.playback.play_tracks([Track(title, artist, "Spotify", "")], 0)

        def seen():
            saved = state.window.grabWindow().save(shot)
            if log:
                playback = state.playback
                log.write(f"SMOKE saved={saved} playing={playback.playing} loading={playback.loading} "
                          f"position={playback.media.position()} duration={playback.media.duration()}\n")
            app.exit(0 if saved else 3)
        if wanted:
            QTimer.singleShot(1500, play)
        QTimer.singleShot(int(os.environ.get("OPENMUSIC_SMOKE_MS", "7000")), seen)
    code = app.exec()
    if sys.platform == "win32":
        # On Windows taking the scene and the threads apart crashes the process on its way out (the
        # build check caught it). Everything is saved by now, so the process simply ends.
        if log:
            log.flush()
        os._exit(code)
    # Left for interpreter shutdown, the scene crashes Qt on Wayland when PySide tears it down.
    delete(engine)
    return code


if __name__ == "__main__":
    sys.exit(main())
