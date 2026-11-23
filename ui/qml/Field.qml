import QtQuick
import QtQuick.Controls

// A text field: dark glass, rounded, the border lighting up when it has focus.
TextField {
    id: field
    property string glyph: ""
    property real round: 18
    implicitHeight: 42
    leftPadding: glyph ? 42 : 16
    rightPadding: 16
    color: "white"
    placeholderTextColor: Qt.rgba(1, 1, 1, 0.38)
    selectionColor: "#4a4a4a"
    selectedTextColor: "white"
    font.family: "Inter"
    font.pixelSize: 14
    background: Rectangle {
        radius: field.round
        color: Qt.rgba(1, 1, 1, field.activeFocus ? 0.09 : 0.06)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, field.activeFocus ? 0.4 : 0.12)
        Behavior on border.color { ColorAnimation { duration: 180 } }
        Behavior on color { ColorAnimation { duration: 180 } }
        Icon { visible: field.glyph !== ""; name: field.glyph; size: 17; opacity: 0.5; x: 15; anchors.verticalCenter: parent.verticalCenter }
    }
}
