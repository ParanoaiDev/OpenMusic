import QtQuick

// Search: the library first, then everything on SoundCloud.
Item {
    id: page
    property real pad: Math.max(40, Math.min(90, width * 0.035))
    function focusField() { field.forceActiveFocus(); field.selectAll() }
    onVisibleChanged: if (visible) focusField()
    Column {
        id: head
        x: page.pad
        y: 34
        width: page.width - page.pad * 2
        spacing: 16
        Text { text: "Поиск"; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 42 }
        Field {
            id: field
            width: parent.width
            implicitHeight: 56
            round: 16
            font.pixelSize: 17
            glyph: "search"
            placeholderText: "Трек или артист — в медиатеке и на всём SoundCloud"
            onTextEdited: app.search(text)
        }
        Text { text: app.stateMap.searchStatus; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 14 }
    }
    TrackList {
        x: page.pad - 10
        y: head.y + head.height + 14
        width: page.width - page.pad * 2 + 20
        height: page.height - y
        list: "search"
        model: app.searchModel
    }
}
