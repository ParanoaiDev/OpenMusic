"""The island: a small black shape at the top of the screen, like the island of a phone. It shows
the cover and the beat of what plays, opens into a small player under the pointer, and opens on
its own for a moment when a new track starts. ui/qml/Island.qml draws it.

On KDE and other Wayland desktops a window can't place itself, so the island is a layer surface
(layer-shell-qt, the library KDE's own panels use): the desktop keeps it at the top edge and out
of the taskbar. It lives on the desktop: on the layer just above the wallpaper, so the windows of
other apps cover it and it never sits on top of what the listener works in. The setting
islandOverWindows lifts it to the layer over the windows instead. The library has no Python
binding; its one entry point is called through ctypes, and the rest are Qt properties of the
object it returns. On X11 the island is an ordinary frameless window kept below or above the rest."""
import ctypes

from PySide6.QtCore import Property, QMargins, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication, QRegion
from shiboken6 import getCppPointer, isValid, wrapInstance

# The window the island draws in; outside the island's shape the pointer passes through it.
WIDTH, HEIGHT = 640, 300
GAP = 6
# Layers of the layer-shell protocol: "bottom" is above the wallpaper and under every window,
# "top" is over the windows but under full-screen ones.
ON_DESKTOP, OVER_WINDOWS = 1, 2


def layer_shell(window):
    """Makes a window, not yet shown, a layer surface centred at the top edge. None when the
    library is missing."""
    try:
        library = ctypes.CDLL("libLayerShellQtInterface.so.6")
        get = library._ZN12LayerShellQt6Window3getEP7QWindow
    except (OSError, AttributeError):
        return None
    get.restype = ctypes.c_void_p
    get.argtypes = [ctypes.c_void_p]
    pointer = get(getCppPointer(window)[0])
    if not pointer:
        return None
    layer = wrapInstance(pointer, QObject)
    # Anchored to the top edge alone it is centred along it; it never takes the keyboard, keeps no
    # room for itself and stays below a panel at the top of the screen. Island.place() sets the layer.
    for name, value in (("scope", "openmusic-island"), ("layer", ON_DESKTOP), ("anchors", 1), ("keyboardInteractivity", 0),
                        ("exclusionZone", 0), ("margins", QMargins(0, 0, 0, 0))):
        layer.setProperty(name, value)
    return layer


class Island(QObject):
    levelChanged = Signal()

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.window = None
        self.layer = None
        self.placed = None
        self.available = True
        self.loud = 0.0
        # The beat of the music, 30 times a second while the island shows and something plays.
        self.ticker = QTimer(self)
        self.ticker.setInterval(33)
        self.ticker.timeout.connect(self.tick)

    level = Property(float, lambda self: self.loud, notify=levelChanged)

    def attach(self, window):
        self.window = window
        if QGuiApplication.platformName().startswith("wayland"):
            self.layer = layer_shell(window)
            self.available = self.layer is not None
            self.place()
        else:
            self.place()
            screen = window.screen().geometry()
            window.setPosition(screen.x() + (screen.width() - WIDTH) // 2, screen.y())
        # Until the island says its shape, only a small pill at the top takes the pointer.
        window.setMask(QRegion((WIDTH - 200) // 2, 0, 200, 36 + GAP))
        self.sync()

    def place(self):
        """Puts the island on the desktop, under the windows, or over them, as the setting says."""
        over = bool(self.app.settings["islandOverWindows"])
        if self.layer is not None:
            # The property can be set from Python but not read back (its type has no converter).
            layer = OVER_WINDOWS if over else ON_DESKTOP
            if layer != self.placed:
                self.placed = layer
                self.layer.setProperty("layer", layer)
        elif not QGuiApplication.platformName().startswith("wayland"):
            flags = self.window.flags() & ~(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowStaysOnBottomHint)
            flags |= Qt.WindowType.WindowStaysOnTopHint if over else Qt.WindowType.WindowStaysOnBottomHint
            if flags != self.window.flags():
                self.window.setFlags(flags)

    def wanted(self):
        return bool(self.window and self.available and self.app.settings["island"])

    def sync(self):
        if not self.window or not isValid(self.window):
            return
        wanted = self.wanted()
        self.place()
        if wanted != self.window.isVisible():
            self.window.setVisible(wanted)
        if wanted and self.app.playback.playing:
            self.ticker.isActive() or self.ticker.start()
        else:
            self.ticker.stop()
            if self.loud:
                self.loud = 0.0
                self.levelChanged.emit()

    def tick(self):
        level = round(self.app.pulse.level, 3)
        if level != self.loud:
            self.loud = level
            self.levelChanged.emit()

    @Slot(int, int, int, int)
    def shape(self, x, y, width, height):
        """The part of the window that takes the pointer: the island as it is, or will be."""
        if self.window:
            self.window.setMask(QRegion(x, y, width, height))

    @Slot()
    def openApp(self):
        self.app.showWindow(3)
