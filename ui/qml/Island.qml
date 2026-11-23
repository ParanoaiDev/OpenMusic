import QtQuick
import QtQuick.Window
import QtQuick.Effects

// The island at the top of the screen (ui/island.py places it). Small, it shows the cover and the
// beat of what plays; under the pointer it grows into a player; when a new track starts it opens
// halfway for a few seconds to say what it is. Its size moves on springs, so it stretches a little
// past its goal and settles, the way a drop of something thick would.
Window {
    id: win
    width: 640
    height: 300
    visible: false
    color: "transparent"
    title: "OpenMusic"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.Tool | Qt.NoDropShadowWindowHint

    readonly property var p: app.playerMap
    readonly property var s: app.settingsMap
    property string forceMode: ""              // for tests and screenshots
    property bool over: false                  // the pointer rests on the island
    property bool peeking: false               // a new track has just started
    readonly property string mode: forceMode !== "" ? forceMode : over ? "open" : peeking ? "peek" : "compact"
    readonly property bool withLyrics: s.islandLyrics && np.synced && np.lines.length > 0
    // Nothing plays: the island stays, with the logo, and opens into a way to start the music.
    readonly property bool idle: !p.hasTrack
    readonly property size goal: mode === "open" ? (idle ? Qt.size(400, 128) : Qt.size(452, withLyrics ? 208 : 180))
                                 : mode === "peek" ? Qt.size(idle ? 420 : 390, 64) : Qt.size(idle ? 150 : 204, 36)
    property string peekCaption: "Сейчас играет"
    property string peekText: p.title + "  ·  " + p.artist
    readonly property real goalRadius: mode === "open" ? 42 : mode === "peek" ? 32 : 18

    // The colour of the cover, made light enough to glow on black.
    readonly property color cover: p.colour
    readonly property color accent: Qt.hsla(cover.hslHue < 0 ? 0 : cover.hslHue, Math.min(1, cover.hslSaturation * 1.15),
                                            Math.max(0.64, cover.hslLightness), 1)

    // The shape follows its goal on springs. Growing it overshoots a little and settles; going back
    // small it is quicker and calmer. The springs are set before the goal is handed to them: set
    // the other way round, an animation starts with the springs of the change before.
    property bool ready: false
    property real bw: 0
    property real bh: 0
    property real br: goalRadius
    onGoalChanged: {
        var up = goal.width * goal.height > bw * bh
        springW.spring = springH.spring = up ? 4.8 : 10
        springW.damping = up ? 0.4 : 0.8
        springH.damping = up ? 0.42 : 0.8
        bw = goal.width
        bh = goal.height
        pushShape(false)
    }
    Behavior on bw { enabled: win.ready; SpringAnimation { id: springW; epsilon: 0.2 } }
    Behavior on bh { enabled: win.ready; SpringAnimation { id: springH; epsilon: 0.2 } }
    Behavior on br { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
    // The island sits a few pixels below the top edge, but the pointer thrown against the edge
    // already counts as on it.
    readonly property int gap: 6
    // How far the island has grown towards its open shape: the player inside comes in with it.
    readonly property real openHeight: idle ? 128 : (withLyrics ? 208 : 180)
    readonly property real openness: Math.max(0, Math.min(1, (bh - 36) / (openHeight - 36)))
    property real openGate: mode === "open" ? 1 : 0
    Behavior on openGate { NumberAnimation { duration: 70 } }
    readonly property real openShown: openGate * Math.pow(openness, 1.6)

    // ---- what takes the pointer: the island's shape, the bigger of now and next while it grows ----
    property real shapeArea: 0
    function pushShape(now) {
        var w = Math.round(goal.width + (mode === "compact" ? 40 : 12)), h = Math.round(goal.height + gap + 6)
        if (now || w * h >= shapeArea) {
            shrink.stop()
            hit.x = Math.round((width - w) / 2); hit.width = w; hit.height = h
            island.shape(hit.x, 0, w, h)
            shapeArea = w * h
        } else shrink.restart()
    }
    Timer { id: shrink; interval: 420; onTriggered: win.pushShape(true) }
    Component.onCompleted: { bw = goal.width; bh = goal.height; ready = true; pushShape(true); lastTrack = trackKey() }
    // The first time, the island says what it is.
    onVisibleChanged: if (visible && !s.islandHinted) hintWait.start()
    Timer { id: hintWait; interval: 1600; onTriggered: {
        win.peekCaption = "Это остров OpenMusic"; win.peekText = "Наведите на него — здесь мини-плеер"
        win.peeking = true; peekEnd.restart(); app.setSetting("islandHinted", true) } }

    // ---- a new track opens the island for a moment ----
    property string lastTrack: ""
    function trackKey() { return p.hasTrack ? p.title + "\n" + p.artist : "" }
    Connections {
        target: app
        function onPlayerChanged() {
            var key = win.trackKey()
            if (key === win.lastTrack) return
            var first = win.lastTrack === ""
            win.lastTrack = key
            if (key !== "" && !first && win.s.islandPop && win.visible) {
                win.peekCaption = "Сейчас играет"; win.peekText = Qt.binding(function() { return win.p.title + "  ·  " + win.p.artist })
                win.peeking = true; peekEnd.restart()
            }
        }
    }
    Timer { id: peekEnd; interval: 4200; onTriggered: win.peeking = false }

    // ---- the beat and the time ----
    property real clock: 0
    property real lv: 0
    property real heard: 0
    property real alive: p.playing ? 1 : 0
    Behavior on alive { NumberAnimation { duration: 420; easing.type: Easing.OutCubic } }
    readonly property bool beating: (p.playing || alive > 0.01) && !s.calm
    readonly property bool timing: mode === "open" && p.playing
    // Small, the bars are a few pixels tall and 40 steps a second is plenty; open, 60.
    Timer {
        interval: win.mode === "compact" ? 25 : 16
        repeat: true
        running: win.visible && (win.beating || win.timing)
        onTriggered: {
            win.clock = (Date.now() / 1000) % 100000
            win.lv += (island.level - win.lv) * 0.22
            if (win.timing) win.heard = np.playing ? np.positionBase + (Date.now() - np.positionAt) : np.positionBase
        }
    }
    // Where the track is: between the player's reports it runs on by the clock, so the line glides.
    onModeChanged: if (mode === "open" && p.playing) heard = np.playing ? np.positionBase + (Date.now() - np.positionAt) : np.positionBase
    readonly property real at: p.playing && heard > 0 ? Math.min(app.duration, heard) : app.position
    readonly property var speeds: [5.3, 7.9, 6.4, 9.1, 5.9]
    readonly property var phases: [0, 1.9, 3.3, 4.6, 2.5]
    function bar(i) {
        var wave = 0.5 + 0.5 * Math.sin(clock * speeds[i % 5] + phases[i % 5])
        return alive * (0.18 + 0.82 * wave * (0.3 + 0.7 * lv))
    }
    component Bars: Row {
        id: bars
        property real tall: 14
        property int count: 4
        spacing: 2.5
        Repeater {
            model: bars.count
            Rectangle {
                required property int index
                anchors.verticalCenter: parent.verticalCenter
                width: 3
                height: Math.max(3, bars.tall * win.bar(index))
                radius: 1.5
                color: win.accent
            }
        }
    }

    // ---- the line of the text being sung ----
    property string line: ""
    Timer {
        interval: 120
        repeat: true
        triggeredOnStart: true
        running: win.visible && win.mode === "open" && win.withLyrics
        onTriggered: {
            var at = (np.playing ? np.positionBase + (Date.now() - np.positionAt) : np.positionBase) + np.offsetMs
            var lines = np.lines, found = ""
            for (var i = lines.length - 1; i >= 0; i--) if (lines[i].start <= at) { found = lines[i].text; break }
            if (found !== win.line) win.line = found
        }
    }

    function timeText(ms) {
        var seconds = Math.max(0, Math.floor(ms / 1000))
        return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0")
    }

    RectangularShadow {
        anchors.fill: body
        radius: body.radius
        blur: win.mode === "compact" ? 14 : 30
        spread: -2
        offset.y: win.mode === "compact" ? 3 : 10
        color: Qt.rgba(0, 0, 0, win.mode === "compact" ? 0.4 : 0.65)
        Behavior on blur { NumberAnimation { duration: 300 } }
    }
    Rectangle {
        id: body
        // An even width keeps both sides on whole pixels, so the island grows evenly from its middle.
        width: 2 * Math.round(win.bw / 2)
        height: Math.round(win.bh)
        x: (win.width - width) / 2
        y: win.gap
        radius: Math.min(win.br, height / 2, width / 2)
        color: "#000000"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, win.mode === "compact" ? 0.08 : 0.1)
        clip: true


        // A faint glow of the cover's colour along the bottom of the open island.
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            opacity: full.opacity
            gradient: Gradient {
                GradientStop { position: 0.35; color: "transparent" }
                GradientStop { position: 1; color: Qt.rgba(win.cover.r, win.cover.g, win.cover.b, 0.22) }
            }
        }

        // ---- small, nothing plays ----
        Item {
            anchors.fill: parent
            opacity: win.mode === "compact" && win.idle ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 220 } }
            visible: opacity > 0.01
            Image { x: 8; anchors.verticalCenter: parent.verticalCenter; width: 22; height: 22; source: app.stateMap.logo
                    sourceSize: Qt.size(44, 44); smooth: true; mipmap: true }
            Text { x: 38; anchors.verticalCenter: parent.verticalCenter; text: "OpenMusic"; color: Qt.rgba(1, 1, 1, 0.7)
                   font.family: "Inter"; font.pixelSize: 13; font.weight: Font.DemiBold }
        }

        // ---- open, nothing plays ----
        Item {
            width: 400; height: 128
            anchors.horizontalCenter: parent.horizontalCenter
            opacity: win.idle ? win.openShown : 0
            scale: win.openShown > 0.985 ? 1 : 0.92 + 0.08 * win.openShown
            transformOrigin: Item.Top
            visible: opacity > 0.01
            Image { x: 22; y: 20; width: 44; height: 44; source: app.stateMap.logo; sourceSize: Qt.size(88, 88); smooth: true; mipmap: true }
            Column {
                x: 80; y: 22
                spacing: 3
                Text { text: "Ничего не играет"; color: "white"; font.family: "Inter"; font.pixelSize: 16; font.weight: Font.DemiBold }
                Text { text: "Включите трек или Мой поток"; color: Qt.rgba(1, 1, 1, 0.55); font.family: "Inter"; font.pixelSize: 13 }
            }
            Row {
                x: 22; y: 78
                spacing: 8
                PillButton { text: "Мой поток"; primary: true; onClicked: app.radioFromTaste() }
                PillButton { text: "Открыть OpenMusic"; onClicked: app.showWindow(0) }
            }
        }

        // ---- small ----
        Item {
            anchors.fill: parent
            opacity: win.mode === "compact" && !win.idle ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: win.mode === "compact" ? 200 : 90 } }
            visible: opacity > 0.01
            Art { x: 6; anchors.verticalCenter: parent.verticalCenter; width: 24; height: 24; round: 0.5; source: win.p.cover }
            Bars { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; tall: 15 }
        }

        // ---- a new track ----
        Item {
            anchors.fill: parent
            opacity: win.mode === "peek" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: win.mode === "peek" ? 240 : 90 } }
            visible: opacity > 0.01
            Art { x: 12; anchors.verticalCenter: parent.verticalCenter; width: 40; height: 40; round: 0.26; source: win.p.cover; visible: !win.idle }
            Image { x: 12; anchors.verticalCenter: parent.verticalCenter; width: 40; height: 40; visible: win.idle
                    source: app.stateMap.logo; sourceSize: Qt.size(80, 80); smooth: true; mipmap: true }
            Column {
                x: 64
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - x - 64
                spacing: 1
                Text { text: win.peekCaption; color: win.accent; font.family: "Inter"; font.pixelSize: 11; font.weight: Font.DemiBold }
                Text { width: parent.width; text: win.peekText; elide: Text.ElideRight
                       color: "white"; font.family: "Inter"; font.pixelSize: 14; font.weight: Font.DemiBold }
            }
            Bars { anchors.right: parent.right; anchors.rightMargin: 22; anchors.verticalCenter: parent.verticalCenter; tall: 20; count: 5; visible: !win.idle }
        }

        // ---- open: the small player ----
        Item {
            id: full
            width: 452
            height: win.withLyrics ? 208 : 180
            anchors.horizontalCenter: parent.horizontalCenter
            opacity: win.idle ? 0 : win.openShown
            scale: win.openShown > 0.985 ? 1 : 0.92 + 0.08 * win.openShown
            transformOrigin: Item.Top
            visible: opacity > 0.01

            Art {
                id: art
                x: 22; y: 22
                width: 66; height: 66
                round: 0.22
                source: win.p.cover
                scale: artArea.pressed ? 0.95 : artArea.containsMouse ? 1.04 : 1
                Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                MouseArea { id: artArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: island.openApp() }
            }
            Column {
                x: 104; y: 30
                width: parent.width - x - 78
                spacing: 4
                Text { width: parent.width; text: win.p.title; elide: Text.ElideRight; color: "white"
                       font.family: "Inter"; font.pixelSize: 16; font.weight: Font.DemiBold }
                Text { width: parent.width; text: win.p.artist; elide: Text.ElideRight; color: Qt.rgba(1, 1, 1, 0.55)
                       font.family: "Inter"; font.pixelSize: 13 }
            }
            Bars { anchors.right: parent.right; anchors.rightMargin: 28; y: 40; tall: 24; count: 5 }

            Text {
                id: lyric
                x: 22; y: 100
                width: parent.width - 44
                visible: win.withLyrics
                property string shown: ""
                text: shown
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
                color: Qt.rgba(1, 1, 1, 0.88)
                font.family: "Inter"; font.pixelSize: 14; font.weight: Font.Medium
                Component.onCompleted: shown = win.line
                Connections { target: win; function onLineChanged() { swap.restart() } }
                SequentialAnimation {
                    id: swap
                    NumberAnimation { target: lyric; property: "opacity"; to: 0; duration: 110 }
                    ScriptAction { script: lyric.shown = win.line }
                    NumberAnimation { target: lyric; property: "opacity"; to: 1; duration: 240; easing.type: Easing.OutCubic }
                }
            }

            Item {
                id: progress
                x: 22
                y: win.withLyrics ? 130 : 102
                width: parent.width - 44
                height: 18
                readonly property real share: app.duration > 0 ? (scrub.dragging ? scrub.dragShare : Math.min(1, win.at / app.duration)) : 0
                Text { anchors.verticalCenter: parent.verticalCenter; text: win.timeText(scrub.dragging ? scrub.dragShare * app.duration : win.at)
                       color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 11 }
                Text { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                       text: app.duration > 0 ? "−" + win.timeText(app.duration - (scrub.dragging ? scrub.dragShare * app.duration : win.at)) : ""
                       color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 11 }
                Item {
                    id: scrub
                    x: 44
                    width: parent.width - 88
                    height: parent.height
                    property bool dragging: false
                    property real dragShare: 0
                    property real hover: scrubArea.containsMouse || dragging ? 1 : 0
                    Behavior on hover { NumberAnimation { duration: 160 } }
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width
                        height: 4 + 2 * scrub.hover
                        radius: height / 2
                        color: Qt.rgba(1, 1, 1, 0.16)
                        Rectangle { width: parent.width * progress.share; height: parent.height; radius: height / 2; color: "#f4f4f4" }
                    }
                    MouseArea {
                        id: scrubArea
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: app.duration > 0
                        onPressed: (mouse) => { scrub.dragging = true; scrub.dragShare = Math.max(0, Math.min(1, (mouse.x - 4) / scrub.width)) }
                        onPositionChanged: (mouse) => { if (scrub.dragging) scrub.dragShare = Math.max(0, Math.min(1, (mouse.x - 4) / scrub.width)) }
                        onReleased: { app.seek(scrub.dragShare * app.duration); scrub.dragging = false }
                    }
                }
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                y: progress.y + 26
                spacing: 16
                IconButton { anchors.verticalCenter: parent.verticalCenter; size: 36; glyph: 18; name: win.p.liked ? "heart-filled" : "heart"; active: win.p.liked; onClicked: app.likeCurrent() }
                IconButton { anchors.verticalCenter: parent.verticalCenter; size: 38; glyph: 19; name: "previous"; onClicked: app.previous() }
                Item {
                    width: 46; height: 46
                    Rectangle {
                        anchors.centerIn: parent
                        width: 44 * (playArea.pressed ? 0.9 : playArea.containsMouse ? 1.06 : 1); height: width
                        radius: width / 2
                        color: "#f4f4f4"
                        Behavior on width { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                    }
                    Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: win.p.playing || win.p.loading ? 0 : 1
                           name: win.p.playing || win.p.loading ? "pause" : "play"; tint: "#0a0a0a"; size: 19 }
                    MouseArea { id: playArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: app.toggle() }
                }
                IconButton { anchors.verticalCenter: parent.verticalCenter; size: 38; glyph: 19; name: "next"; enabled2: win.p.canNext; onClicked: app.next() }
                IconButton { anchors.verticalCenter: parent.verticalCenter; size: 36; glyph: 18; name: "lyrics"; onClicked: island.openApp() }
            }
        }
    }

    // Takes the pointer over the whole island and the gap above it. It sits on top but only
    // watches: the buttons under it still get their hover and clicks.
    Item {
        id: hit
        z: 100
        HoverHandler {
            onHoveredChanged: {
                if (hovered) { closeWait.stop(); openWait.restart() }
                else { openWait.stop(); closeWait.restart() }
            }
        }
        TapHandler { enabled: win.mode !== "open"; onTapped: { openWait.stop(); win.over = true; win.peeking = false } }
    }
    Timer { id: openWait; interval: 60; onTriggered: { win.over = true; win.peeking = false } }
    // Leaving closes it almost at once; the short wait only forgives a pointer that slips off the edge.
    Timer { id: closeWait; interval: 90; onTriggered: win.over = false }
}
