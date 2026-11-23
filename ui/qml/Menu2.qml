import QtQuick
import QtQuick.Controls

// A menu in the look of the app: dark glass, rounded, opening with a short grow and fade.
Menu {
    id: menu
    padding: 6
    implicitWidth: 280
    delegate: MenuItem2 { }
    background: Rectangle {
        implicitWidth: 280
        radius: 14
        color: "#18181b"
        border.color: Qt.rgba(1, 1, 1, 0.1)
    }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.94; to: 1; duration: 190; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: 110 } }
}
