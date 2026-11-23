import QtQuick
import QtQuick.Controls

// A panel over a dimmed window that comes in out of a short grow and fade.
Popup {
    id: sheet
    modal: true
    dim: true
    anchors.centerIn: Overlay.overlay
    padding: 28
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.62); Behavior on opacity { NumberAnimation { duration: 250 } } }
    background: Rectangle { radius: 24; color: "#111113"; border.color: Qt.rgba(1, 1, 1, 0.1) }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 220; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.94; to: 1; duration: 300; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; to: 0; duration: 160 }
            NumberAnimation { property: "scale"; to: 0.97; duration: 160 }
        }
    }
}
