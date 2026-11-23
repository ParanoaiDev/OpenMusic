import QtQuick

// The base of every tile on the home screen: it eases into its hover and sinks a little when pressed.
Item {
    id: card
    property real lift: area.containsMouse ? 1 : 0
    Behavior on lift { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    property alias hovered: area.containsMouse
    signal clicked()
    signal rightClicked()
    signal entered()
    scale: (1 + 0.035 * lift) * (area.pressed ? 0.97 : 1)
    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (mouse) => mouse.button === Qt.RightButton ? card.rightClicked() : card.clicked()
        onEntered: card.entered()
        z: 10
    }
}
