"""The icon in the system tray: a click shows or hides the window, its menu plays, pauses, skips
and turns the island on and off. With "close to tray" the window's cross only hides the window."""
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class Tray(QObject):
    def __init__(self, app, icon_path):
        super().__init__(app)
        self.app = app
        self.icon_path = str(icon_path)
        self.icon = None
        self.menu = None
        self.told = False

    @property
    def shown(self):
        return self.icon is not None and self.icon.isVisible()

    def sync(self):
        wanted = self.app.settings["tray"] and QSystemTrayIcon.isSystemTrayAvailable()
        if wanted and self.icon is None:
            self.build()
        elif not wanted and self.icon is not None:
            self.icon.hide()
            self.icon.deleteLater()
            self.menu.deleteLater()
            self.icon = self.menu = None
        if self.icon is not None:
            self.refresh()

    def build(self):
        self.icon = QSystemTrayIcon(QIcon(self.icon_path), self)
        self.menu = QMenu()
        self.now = self.menu.addAction("")
        self.now.setEnabled(False)
        self.menu.addSeparator()
        self.play = self.menu.addAction("Играть", self.app.toggle)
        self.menu.addAction("Следующий", self.app.next)
        self.menu.addAction("Предыдущий", self.app.previous)
        self.menu.addSeparator()
        self.island = QAction("Остров сверху экрана", self.menu)
        self.island.setCheckable(True)
        self.island.toggled.connect(lambda on: self.app.setSetting("island", on))
        self.menu.addAction(self.island)
        self.menu.addAction("Показать OpenMusic", lambda: self.app.showWindow(-1))
        self.menu.addSeparator()
        self.menu.addAction("Выйти", self.app.quitApp)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self.activated)
        self.icon.show()

    def activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.app.toggleWindow()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.app.toggle()

    def refresh(self):
        player = self.app.player
        text = f"{player['title']} — {player['artist']}" if player["hasTrack"] and player.get("artist") else player["title"]
        self.now.setText(text if len(text) <= 60 else text[:57] + "…")
        self.icon.setToolTip(f"OpenMusic\n{text}" if player["hasTrack"] else "OpenMusic")
        self.play.setText("Пауза" if player["playing"] or player["loading"] else "Играть")
        self.island.blockSignals(True)
        self.island.setChecked(self.app.settings["island"])
        self.island.setEnabled(self.app.island.available)
        self.island.blockSignals(False)

    def tell_hidden(self):
        """Says once where the window went when the cross hid it."""
        if self.icon is not None and not self.told:
            self.told = True
            self.icon.showMessage("OpenMusic играет дальше", "Окно спрятано в трей. Выйти можно из меню значка.",
                                  QIcon(self.icon_path), 4000)
