import QtQuick
import QtQuick.Effects

// A whole line of the clip mode. Two of these take turns: the one being sung is active, and the one
// before it drifts up, shrinks and dissolves.
Item {
    id: line
    property var rows: []
    property real lineStart: 0
    property bool active: false
    property real now: 0
    property int px: 80
    property real leaving: active ? 0 : 1
    Behavior on leaving { NumberAnimation { duration: 650; easing.type: Easing.OutCubic } }

    opacity: 1 - leaving
    scale: 1 - 0.12 * leaving
    transform: Translate { y: -line.px * 1.3 * line.leaving }
    layer.enabled: leaving > 0.01
    layer.effect: MultiEffect { blurEnabled: true; blurMax: 48; blur: line.leaving * 0.8 }

    Column {
        anchors.centerIn: parent
        spacing: line.px * 0.02
        Repeater {
            model: line.rows
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: line.px * 0.26
                Repeater {
                    model: modelData
                    ClipWord {
                        info: modelData
                        lineStart: line.lineStart
                        now: line.now
                        px: line.px
                    }
                }
            }
        }
    }
}
