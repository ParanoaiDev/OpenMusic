import QtQuick
import QtQuick.Controls

// "Добавить музыку": the sources in two columns, then the steps of the one chosen.
Sheet {
    id: sheet
    width: 820
    property int chosen: -1
    readonly property var sources: app.stateMap.importSources
    readonly property var source: chosen >= 0 ? sources[chosen] : null
    onOpened: { chosen = -1 }
    contentItem: Item {
        implicitHeight: chosen < 0 ? menu.implicitHeight : detail.implicitHeight
        Behavior on implicitHeight { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
        clip: true
        Column {
            id: menu
            width: parent.width
            spacing: 6
            opacity: sheet.chosen < 0 ? 1 : 0
            visible: opacity > 0.01
            x: sheet.chosen < 0 ? 0 : -40
            Behavior on opacity { NumberAnimation { duration: 220 } }
            Behavior on x { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
            Item {
                width: parent.width; height: 40
                Text { text: "Добавить музыку"; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 28 }
                IconButton { anchors.right: parent.right; name: "close"; onClicked: sheet.close() }
            }
            Text { text: "Откуда взять треки? Вход в аккаунты не нужен."; color: Qt.rgba(1, 1, 1, 0.55); font.family: "Inter"; font.pixelSize: 14 }
            Item { width: 1; height: 10 }
            Grid {
                columns: 2
                columnSpacing: 10
                rowSpacing: 10
                Repeater {
                    model: sheet.sources
                    Rectangle {
                        width: (menu.width - 10) / 2
                        height: 72
                        radius: 16
                        color: Qt.rgba(1, 1, 1, rowArea.containsMouse ? 0.09 : 0.045)
                        border.color: Qt.rgba(1, 1, 1, rowArea.containsMouse ? 0.22 : 0.07)
                        Behavior on color { ColorAnimation { duration: 160 } }
                        Rectangle {
                            x: 14; anchors.verticalCenter: parent.verticalCenter
                            width: 44; height: 44; radius: 12
                            color: Qt.rgba(1, 1, 1, 0.08)
                            Image { anchors.centerIn: parent; width: 22; height: 22; source: modelData.icon; sourceSize: Qt.size(44, 44); mipmap: true }
                        }
                        Column {
                            x: 72; anchors.verticalCenter: parent.verticalCenter
                            spacing: 2
                            Text { text: modelData.name; color: "white"; font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15 }
                            Text { text: modelData.summary; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 13 }
                        }
                        Text { anchors.right: parent.right; anchors.rightMargin: 18 - 4 * (rowArea.containsMouse ? 1 : 0); anchors.verticalCenter: parent.verticalCenter
                               text: "›"; color: Qt.rgba(1, 1, 1, 0.5); font.pixelSize: 22
                               Behavior on anchors.rightMargin { NumberAnimation { duration: 160 } } }
                        MouseArea { id: rowArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { sheet.chosen = index; field.text = ""; if (modelData.field) field.forceActiveFocus() } }
                    }
                }
            }
        }
        Column {
            id: detail
            width: parent.width
            spacing: 10
            opacity: sheet.chosen >= 0 ? 1 : 0
            visible: opacity > 0.01
            x: sheet.chosen >= 0 ? 0 : 40
            Behavior on opacity { NumberAnimation { duration: 220 } }
            Behavior on x { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
            Item {
                width: parent.width; height: 40
                IconButton { name: "back"; onClicked: sheet.chosen = -1 }
                IconButton { anchors.right: parent.right; name: "close"; onClicked: sheet.close() }
            }
            Row {
                spacing: 14
                Rectangle {
                    width: 56; height: 56; radius: 14; color: Qt.rgba(1, 1, 1, 0.08)
                    Image { anchors.centerIn: parent; width: 26; height: 26; source: sheet.source ? sheet.source.icon : ""; sourceSize: Qt.size(52, 52); mipmap: true }
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text { text: sheet.source ? sheet.source.name : ""; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 26 }
                    Text { text: sheet.source ? sheet.source.summary : ""; color: Qt.rgba(1, 1, 1, 0.55); font.family: "Inter"; font.pixelSize: 14 }
                }
            }
            Item { width: 1; height: 4 }
            Repeater {
                model: sheet.source ? sheet.source.steps : []
                Rectangle {
                    width: detail.width; height: 46; radius: 12
                    color: Qt.rgba(1, 1, 1, 0.045)
                    Rectangle { x: 12; anchors.verticalCenter: parent.verticalCenter; width: 26; height: 26; radius: 13; color: Qt.rgba(1, 1, 1, 0.1)
                                Text { anchors.centerIn: parent; text: index + 1; color: "white"; font.family: "Inter"; font.weight: Font.Bold; font.pixelSize: 12 } }
                    Text { x: 50; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 62; elide: Text.ElideRight; text: modelData; color: "white"; font.family: "Inter"; font.pixelSize: 14 }
                }
            }
            Field {
                id: field
                visible: !!(sheet.source && sheet.source.field)
                width: parent.width
                implicitHeight: 50
                round: 14
                placeholderText: sheet.source ? sheet.source.field : ""
                onAccepted: submit()
            }
            Text {
                visible: !!(sheet.source && sheet.source.note)
                width: parent.width
                wrapMode: Text.WordWrap
                text: sheet.source ? sheet.source.note : ""
                color: Qt.rgba(1, 1, 1, 0.42)
                font.family: "Inter"; font.pixelSize: 13
            }
            Item { width: 1; height: 6 }
            Row {
                anchors.right: parent.right
                spacing: 10
                PillButton {
                    visible: !!(sheet.source && sheet.source.secondaryTitle)
                    text: sheet.source ? sheet.source.secondaryTitle : ""
                    onClicked: app.importChoose(sheet.source.secondaryKind, "")
                }
                PillButton {
                    primary: true
                    text: sheet.source ? sheet.source.primary : ""
                    opacity: !sheet.source || !sheet.source.field || field.text.trim() !== "" ? 1 : 0.4
                    onClicked: submit()
                }
            }
        }
    }
    function submit() {
        if (!source) return
        if (source.field && field.text.trim() === "") return
        var kind = source.kind, value = field.text
        close()
        app.importChoose(kind, value)
    }
}
