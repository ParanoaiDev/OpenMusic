import QtQuick

// A small label over a button after the pointer rests on it.
Rectangle {
    id: tip
    property alias text: label.text
    property bool shown: false
    property bool ready: false
    z: 1000
    visible: opacity > 0.01
    opacity: ready ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 140 } }
    width: label.implicitWidth + 18
    height: 28
    radius: 8
    color: "#1c1c1e"
    border.color: Qt.rgba(1, 1, 1, 0.12)
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.top
    anchors.bottomMargin: 8
    onShownChanged: shown ? delay.restart() : (delay.stop(), ready = false)
    Timer { id: delay; interval: 550; onTriggered: tip.ready = true }
    Text { id: label; anchors.centerIn: parent; color: "white"; font.family: "Inter"; font.pixelSize: 12 }
}
