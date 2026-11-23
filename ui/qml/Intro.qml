import QtQuick
import QtQuick.Effects

// The start of the app. The mark of the logo gathers out of blur in the middle of the dark window
// and the name comes in under it; then the mark flies to its place in the rail while the cover
// fades and the interface comes in from the edges (Shell.qml moves it by "reveal"). A click skips it.
Item {
    id: intro
    anchors.fill: parent
    z: 1000
    visible: !done
    property bool wanted: true
    property string mark                              // the picture of the mark
    property rect land: Qt.rect(19, 22, 46, 46)       // where the mark ends: the logo of the rail
    property real gather: 0                           // the mark has come out of the blur
    property real word: 0                             // the name is in
    property real ripple: 0                           // the ring that runs out from the mark
    property real fly: 0                              // the mark is in the rail
    property real reveal: 0                           // the interface is in place
    property bool done: false
    readonly property int big: 280
    readonly property real middle: Math.round(height / 2 - 44)

    Component.onCompleted: if (!wanted) { reveal = 1; done = true }
    // The first frames of a window take long, and an animation that began before them would be
    // seen from its middle; so it begins with the first frame shown.
    Connections {
        target: intro.Window.window
        enabled: intro.wanted && !play.running && !intro.done && intro.gather === 0
        function onFrameSwapped() { play.start() }
    }
    function skip() {
        if (done || hurry.running) return
        play.stop()
        hurry.start()
    }

    SequentialAnimation {
        id: play
        PauseAnimation { duration: 140 }
        ParallelAnimation {
            NumberAnimation { target: intro; property: "gather"; to: 1; duration: 820; easing.type: Easing.OutCubic }
            SequentialAnimation {
                PauseAnimation { duration: 300 }
                NumberAnimation { target: intro; property: "ripple"; to: 1; duration: 820; easing.type: Easing.OutCubic }
            }
            SequentialAnimation {
                PauseAnimation { duration: 380 }
                NumberAnimation { target: intro; property: "word"; to: 1; duration: 640; easing.type: Easing.OutCubic }
            }
        }
        PauseAnimation { duration: 120 }
        ParallelAnimation {
            NumberAnimation { target: intro; property: "fly"; to: 1; duration: 780; easing.type: Easing.InOutCubic }
            SequentialAnimation {
                PauseAnimation { duration: 160 }
                NumberAnimation { target: intro; property: "reveal"; to: 1; duration: 820; easing.type: Easing.OutCubic }
            }
        }
        ScriptAction { script: intro.done = true }
    }
    SequentialAnimation {
        id: hurry
        ParallelAnimation {
            NumberAnimation { target: intro; property: "gather"; to: 1; duration: 200 }
            NumberAnimation { target: intro; property: "fly"; to: 1; duration: 380; easing.type: Easing.InOutCubic }
            NumberAnimation { target: intro; property: "reveal"; to: 1; duration: 420; easing.type: Easing.OutCubic }
        }
        ScriptAction { script: intro.done = true }
    }

    Rectangle { anchors.fill: parent; color: "#060608"; opacity: 1 - intro.reveal }
    MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.AllButtons; onPressed: intro.skip(); onWheel: (wheel) => wheel.accepted = true }

    Item {
        id: flying
        readonly property real size: intro.big + (intro.land.width - intro.big) * intro.fly
        readonly property real cx: intro.width / 2 + (intro.land.x + intro.land.width / 2 - intro.width / 2) * intro.fly
        readonly property real cy: intro.middle + (intro.land.y + intro.land.height / 2 - intro.middle) * intro.fly
        x: cx - size / 2; y: cy - size / 2
        width: size; height: size
        // A soft light behind the mark.
        RectangularShadow {
            anchors.centerIn: parent
            width: parent.size * 0.5; height: width
            radius: width / 2
            blur: parent.size * 0.8
            color: "white"
            opacity: 0.14 * intro.gather * (1 - intro.fly)
        }
        Rectangle {
            anchors.centerIn: parent
            width: parent.size * (0.72 + 0.95 * intro.ripple); height: width
            radius: width / 2
            color: "transparent"
            border.width: 1.5
            border.color: "white"
            opacity: 0.32 * (1 - intro.ripple) * (intro.ripple > 0 ? 1 : 0) * (1 - intro.fly)
        }
        Image {
            id: picture
            anchors.fill: parent
            source: intro.mark
            sourceSize: Qt.size(intro.big * Screen.devicePixelRatio, intro.big * Screen.devicePixelRatio)
            mipmap: true
            visible: false
        }
        MultiEffect {
            anchors.fill: parent
            source: picture
            blurEnabled: intro.gather < 1
            blur: 1 - intro.gather
            blurMax: 64
            autoPaddingEnabled: true
            opacity: intro.gather
            scale: 0.78 + 0.22 * intro.gather
            rotation: (1 - intro.gather) * -14
        }
    }
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        y: intro.middle + intro.big / 2 + 10 + Math.round((1 - intro.word) * 18)
        opacity: intro.word * Math.max(0, 1 - intro.fly * 2.6)
        Text { text: "Open"; color: "white"; font.family: "Inter Display"; font.weight: Font.Light; font.pixelSize: 52; font.letterSpacing: (1 - intro.word) * 9 }
        Text { text: "Music"; color: "white"; font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 52; font.letterSpacing: (1 - intro.word) * 9 }
    }
}
