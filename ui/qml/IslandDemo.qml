import QtQuick

// A small picture of the island on a screen, opening and closing by itself, so the setting shows
// what it does.
Rectangle {
    id: demo
    property bool running: false
    property bool open: false
    height: 150
    radius: 18
    clip: true
    readonly property color tint: app.playerMap.colour
    gradient: Gradient {
        GradientStop { position: 0; color: Qt.rgba(demo.tint.r * 0.45, demo.tint.g * 0.45, demo.tint.b * 0.45, 1) }
        GradientStop { position: 1; color: "#0c0c10" }
    }
    // Two windows of some other app under the island.
    Rectangle { x: parent.width * 0.08; y: 52; width: parent.width * 0.5; height: 120; radius: 10; color: Qt.rgba(1, 1, 1, 0.06); border.color: Qt.rgba(1, 1, 1, 0.07) }
    Rectangle { x: parent.width * 0.46; y: 72; width: parent.width * 0.44; height: 110; radius: 10; color: Qt.rgba(1, 1, 1, 0.08); border.color: Qt.rgba(1, 1, 1, 0.08) }
    Timer { interval: 2400; repeat: true; running: demo.running && demo.visible; onTriggered: demo.open = !demo.open }
    onRunningChanged: if (!running) open = false

    Rectangle {
        id: pill
        anchors.horizontalCenter: parent.horizontalCenter
        y: 8
        width: demo.open ? 250 : 112
        height: demo.open ? 104 : 22
        radius: demo.open ? 28 : 11
        color: "black"
        border.color: Qt.rgba(1, 1, 1, 0.1)
        Behavior on width { SpringAnimation { spring: 3.4; damping: 0.3; epsilon: 0.25 } }
        Behavior on height { SpringAnimation { spring: 3.4; damping: 0.32; epsilon: 0.25 } }
        Behavior on radius { NumberAnimation { duration: 340; easing.type: Easing.OutCubic } }
        clip: true
        Item {
            anchors.fill: parent
            opacity: demo.open ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: 160 } }
            Rectangle { x: 4; anchors.verticalCenter: parent.verticalCenter; width: 14; height: 14; radius: 7; color: demo.tint }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 9; anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Repeater { model: [6, 10, 7, 9]; Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 2; height: modelData; radius: 1; color: Qt.lighter(demo.tint, 1.6) } }
            }
        }
        Item {
            anchors.fill: parent
            opacity: demo.open ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: demo.open ? 300 : 100 } }
            Rectangle { x: 14; y: 14; width: 40; height: 40; radius: 10; color: demo.tint }
            Rectangle { x: 64; y: 20; width: 110; height: 8; radius: 4; color: Qt.rgba(1, 1, 1, 0.85) }
            Rectangle { x: 64; y: 36; width: 70; height: 7; radius: 3.5; color: Qt.rgba(1, 1, 1, 0.4) }
            Rectangle { x: 14; y: 66; width: parent.width - 28; height: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.15)
                        Rectangle { width: parent.width * 0.42; height: 4; radius: 2; color: "white" } }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter; y: 78
                spacing: 14
                Repeater { model: 3; Rectangle { width: index === 1 ? 18 : 12; height: width; radius: width / 2; anchors.verticalCenter: parent.verticalCenter
                                                 color: index === 1 ? "white" : Qt.rgba(1, 1, 1, 0.4) } }
            }
        }
    }
}
