import QtQuick

// Asks for a name: a new playlist, or a new name for one.
Sheet {
    id: dialog
    width: 460
    property string title
    property string action
    property string arg
    function ask(heading, value, act, argument) { title = heading; action = act; arg = argument; field.text = value; open(); field.forceActiveFocus(); field.selectAll() }
    contentItem: Column {
        spacing: 16
        Text { text: dialog.title; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 24 }
        Field { id: field; width: parent.width; implicitHeight: 48; round: 14; placeholderText: "Название"; onAccepted: dialog.done() }
        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton { text: "Отмена"; onClicked: dialog.close() }
            PillButton { text: "Готово"; primary: true; onClicked: dialog.done() }
        }
    }
    function done() { if (field.text.trim() === "") return; close(); app.named(action, arg, field.text) }
}
