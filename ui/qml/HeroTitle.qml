import QtQuick
import QtQuick.Effects

// The words in the middle of the top of the home screen. The greeting has its last word on a
// coloured plate that slides out from the left; "Мой поток" is set in two faces, an italic serif and
// a heavy grotesque painted with the flowing colours of the covers; its letters rise in one by one,
// then sway a little with the bass; the caption lights up word by word.
Column {
    id: title
    property real t: 0
    property real bass: 0
    property color c0: "white"
    property color c1: "white"
    property color c2: "white"
    property string greeting: ""
    property string caption: ""
    property real size: 110
    property real show: 0
    property real lit: 0
    property bool go: true
    readonly property var words: caption.split(" ")
    spacing: 12

    function clamp(x) { return Math.max(0, Math.min(1, x)) }
    function back(x) { var c = 1.6; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2) }
    function replay() { show = 0; lit = 0; enter.restart() }
    Component.onCompleted: if (go) replay()
    onGoChanged: if (go) replay()
    onGreetingChanged: if (go) replay()
    onCaptionChanged: { lit = 0; if (!enter.running) litUp.restart() }

    SequentialAnimation {
        id: enter
        NumberAnimation { target: title; property: "show"; from: 0; to: 1; duration: 1500 }
        ScriptAction { script: litUp.restart() }
    }
    NumberAnimation { id: litUp; target: title; property: "lit"; from: 0; to: title.words.length + 1; duration: 70 * title.words.length + 300 }

    // One letter of the title: rises from below with a small overshoot, then rides a slow wave
    // that the bass pushes up.
    component Letter: Text {
        required property int index
        required property string modelData
        property int shift: 0
        readonly property int n: index + shift
        text: modelData
        // Qt's own text drawing places letters between pixels; the system's, used elsewhere in the
        // app for crispness, snaps them to whole pixels, so a slowly swaying letter moves in steps.
        renderType: Text.QtRendering
        readonly property real p: title.clamp((title.show * 1.7 - n * 0.075) / 0.6)
        opacity: title.clamp(p * 1.6)
        color: "white"
        transform: Translate {
            y: (1 - title.back(p)) * title.size * 0.32
               - title.bass * title.size * 0.06 * (0.5 + 0.5 * Math.sin(title.t * 3.2 - n * 0.7))
        }
    }

    // ---- greeting ----
    Row {
        id: hello
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 9
        readonly property int cut: title.greeting.lastIndexOf(" ")
        readonly property real p: title.clamp((title.show - 0.25) / 0.35)
        opacity: title.clamp(title.show * 3)
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: hello.cut > 0 ? title.greeting.slice(0, hello.cut) : title.greeting
            color: Qt.rgba(1, 1, 1, 0.8)
            font.family: "Inter Display"; font.weight: Font.Medium; font.pixelSize: 22
        }
        Item {
            anchors.verticalCenter: parent.verticalCenter
            visible: hello.cut > 0
            width: tail.implicitWidth + 22; height: tail.implicitHeight + 6
            Rectangle {
                width: parent.width * (1 - Math.pow(1 - hello.p, 3)); height: parent.height
                radius: 9
                color: Qt.tint(title.c0, Qt.rgba(1, 1, 1, 0.72))
                rotation: -2
                antialiasing: true
            }
            Text {
                id: tail
                anchors.centerIn: parent
                text: hello.cut > 0 ? title.greeting.slice(hello.cut + 1) : ""
                color: "#0b0b0e"
                opacity: title.clamp(hello.p * 2 - 0.6)
                font.family: "C059"; font.italic: true; font.weight: Font.Bold; font.pixelSize: 23
            }
        }
    }

    // ---- "Мой поток" ----
    // The box keeps the size of the letters for the layout; the layers inside reach past it so the
    // letters can rise, sway and lean without being cut.
    Item {
        id: box
        anchors.horizontalCenter: parent.horizontalCenter
        readonly property real pad: Math.round(title.size * 0.36)
        readonly property real gap: Math.round(title.size * 0.2)
        width: moi.width + gap + heavy.width; height: heavy.height
        FontMetrics { id: serif; font.family: "C059"; font.italic: true; font.pixelSize: Math.round(title.size * 0.98) }
        FontMetrics { id: grot; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: Math.round(title.size * 1.1) }
        Item {
            x: -box.pad; y: -box.pad
            width: box.width + box.pad * 2; height: box.height + box.pad * 2
            layer.enabled: true
            layer.effect: MultiEffect { shadowEnabled: true; shadowBlur: 1.0; shadowOpacity: 0.55; shadowColor: title.c0; autoPaddingEnabled: true }
            Row {
                id: moi
                x: box.pad; y: box.pad + grot.ascent - serif.ascent
                Repeater {
                    model: ["М", "о", "й"]
                    Letter { font.family: "C059"; font.italic: true; font.pixelSize: serif.font.pixelSize }
                }
            }
            // The heavy word goes into a layer of its own, painted by the gradient shader.
            Item {
                x: box.pad + moi.width + box.gap
                width: heavy.width + box.pad; height: parent.height
                layer.enabled: true
                layer.effect: ShaderEffect {
                    property real time: title.t
                    property real shine: (title.t * 0.11) % 2.2 - 0.4
                    property real lift: 0.22
                    property color c0: title.c0
                    property color c1: title.c1
                    property color c2: title.c2
                    fragmentShader: "fill.frag.qsb"
                }
                Row {
                    id: heavy
                    y: box.pad
                    Repeater {
                        model: ["п", "о", "т", "о", "к"]
                        Letter {
                            shift: 3
                            font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: grot.font.pixelSize
                            font.letterSpacing: -title.size * 0.02
                        }
                    }
                }
            }
        }
    }

    // ---- caption: the words light up in turn ----
    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 5
        Repeater {
            model: title.words
            Text {
                text: modelData
                renderType: Text.QtRendering
                readonly property real p: title.clamp(title.lit - index)
                color: "white"
                opacity: 0.22 + 0.5 * p
                font.family: "Inter"; font.pixelSize: 17
                transform: Translate { y: (1 - p) * 6 }
            }
        }
    }
}
