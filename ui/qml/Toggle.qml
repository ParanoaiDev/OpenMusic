import QtQuick

// A switch: the knob runs to the other side on a spring and the track fills with light.
Item {
    id: toggle
    property bool checked: false
    property bool enabled2: true
    property bool hot: false                // the pointer is on the row this switch belongs to
    width: 46
    height: 28
    opacity: enabled2 ? 1 : 0.35
    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: toggle.checked ? "#f4f4f4" : Qt.rgba(1, 1, 1, toggle.hot ? 0.2 : 0.13)
        Behavior on color { ColorAnimation { duration: 220 } }
    }
    Rectangle {
        y: 3
        width: 22
        height: 22
        radius: 11
        x: toggle.checked ? toggle.width - width - 3 : 3
        color: toggle.checked ? "#0a0a0a" : "#e9e9e9"
        Behavior on x { SpringAnimation { spring: 5; damping: 0.4; epsilon: 0.1 } }
        Behavior on color { ColorAnimation { duration: 220 } }
    }
}
