import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import delete

from library import Library

ROOT = Path(__file__).resolve().parent


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("OpenMusic")
    app.setApplicationDisplayName("OpenMusic")
    app.setDesktopFileName("OpenMusic")
    app.setWindowIcon(QIcon(str(ROOT / "assets" / "icon.png")))
    # The island and the tray outlive the window when it hides; the app ends when the window closes.
    app.setQuitOnLastWindowClosed(False)
    QQuickStyle.setStyle("Basic")
    # Text drawn the way the system draws it: crisp at every size, where Qt Quick's own way blurs small text.
    QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)
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
    code = app.exec()
    # Left for interpreter shutdown, the scene crashes Qt on Wayland when PySide tears it down.
    delete(engine)
    return code


if __name__ == "__main__":
    sys.exit(main())
