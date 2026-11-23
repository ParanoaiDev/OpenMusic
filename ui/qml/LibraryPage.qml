import QtQuick
import QtQuick.Controls

// The library and the listener's own collections in one list.
Item {
    id: page
    readonly property var st: app.stateMap
    property real pad: Math.max(40, Math.min(90, width * 0.035))
    Connections {
        target: app
        function onQuerySet(text) { search.text = text }
    }
    Column {
        id: head
        x: page.pad
        y: 34
        width: page.width - page.pad * 2
        spacing: 18
        Item {
            width: parent.width
            height: 64
            Column {
                Text { text: page.st.viewTitle; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 42 }
                Text { text: page.st.viewCount; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 14 }
            }
            Row {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: 6
                spacing: 10
                Field {
                    id: search
                    width: 320
                    glyph: "search"
                    placeholderText: "Поиск по трекам и артистам"
                    onTextEdited: app.filter(text)
                }
                IconButton {
                    name: "more"
                    size: 42
                    tip: "Действия"
                    onClicked: actions.popup()
                    Menu2 {
                        id: actions
                        Instantiator {
                            model: page.st.libraryActions
                            delegate: MenuItem2 { text: modelData.title; onTriggered: app.libraryAction(modelData.action, modelData.arg) }
                            onObjectAdded: (index, object) => actions.insertItem(index, object)
                            onObjectRemoved: (index, object) => actions.removeItem(object)
                        }
                    }
                }
            }
        }
        Row {
            spacing: 8
            PillButton { text: "Все треки"; checked: page.st.view === "library"; onClicked: app.setView("library", -1) }
            PillButton { text: "Мне нравится"; checked: page.st.view === "likes"; onClicked: app.setView("likes", -1) }
            PillButton { text: "История"; checked: page.st.view === "history"; onClicked: app.setView("history", -1) }
            PillButton {
                text: "Плейлисты ▾"
                checked: page.st.view === "playlist"
                onClicked: lists.popup()
                Menu2 {
                    id: lists
                    MenuItem2 { text: "Новый плейлист…"; onTriggered: app.libraryAction("new-playlist", "") }
                    Instantiator {
                        model: page.st.playlists
                        delegate: MenuItem2 { text: modelData.name + "  ·  " + modelData.count; onTriggered: app.setView("playlist", modelData.id) }
                        onObjectAdded: (index, object) => lists.insertItem(index, object)
                        onObjectRemoved: (index, object) => lists.removeItem(object)
                    }
                }
            }
            // Jams: the lists "Начать джем" in a track's menu has made, the latest first.
            PillButton {
                text: "Джемы ▾"
                visible: page.st.jams.length > 0
                checked: page.st.view === "jam"
                onClicked: jams.popup()
                Menu2 {
                    id: jams
                    Instantiator {
                        model: page.st.jams
                        delegate: MenuItem2 { text: modelData.name + "  ·  " + modelData.count; onTriggered: app.setView("jam", modelData.id) }
                        onObjectAdded: (index, object) => jams.insertItem(index, object)
                        onObjectRemoved: (index, object) => jams.removeItem(object)
                    }
                }
            }
        }
        Flow {
            width: parent.width
            spacing: 8
            visible: page.st.sources.length > 0
            Repeater {
                model: page.st.sources
                PillButton { text: modelData.title; checked: modelData.checked; onClicked: app.setSource(modelData.name) }
            }
        }
    }
    TrackList {
        id: tracks
        x: page.pad - 10
        y: head.y + head.height + 18
        width: page.width - page.pad * 2 + 20
        height: page.height - y
        list: "library"
        model: app.libraryModel
    }
    Text {
        anchors.centerIn: tracks
        visible: app.libraryModel.count === 0
        width: 520
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: page.st.emptyText
        color: Qt.rgba(1, 1, 1, 0.5)
        font.family: "Inter"; font.pixelSize: 16
    }
}
