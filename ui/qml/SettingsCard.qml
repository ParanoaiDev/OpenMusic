import QtQuick

// A group of settings on a soft card. Cards come in one after another when the page opens.
Rectangle {
    id: card
    property string title
    property string note: ""
    property int order: 0
    property bool active: false
    default property alias content: body.data
    width: parent ? parent.width : 400
    height: body.y + body.implicitHeight + 22
    radius: 24
    color: Qt.rgba(1, 1, 1, 0.035)
    border.color: Qt.rgba(1, 1, 1, 0.06)
    property real rise: 0
    opacity: rise
    transform: Translate { y: (1 - card.rise) * 22 }
    onActiveChanged: if (active) { rise = 0; enter.restart() }
    Component.onCompleted: if (active) enter.restart()
    SequentialAnimation {
        id: enter
        PauseAnimation { duration: card.order * 70 }
        NumberAnimation { target: card; property: "rise"; to: 1; duration: 560; easing.type: Easing.OutCubic }
    }
    Text {
        id: heading
        x: 26; y: 22
        text: card.title
        color: "white"
        font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 20
    }
    Text {
        anchors.left: heading.right; anchors.leftMargin: 12; anchors.baseline: heading.baseline
        width: card.width - x - 26
        elide: Text.ElideRight
        text: card.note
        color: Qt.rgba(1, 1, 1, 0.42)
        font.family: "Inter"; font.pixelSize: 13
    }
    Column {
        id: body
        x: 26
        y: heading.y + heading.height + 10
        width: card.width - 52
    }
}
