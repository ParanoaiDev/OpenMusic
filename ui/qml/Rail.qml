import QtQuick

// The left panel: the logo, the pages, and "add music". The light under the current page slides
// to the one chosen.
Rectangle {
    id: rail
    width: 84
    color: "#0b0b0d"
    signal addClicked()
    property bool showLogo: true      // the start screen brings the logo here itself
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Qt.rgba(1, 1, 1, 0.06) }
    Image {
        source: app.stateMap.logo
        width: 46; height: 46
        sourceSize: Qt.size(96, 96)
        anchors.horizontalCenter: parent.horizontalCenter
        y: 22
        smooth: true
        mipmap: true
        visible: rail.showLogo
    }
    readonly property var pages: [ { icon: "home", name: "Главная", page: 0 }, { icon: "search", name: "Поиск", page: 1 },
                                   { icon: "library", name: "Медиатека", page: 2 }, { icon: "lyrics", name: "Сейчас играет", page: 3 },
                                   { icon: "settings", name: "Настройки", page: 4 } ]
    Rectangle {
        id: marker
        width: 52; height: 52
        radius: 16
        x: (rail.width - width) / 2
        // A page that is not in the rail (an artist's) keeps the light where it was and dims it.
        readonly property int place: rail.pages.findIndex(p => p.page === app.stateMap.page)
        property int last: 0
        onPlaceChanged: if (place >= 0) last = place
        y: column.y + (place >= 0 ? place : last) * 62
        opacity: place >= 0 ? 1 : 0.35
        Behavior on opacity { NumberAnimation { duration: 300 } }
        color: Qt.rgba(1, 1, 1, 0.1)
        Behavior on y { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }
        Rectangle { x: -(rail.width - parent.width) / 2; y: 14; width: 3; height: parent.height - 28; radius: 2; color: "white" }
    }
    Column {
        id: column
        y: 104
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 10
        Repeater {
            model: rail.pages
            IconButton {
                size: 52
                glyph: 22
                name: modelData.icon
                tip: modelData.name
                active: app.stateMap.page === modelData.page
                onClicked: app.setPage(modelData.page)
            }
        }
    }
    Item {
        width: 52; height: 52
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        Rectangle {
            anchors.fill: parent
            radius: 26
            color: addArea.containsMouse ? "white" : "#ececec"
            scale: addArea.pressed ? 0.92 : addArea.containsMouse ? 1.06 : 1
            Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: 160 } }
        }
        Icon { anchors.centerIn: parent; name: "plus"; tint: "#0a0a0a"; size: 22 }
        MouseArea { id: addArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: rail.addClicked() }
        ToolTipText { text: "Добавить музыку"; shown: addArea.containsMouse }
    }
}
