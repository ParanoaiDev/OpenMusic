import QtQuick
import QtQuick.Controls

// The menu of a track, the same everywhere.
Menu2 {
    id: menu
    property var info: ({})
    function openFor(data) { info = data; popup() }
    function act(action, arg) { app.trackAction(info.list, info.index, action, arg || "") }
    MenuItem2 { text: "Слушать"; onTriggered: menu.act("play") }
    MenuItem2 { text: "Начать джем"; onTriggered: menu.act("jam") }
    MenuItem2 { text: "Играть следующим"; onTriggered: menu.act("next") }
    MenuItem2 { text: "Добавить в очередь"; onTriggered: menu.act("queue") }
    MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Qt.rgba(1, 1, 1, 0.08) } }
    MenuItem2 { text: menu.info.liked ? "Убрать из «Мне нравится»" : "Нравится"; onTriggered: menu.act("like") }
    Menu2 {
        id: lists
        title: "Добавить в плейлист"
        MenuItem2 { text: "Новый плейлист…"; onTriggered: menu.act("new-playlist") }
        Instantiator {
            model: menu.info.playlists || []
            delegate: MenuItem2 { text: modelData.name; onTriggered: menu.act("playlist", String(modelData.id)) }
            onObjectAdded: (index, object) => lists.insertItem(index, object)
            onObjectRemoved: (index, object) => lists.removeItem(object)
        }
    }
    MenuSeparator { contentItem: Rectangle { implicitHeight: 1; color: Qt.rgba(1, 1, 1, 0.08) } }
    MenuItem2 { text: "Открыть в " + (menu.info.source || ""); enabled: !!menu.info.canOpen; onTriggered: menu.act("open") }
    MenuItem2 { text: "Все треки " + (menu.info.artist || ""); onTriggered: menu.act("artist") }
    Instantiator {
        model: menu.info.extras || []
        delegate: MenuItem2 { text: modelData.title; onTriggered: menu.act(modelData.action) }
        onObjectAdded: (index, object) => menu.addItem(object)
        onObjectRemoved: (index, object) => menu.removeItem(object)
    }
}
