import QtQuick

// A rounded button that eases into its hover and sinks a little when pressed, like the rest of the app.
Item {
    id: pill
    property string text: ""
    property bool checked: false
    property bool primary: false
    signal clicked()
    implicitWidth: Math.max(36, label.implicitWidth + 30)
    implicitHeight: 34
    scale: area.pressed ? 0.96 : 1
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: pill.checked || pill.primary ? (area.containsMouse ? "#ffffff" : "#ececec")
                                            : Qt.rgba(1, 1, 1, area.containsMouse ? 0.16 : 0.07)
        border.width: pill.checked || pill.primary ? 0 : 1
        border.color: Qt.rgba(1, 1, 1, area.containsMouse ? 0.4 : 0.16)
        Behavior on color { ColorAnimation { duration: 180 } }
    }
    Text {
        id: label
        anchors.centerIn: parent
        text: pill.text
        color: pill.checked || pill.primary ? "#0a0a0a" : (area.containsMouse ? "#ffffff" : "#bdbdbd")
        font.family: "Inter"
        font.pixelSize: 13
        font.weight: Font.DemiBold
        Behavior on color { ColorAnimation { duration: 180 } }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: pill.clicked()
    }
}
