import QtQuick
import QtQuick.Controls

// A titled row that scrolls sideways: with a sideways swipe, with Shift and the wheel, or with the
// arrows, which are there only when the row is wider than the page. The plain wheel scrolls the page.
Column {
    id: shelf
    property string title
    property alias model: row.model
    property alias delegate: row.delegate
    property real itemHeight: 220
    property real gap: 22
    readonly property real span: Math.max(0, row.contentWidth - row.width)
    spacing: 16
    width: parent ? parent.width : 0
    Item {
        width: parent.width
        height: 34
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: shelf.title
            color: "white"
            font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 26
        }
        Row {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            visible: shelf.span > 0
            PillButton {
                text: "‹"
                onClicked: row.page(-1)
                opacity: row.contentX > 1 ? 1 : 0.35
                Behavior on opacity { NumberAnimation { duration: 200 } }
            }
            PillButton {
                text: "›"
                onClicked: row.page(1)
                opacity: row.contentX < shelf.span - 1 ? 1 : 0.35
                Behavior on opacity { NumberAnimation { duration: 200 } }
            }
        }
    }
    ListView {
        id: row
        width: parent.width
        height: shelf.itemHeight
        orientation: ListView.Horizontal
        spacing: shelf.gap
        clip: false
        interactive: false
        pixelAligned: true
        boundsBehavior: Flickable.StopAtBounds
        cacheBuffer: 1200
        function page(direction) {
            var from = slide.running ? slide.to : contentX
            slide.to = Math.round(Math.max(0, Math.min(shelf.span, from + direction * width * 0.8)))
            slide.restart()
        }
        NumberAnimation { id: slide; target: row; property: "contentX"; duration: 500; easing.type: Easing.OutCubic }
        // The tiles of a new row come in one after another.
        populate: Transition {
            id: pop
            SequentialAnimation {
                PropertyAction { property: "opacity"; value: 0 }
                PauseAnimation { duration: Math.min(12, pop.ViewTransition.index) * 35 }
                ParallelAnimation {
                    NumberAnimation { property: "opacity"; to: 1; duration: 360; easing.type: Easing.OutCubic }
                    NumberAnimation { property: "y"; from: 22; to: 0; duration: 420; easing.type: Easing.OutCubic }
                }
            }
        }
        add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 320 } }
    }
    SmoothWheel { flick: row; horizontal: true }
    SmoothWheel { flick: row; horizontal: true; shifted: true }
}
