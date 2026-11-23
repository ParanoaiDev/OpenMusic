import QtQuick
import QtQuick.Effects

// One word of the clip mode. It waits in its place as a pale ghost; when it is sung it lights up
// with a short swell and lift that passes through a soft blur and settles, with no jump at the
// start. The accent word of a line lands on a white plate in italics.
Item {
    id: word
    property var info
    property real lineStart: 0
    property real now: 0
    property int px: 80
    readonly property bool accent: info && info.accent
    readonly property bool sung: now >= lineStart + (info ? info.delay : 0)
    property real appear: sung ? 1 : 0
    Behavior on appear { NumberAnimation { duration: 480; easing.type: Easing.OutCubic } }
    property real plate: accent && sung ? 1 : 0
    Behavior on plate { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }

    width: text.implicitWidth + (accent ? px * 0.3 : 0)
    height: text.implicitHeight

    Rectangle {
        visible: word.accent
        x: 0
        y: parent.height * 0.08
        height: parent.height * 0.9
        width: parent.width * word.plate
        radius: word.px * 0.14
        color: "#f6f6f6"
        opacity: word.plate
    }
    Text {
        id: text
        x: word.accent ? word.px * 0.15 : 0
        text: word.info ? word.info.text : ""
        color: word.accent && word.plate > 0.97 ? "#0a0a0a" : "white"
        font.family: "Inter Display"
        font.weight: Font.Black
        font.italic: word.accent
        font.pixelSize: word.px
        visible: false
    }
    // Drawn through an effect with padding, so the blur a word comes in with is not cut into a box.
    readonly property real swell: Math.sin(Math.PI * appear)
    MultiEffect {
        source: text
        x: text.x
        y: -word.px * 0.08 * word.swell
        width: text.width
        height: text.height
        autoPaddingEnabled: false
        paddingRect: Qt.rect(word.px * 0.6, word.px * 0.5, word.px * 0.6, word.px * 0.5)
        opacity: 0.2 + 0.8 * word.appear
        scale: 1 + 0.1 * word.swell
        blurEnabled: true
        blurMax: 40
        blur: 0.55 * word.swell
    }
}
