from pathlib import Path

from PySide6.QtGui import QColor, QPalette


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

INK = "#060606"
TEXT = "#f2f2f2"
MUTED = "#8e8e8e"
FAINT = "#5a5a5a"
WHITE = "#f4f4f4"

QSS = """
QWidget { color: @TEXT; font-family: "Inter", "Noto Sans", sans-serif; font-size: 10pt; }
QMainWindow, QDialog, QMessageBox { background: #0d0d0d; }
QToolTip { color: @TEXT; background: #161616; border: 1px solid rgba(255,255,255,30); border-radius: 6px; padding: 5px 8px; }
QScrollArea { background: transparent; border: none; }
QWidget#pageBody, QWidget#shelfBody { background: transparent; }

QLabel#pageTitle { font-family: "Inter Display", "Inter"; font-size: 27pt; font-weight: 800; }
QLabel#sectionTitle { font-family: "Inter Display", "Inter"; font-size: 15pt; font-weight: 700; }
QLabel#sheetTitle { font-family: "Inter Display", "Inter"; font-size: 19pt; font-weight: 800; }
QLabel#heroName { font-family: "Inter Display", "Inter"; font-size: 42pt; font-weight: 900; }
QLabel#statNumber { font-family: "Inter Display", "Inter"; font-size: 24pt; font-weight: 800; }
QLabel#emptyTitle { font-family: "Inter Display", "Inter"; font-size: 24pt; font-weight: 800; }
QLabel#overline { color: @MUTED; font-size: 8pt; font-weight: 700; }
QLabel#muted { color: @MUTED; }
QLabel#faint { color: @FAINT; font-size: 9pt; }
QLabel#tileTitle { font-weight: 600; }
QLabel#tileCaption { color: @MUTED; font-size: 9pt; }
QLabel#serviceName { font-weight: 650; font-size: 10.5pt; }
QLabel#stepNumber { color: @TEXT; background: rgba(255,255,255,20); border-radius: 12px; font-weight: 700; font-size: 9pt; }
QLabel#serviceTile { background: rgba(255,255,255,14); border: 1px solid rgba(255,255,255,24); border-radius: 13px; }
QLabel#toast { background: @WHITE; color: #0a0a0a; border-radius: 16px; padding: 8px 20px; font-weight: 600; }
QLabel#toast[error="true"] { background: #1b1b1b; color: @TEXT; border: 1px solid rgba(255,255,255,70); }

QPushButton {
  color: @TEXT; background: rgba(255,255,255,14); border: 1px solid rgba(255,255,255,24);
  border-radius: 18px; padding: 0 18px; min-height: 34px; font-weight: 600;
}
QPushButton:hover { background: rgba(255,255,255,26); }
QPushButton:pressed { background: rgba(255,255,255,38); }
QPushButton:focus { border-color: rgba(255,255,255,130); }
QPushButton:disabled { color: @FAINT; background: rgba(255,255,255,8); }
QPushButton::menu-indicator { image: none; width: 0; }
QPushButton#primary { background: @WHITE; color: #0a0a0a; border: 2px solid @WHITE; }
QPushButton#primary:hover { background: #ffffff; border-color: #ffffff; }
QPushButton#primary:pressed { background: #cfcfcf; border-color: #cfcfcf; }
QPushButton#primary:focus { border-color: #8a8a8a; }
QPushButton#primary:disabled { background: rgba(255,255,255,34); border-color: transparent; color: rgba(255,255,255,90); }
QPushButton#text { background: transparent; border: 1px solid transparent; color: @MUTED; padding: 0 10px; }
QPushButton#text:hover { color: @TEXT; }
QPushButton#chip {
  background: transparent; color: @MUTED; border: 1px solid rgba(255,255,255,26);
  border-radius: 15px; min-height: 28px; padding: 0 14px; font-weight: 500;
}
QPushButton#chip:hover { color: @TEXT; border-color: rgba(255,255,255,70); }
QPushButton#chip:checked { background: @WHITE; color: #0a0a0a; border-color: @WHITE; font-weight: 600; }
QPushButton#play { background: @WHITE; border: 2px solid @WHITE; border-radius: 21px; padding: 0; min-height: 0; }
QPushButton#play:hover { background: #ffffff; }
QPushButton#play:pressed { background: #cfcfcf; }
QPushButton#play:focus { border-color: #8a8a8a; }
QPushButton#play:disabled { background: rgba(255,255,255,26); border-color: transparent; }

QToolButton { background: transparent; border: none; border-radius: 17px; }
QToolButton:hover { background: rgba(255,255,255,18); }
QToolButton:pressed { background: rgba(255,255,255,30); }
QToolButton:focus { border: 1px solid rgba(255,255,255,110); }
QToolButton::menu-indicator { image: none; width: 0; }
QToolButton#rail { border-radius: 15px; }
QToolButton#rail:checked { background: transparent; }
QToolButton#rail:checked:hover { background: rgba(255,255,255,10); }
QToolButton#railAdd { background: @WHITE; border-radius: 24px; }
QToolButton#railAdd:hover { background: #ffffff; }
QToolButton#railAdd:pressed { background: #cfcfcf; }

QLineEdit {
  background: rgba(255,255,255,12); border: 1px solid rgba(255,255,255,22); border-radius: 18px;
  padding: 0 14px; min-height: 34px; selection-background-color: #4a4a4a;
}
QLineEdit:focus { border-color: rgba(255,255,255,100); background: rgba(255,255,255,16); }
QLineEdit#field { border-radius: 12px; min-height: 44px; font-size: 10.5pt; }

QFrame#rail { background: rgba(255,255,255,5); border-right: 1px solid rgba(255,255,255,13); }
QFrame#playerBar { background: rgba(9,9,9,238); border-top: 1px solid rgba(255,255,255,15); }
QFrame#sheet { background: #101010; border: 1px solid rgba(255,255,255,28); border-radius: 22px; }
QFrame#step { background: rgba(255,255,255,6); border-radius: 12px; }

QTableView { background: transparent; border: none; outline: none; selection-background-color: transparent; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section {
  background: transparent; color: @FAINT; border: none; border-bottom: 1px solid rgba(255,255,255,14);
  padding: 0 12px 8px 12px; font-size: 8.5pt; font-weight: 600;
}
QTableCornerButton::section { background: transparent; border: none; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,36); border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,80); }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0 2px; }
QScrollBar::handle:horizontal { background: rgba(255,255,255,22); border-radius: 3px; min-width: 40px; }
QScrollBar::handle:horizontal:hover { background: rgba(255,255,255,60); }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QMenu { background: #151515; border: 1px solid rgba(255,255,255,28); border-radius: 12px; padding: 6px; }
QMenu::item { padding: 8px 24px 8px 14px; border-radius: 7px; }
QMenu::item:selected { background: rgba(255,255,255,22); }
QMenu::item:disabled { color: @FAINT; }
QMenu::separator { height: 1px; background: rgba(255,255,255,18); margin: 5px 8px; }

QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,40); border-radius: 2px; }
QSlider::sub-page:horizontal { background: @WHITE; border-radius: 2px; }
QSlider::sub-page:horizontal:disabled { background: rgba(255,255,255,40); }
QSlider::handle:horizontal { width: 12px; margin: -4px 0; border-radius: 6px; background: @WHITE; }
QSlider::handle:horizontal:hover { background: #ffffff; }
QSlider::handle:horizontal:disabled { background: transparent; }
"""


def apply_theme(app):
    app.setStyle("Fusion")
    palette = app.palette()
    for role, color in {
        QPalette.ColorRole.Window: "#0d0d0d",
        QPalette.ColorRole.Base: "#111111",
        QPalette.ColorRole.AlternateBase: "#151515",
        QPalette.ColorRole.Button: "#1b1b1b",
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: "#3d3d3d",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: FAINT,
        QPalette.ColorRole.ToolTipBase: "#161616",
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.Link: TEXT,
    }.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    sheet = QSS
    for name, value in (("@TEXT", TEXT), ("@MUTED", MUTED), ("@FAINT", FAINT), ("@WHITE", WHITE)):
        sheet = sheet.replace(name, value)
    app.setStyleSheet(sheet)
