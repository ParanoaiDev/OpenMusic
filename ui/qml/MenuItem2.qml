import QtQuick
import QtQuick.Controls

MenuItem {
    id: item
    implicitHeight: 38
    leftPadding: 14
    rightPadding: 14
    contentItem: Text {
        text: item.text
        color: item.enabled ? "white" : Qt.rgba(1, 1, 1, 0.35)
        font.family: "Inter"
        font.pixelSize: 14
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    arrow: Text {
        x: item.width - width - 12
        anchors.verticalCenter: parent.verticalCenter
        visible: item.subMenu
        text: "›"
        color: Qt.rgba(1, 1, 1, 0.5)
        font.pixelSize: 18
    }
    background: Rectangle {
        radius: 9
        color: Qt.rgba(1, 1, 1, item.highlighted ? 0.1 : 0)
        Behavior on color { ColorAnimation { duration: 120 } }
    }
}
