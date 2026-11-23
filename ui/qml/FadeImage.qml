import QtQuick

// An image that cross-fades to a new picture instead of switching to it.
Item {
    id: holder
    property url source
    property int fillMode: Image.PreserveAspectCrop
    property int duration: 900
    property bool flip: false
    // A change handler does not run for the first value, so the first picture is set when ready.
    Component.onCompleted: show()
    onSourceChanged: show()
    property url shown
    function show() {
        if (source == shown) return
        shown = source
        if (flip) { second.source = source } else { first.source = source }
        flip = !flip
    }
    Image {
        id: first
        anchors.fill: parent
        fillMode: holder.fillMode
        asynchronous: true
        smooth: true
        mipmap: true
        opacity: holder.flip && status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: holder.duration; easing.type: Easing.InOutSine } }
    }
    Image {
        id: second
        anchors.fill: parent
        fillMode: holder.fillMode
        asynchronous: true
        smooth: true
        mipmap: true
        opacity: !holder.flip && status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: holder.duration; easing.type: Easing.InOutSine } }
    }
}
