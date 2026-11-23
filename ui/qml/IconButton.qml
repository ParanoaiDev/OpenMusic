import QtQuick

// A round button with an icon that lights up under the pointer and sinks when pressed.
Item {
    id: button
    property string name
    property real size: 38
    property real glyph: 19
    property bool active: false
    property bool enabled2: true
    property string tip: ""
    signal clicked()
    width: size
    height: size
    opacity: enabled2 ? 1 : 0.35
    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Qt.rgba(1, 1, 1, area.pressed ? 0.2 : area.containsMouse ? 0.11 : 0)
        Behavior on color { ColorAnimation { duration: 160 } }
        scale: area.pressed ? 0.92 : 1
        Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    }
    Icon {
        anchors.centerIn: parent
        name: button.name
        size: button.glyph
        opacity: button.active ? 1 : area.containsMouse ? 0.95 : 0.62
        Behavior on opacity { NumberAnimation { duration: 160 } }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        enabled: button.enabled2
        onClicked: button.clicked()
    }
    ToolTipText { text: button.tip; shown: area.containsMouse && button.tip !== "" }
}
