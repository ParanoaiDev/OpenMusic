import QtQuick

Sheet {
    id: dialog
    width: 480
    property string question
    property string action
    property string arg
    function ask(text, act, argument) { question = text; action = act; arg = argument; open() }
    contentItem: Column {
        spacing: 20
        Text { width: parent.width; wrapMode: Text.WordWrap; text: dialog.question; color: "white"; font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 17 }
        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton { text: "Отмена"; onClicked: dialog.close() }
            PillButton { text: "Удалить"; primary: true; onClicked: { dialog.close(); app.confirmed(dialog.action, dialog.arg) } }
        }
    }
}
