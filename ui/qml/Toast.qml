import QtQuick

// A short message above the player: it rises in, waits, and sinks away. While an import runs a
// thin light runs along its bottom.
Rectangle {
    id: toast
    property bool error: false
    property bool busy: false
    property string message: ""
    property real shown: 0
    Behavior on shown { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
    function say(text, isError, sticky) {
        message = text; error = isError; busy = sticky && !isError
        shown = 1
        sticky ? hide.stop() : hide.restart()
    }
    Timer { id: hide; interval: 6000; onTriggered: toast.shown = 0 }
    visible: shown > 0.01
    opacity: shown
    width: Math.min(640, label.implicitWidth + 48)
    height: Math.max(42, label.paintedHeight + 22)
    radius: 21
    color: error ? "#1c1c1f" : "#f4f4f4"
    border.width: error ? 1 : 0
    border.color: Qt.rgba(1, 1, 1, 0.25)
    transform: Translate { y: (1 - toast.shown) * 16 }
    clip: true
    Text {
        id: label
        anchors.centerIn: parent
        width: Math.min(implicitWidth, 592)
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: toast.message
        color: toast.error ? "white" : "#0a0a0a"
        font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 14
    }
    Rectangle {
        visible: toast.busy
        anchors.bottom: parent.bottom
        height: 3; width: 140
        color: Qt.rgba(0, 0, 0, 0.35)
        radius: 2
        NumberAnimation on x { from: -140; to: toast.width; duration: 1300; loops: Animation.Infinite; running: toast.busy }
    }
}
