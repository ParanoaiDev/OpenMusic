# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: OpenMusic as a folder with its own Python and Qt (dist/OpenMusic).
#   pyinstaller packaging/openmusic.spec --noconfirm
# The folder becomes an AppImage on Linux and an installer on Windows (.github/workflows/release.yml).
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [(os.path.join(ROOT, "ui", "qml"), "ui/qml"), (os.path.join(ROOT, "assets"), "assets")]
if os.path.isdir(os.path.join(ROOT, "bin")):          # ffmpeg and ffprobe put there by the build, when it carries them
    datas.append((os.path.join(ROOT, "bin"), "bin"))
icon = os.path.join(ROOT, "packaging", "windows", "icon.ico")

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=["yt_dlp", "numpy", "effects", "waveform", "mixes", "similar", "PySide6.QtDBus"],
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
              "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtQuick3D",
              "PySide6.QtPdf", "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtSensors", "PySide6.QtTest"],
    noarchive=False,
)
# Qt comes with everything it can do; what a music player never touches stays out of the download.
UNUSED = ("WebEngine", "Quick3D", "Qt3D", "Charts", "DataVisualization", "Graphs", "Pdf", "Location", "Positioning", "Sensors",
          "VirtualKeyboard", "RemoteObjects", "Scxml", "SerialPort", "SerialBus", "Bluetooth", "Nfc", "TextToSpeech", "Designer",
          "QtTest", "Qt6Test", "Qt6Help", "lupdate", "linguist", "assistant", "qmlls", "qmlformat", "qmllint")
def wanted(entry):
    name = entry[0].replace("\\", "/")
    return not any(word in name for word in UNUSED)
a.binaries = [entry for entry in a.binaries if wanted(entry)]
a.datas = [entry for entry in a.datas if wanted(entry)]

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="OpenMusic", console=False,
          icon=icon if sys.platform == "win32" and os.path.exists(icon) else None)
coll = COLLECT(exe, a.binaries, a.datas, name="OpenMusic")
