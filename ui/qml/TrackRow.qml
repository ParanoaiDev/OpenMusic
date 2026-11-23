import QtQuick

// A track in a list: its cover, title and artist, quiet details. The light under it follows the
// pointer, and the track that plays shows moving bars over its cover.
Item {
    id: row
    property string list
    property bool compact: false
    property int number: 0              // a place in a chart, shown before the cover; the play sign takes it under the pointer
    height: 62
    readonly property bool playing: model.current && app.playerMap.playing
    Rectangle {
        anchors.fill: parent
        radius: 12
        color: Qt.rgba(1, 1, 1, model.current ? 0.09 : area.containsMouse ? 0.06 : 0)
        Behavior on color { ColorAnimation { duration: 180 } }
    }
    Text {
        visible: row.number > 0
        x: 6; width: 34
        anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: Text.AlignHCenter
        text: row.number
        color: model.current ? "white" : Qt.rgba(1, 1, 1, 0.5)
        opacity: area.containsMouse ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 140 } }
        font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 16
    }
    Icon {
        visible: row.number > 0
        x: 6 + (34 - size) / 2
        anchors.verticalCenter: parent.verticalCenter
        name: "play"
        size: 15
        opacity: area.containsMouse ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 140 } }
    }
    RoundImage {
        id: art
        x: row.number > 0 ? 46 : 10
        anchors.verticalCenter: parent.verticalCenter
        width: 44; height: 44
        radius: 6
        source: model.cover
    }
    Rectangle {
        anchors.fill: art
        radius: 6
        color: Qt.rgba(0, 0, 0, model.current ? 0.55 : area.containsMouse ? 0.45 : 0)
        Behavior on color { ColorAnimation { duration: 180 } }
    }
    Icon {
        anchors.centerIn: art
        name: "play"
        size: 16
        opacity: !model.current && area.containsMouse ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 160 } }
    }
    Row {
        anchors.centerIn: art
        spacing: 3
        visible: model.current
        Repeater {
            model: 3
            Rectangle {
                width: 3.5
                radius: 2
                color: "white"
                anchors.bottom: parent.bottom
                property real level: 0.4
                height: 6 + 14 * level
                SequentialAnimation on level {
                    running: row.playing
                    loops: Animation.Infinite
                    NumberAnimation { to: 1.0; duration: 260 + index * 90; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.25; duration: 300 + index * 70; easing.type: Easing.InOutSine }
                }
            }
        }
    }
    Column {
        x: art.x + 60
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - x - (row.compact ? 52 : 300)
        spacing: 3
        Text { width: parent.width; text: model.title; elide: Text.ElideRight; color: "white"; font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15 }
        Text { width: parent.width; text: model.artist; elide: Text.ElideRight; color: Qt.rgba(1, 1, 1, 0.55); font.family: "Inter"; font.pixelSize: 13 }
    }
    Text {
        visible: !row.compact
        x: parent.width - 290
        width: 140
        anchors.verticalCenter: parent.verticalCenter
        text: model.source
        elide: Text.ElideRight
        color: Qt.rgba(1, 1, 1, 0.45)
        font.family: "Inter"; font.pixelSize: 13
    }
    Text {
        visible: !row.compact
        x: parent.width - 150
        width: 100
        anchors.verticalCenter: parent.verticalCenter
        text: model.detail
        elide: Text.ElideRight
        color: Qt.rgba(1, 1, 1, 0.4)
        font.family: "Inter"; font.pixelSize: 13
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (mouse) => mouse.button === Qt.RightButton ? app.openMenu(row.list, index) : app.play(row.list, index)
        onEntered: app.hover(row.list, index)
        // The three dots open the same menu as the right button: for those who do not right-click,
        // and for a finger on a phone.
        IconButton {
            anchors.right: parent.right
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            size: 34
            glyph: 17
            name: "more"
            tip: "Меню трека"
            visible: opacity > 0
            opacity: area.containsMouse ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 160 } }
            onClicked: app.openMenu(row.list, index)
        }
    }
}
