import QtQuick
import QtQuick.Controls

// The queue slides in from the right: what plays now and what comes after it.
Drawer {
    id: drawer
    edge: Qt.RightEdge
    width: 460
    height: parent.height
    dim: true
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.4) }
    background: Rectangle { color: "#101012"; Rectangle { width: 1; height: parent.height; color: Qt.rgba(1, 1, 1, 0.08) } }
    Column {
        id: head
        x: 24; y: 24
        width: parent.width - 48
        spacing: 4
        Item {
            width: parent.width; height: 40
            Text { text: "Очередь"; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 28 }
            IconButton { anchors.right: parent.right; name: "close"; onClicked: drawer.close() }
        }
        Text { text: app.stateMap.queueCaption; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 13 }
    }
    TrackList {
        id: list
        x: 12
        y: head.y + head.height + 14
        width: parent.width - 18
        height: parent.height - y - 12
        list: "queue"
        compact: true
        model: app.queueModel
    }
    onOpened: list.view.positionViewAtIndex(Math.max(0, app.playerMap.queueIndex - 1), ListView.Beginning)
}
