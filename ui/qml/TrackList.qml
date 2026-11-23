import QtQuick
import QtQuick.Controls

// A long list of tracks that scrolls smoothly; new contents come in row after row.
Item {
    id: holder
    property alias model: view.model
    property string list
    property bool compact: false
    property bool numbered: false
    property alias view: view
    ListView {
        id: view
        anchors.fill: parent
        clip: true
        interactive: false
        cacheBuffer: 900
        spacing: 2
        reuseItems: true
        ScrollBar.vertical: ScrollBar { width: 8; policy: ScrollBar.AsNeeded }
        delegate: TrackRow {
            width: view.width - 12
            list: holder.list
            compact: holder.compact
            number: holder.numbered ? index + 1 : 0
        }
        add: Transition { NumberAnimation { properties: "opacity"; from: 0; to: 1; duration: 260 } }
        populate: Transition {
            id: pop
            SequentialAnimation {
                PropertyAction { property: "opacity"; value: 0 }
                PauseAnimation { duration: Math.min(14, pop.ViewTransition.index) * 22 }
                ParallelAnimation {
                    NumberAnimation { property: "opacity"; to: 1; duration: 320; easing.type: Easing.OutCubic }
                    NumberAnimation { property: "y"; from: pop.ViewTransition.destination.y + 18; duration: 380; easing.type: Easing.OutCubic }
                }
            }
        }
    }
    SmoothWheel { flick: view }
}
