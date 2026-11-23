import QtQuick

// One setting: what it is and what it does on the left, its switch on the right. The whole row
// takes the click.
Item {
    id: row
    property string title
    property string text: ""
    property bool checked: false
    property bool enabled2: true
    property bool last: false
    signal toggled(bool on)
    width: parent ? parent.width : 300
    height: Math.max(58, words.implicitHeight + 26)
    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: -12
        anchors.rightMargin: -12
        radius: 14
        color: Qt.rgba(1, 1, 1, area.containsMouse ? 0.045 : 0)
        Behavior on color { ColorAnimation { duration: 160 } }
    }
    Column {
        id: words
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width - 74
        spacing: 3
        opacity: row.enabled2 ? 1 : 0.45
        Text { width: parent.width; text: row.title; wrapMode: Text.WordWrap; color: "white"; font.family: "Inter"; font.pixelSize: 15; font.weight: Font.Medium }
        Text { width: parent.width; visible: text !== ""; text: row.text; wrapMode: Text.WordWrap; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 13; lineHeight: 1.15 }
    }
    Toggle { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; checked: row.checked; enabled2: row.enabled2; hot: area.containsMouse }
    Rectangle { visible: !row.last; anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.06) }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        enabled: row.enabled2
        cursorShape: Qt.PointingHandCursor
        onClicked: row.toggled(!row.checked)
    }
}
