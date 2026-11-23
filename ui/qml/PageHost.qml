import QtQuick

// One page of the window. The page that is chosen fades and rises in, the one left fades out;
// a page out of sight is not drawn at all, so its animations stop.
Item {
    id: host
    property int index
    readonly property bool current: app.stateMap.page === index
    default property alias content: holder.data
    anchors.fill: parent
    property real shown: current ? 1 : 0
    Behavior on shown { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }
    opacity: shown
    visible: shown > 0.001
    z: current ? 1 : 0
    Item {
        id: holder
        anchors.fill: parent
        transform: Translate { y: (1 - host.shown) * 26 }
    }
}
