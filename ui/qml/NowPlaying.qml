import QtQuick
import QtQuick.Effects

// The now-playing screen, drawn by the graphics card. Python (ui/now_quick.py) hands over the track,
// its cover, colours, text and loudness through the "np" object; everything that moves is animated
// here, every frame of the screen.
Rectangle {
    id: root
    color: "#07060a"

    // ---- Time: the player reports its position in uneven steps, so it runs on here every frame ----
    property real pos: 0
    property real t: 0
    property real lv: 0
    property real bs: 0
    readonly property real now: pos + np.offsetMs
    // The lines, kept as a list of this screen's own: asking np for them makes a new copy each time.
    property var lines: np.lines
    // A line lights up a little before it is sung, so the change is half done when the voice comes in.
    readonly property real lead: np.synced ? 200 : 0
    readonly property int current: currentLine(now + lead)
    // The clip shows only text with real timing.
    readonly property int clipCurrent: np.synced ? current : -1

    // How far through its current line the track is, 0…1.
    function progressAt(at) {
        var line = current >= 0 && current < lines.length ? lines[current] : null
        if (!line || line.end <= line.start) return 0
        return Math.max(0, Math.min(1, (at - line.start) / (line.end - line.start)))
    }
    function currentLine(at) {
        var lines = root.lines
        if (!(np.synced || np.rough) || !lines || lines.length === 0) return -1
        var found = -1
        for (var i = 0; i < lines.length; i++) {
            if (lines[i].start <= at) found = i
            else break
        }
        return found
    }
    // 0..1 through a stretch without singing (before the first line or a long break), else -1.
    function waiting(at) {
        var lines = root.lines
        if (!np.synced || !lines || lines.length === 0) return -1
        var i = root.current
        var start, end
        if (i < 0) { start = 0; end = lines[0].start }
        else {
            if (i + 1 >= lines.length) return -1
            start = lines[i].end; end = lines[i + 1].start
            if (end - start < 3500 || at < start) return -1
        }
        if (end - start < 1500) return -1
        return Math.max(0, Math.min(1, (at - start) / (end - start)))
    }

    // 60 frames a second, not the monitor's 240: smooth to the eye at a quarter of the work.
    Timer {
        interval: 16
        repeat: true
        running: root.visible
        property real last: Date.now()
        property real frameTime: 0.016
        onRunningChanged: last = Date.now()
        onTriggered: {
            var stamp = Date.now()
            frameTime = Math.min(0.1, (stamp - last) / 1000)
            last = stamp
            var dt = frameTime * 1000
            var reported = np.playing ? np.positionBase + (Date.now() - np.positionAt) : np.positionBase
            var predicted = root.pos + (np.playing ? dt : 0)
            if (Math.abs(reported - predicted) > 300 || !np.playing) root.pos = reported
            else root.pos = predicted + (reported - predicted) * 0.08
            if (!app.settingsMap.calm) root.t += frameTime
            root.lv += ((np.playing ? np.level : 0) - root.lv) * Math.min(1, frameTime * 12)
            root.bs += ((np.playing ? np.bass : 0) - root.bs) * Math.min(1, frameTime * (np.bass > root.bs ? 18 : 6))
            if (np.rough && lyricsBox.visible) { list.aim(); root.settled ? list.step(Math.min(0.05, frameTime)) : list.arrive() }
        }
    }

    // Layout changes animate only once the screen has settled, so it never slides in from nowhere.
    property bool settled: false
    Timer { interval: 800; running: true; onTriggered: root.settled = true }

    // ---- Layout: the cover is big on the left with the text beside it, or small in the corner ----
    readonly property bool clipMode: np.mode === "clip"
    property real coverSize: clipMode ? Math.max(90, Math.min(170, height * 0.15)) : Math.max(240, Math.min(620, Math.min(height * 0.5, width * 0.3)))
    property real coverX: clipMode ? width * 0.04 : Math.max(40, Math.min(140, width * 0.07))
    property real coverY: clipMode ? height * 0.05 : (height - coverSize - 170) / 2
    Behavior on coverSize { enabled: root.settled; NumberAnimation { duration: 750; easing.type: Easing.OutCubic } }
    Behavior on coverX { enabled: root.settled; NumberAnimation { duration: 750; easing.type: Easing.OutCubic } }
    Behavior on coverY { enabled: root.settled; NumberAnimation { duration: 750; easing.type: Easing.OutCubic } }
    readonly property real lyricPx: Math.max(20, Math.min(84, Math.min(height * 0.045, width * 0.028) * np.textScale))
    readonly property real clipPx: Math.max(40, Math.min(118, Math.min(height * 0.088, width * 0.056)))
    onWidthChanged: np.layout(width * 0.86, clipPx)
    onClipPxChanged: np.layout(width * 0.86, clipPx)

    // ---- Colours, eased from one cover to the next ----
    property color col0: np.colours[0]
    property color col1: np.colours[1]
    property color col2: np.colours[2]
    property color col3: np.colours[3]
    property color mood: np.mood
    Behavior on col0 { ColorAnimation { duration: 1600 } }
    Behavior on col1 { ColorAnimation { duration: 1600 } }
    Behavior on col2 { ColorAnimation { duration: 1600 } }
    Behavior on col3 { ColorAnimation { duration: 1600 } }
    Behavior on mood { ColorAnimation { duration: 1600 } }

    ShaderEffect {
        anchors.fill: parent
        property real time: root.t
        property real bass: root.bs
        property real aspect: width / Math.max(1, height)
        property color c0: root.col0
        property color c1: root.col1
        property color c2: root.col2
        property color c3: root.col3
        property color mood: root.mood
        property vector4d spot: Qt.vector4d((root.coverX + root.coverSize / 2) / Math.max(1, width),
                                            (root.coverY + root.coverSize / 2) / Math.max(1, height),
                                            root.coverSize / Math.max(1, width) * 1.25, np.hasTrack ? 0.9 : 0)
        fragmentShader: "mesh.frag.qsb"
    }

    // The cover itself, blown up and blurred, gives the field the texture of the artwork.
    Item {
        id: smear
        anchors.fill: parent
        visible: false
        FadeImage {
            width: parent.width * 1.3
            height: parent.height * 1.3
            x: -parent.width * 0.15 + Math.sin(root.t * 0.05) * 40
            y: -parent.height * 0.15 + Math.cos(root.t * 0.037) * 30
            source: np.cover
            duration: 1400
        }
    }
    MultiEffect {
        anchors.fill: parent
        source: smear
        blurEnabled: true
        blur: 1.0
        blurMax: 64
        saturation: 0.25
        opacity: np.hasTrack ? 0.3 : 0
        Behavior on opacity { NumberAnimation { duration: 800 } }
    }

    // ---- The ring of the logo behind the cover, turning, swelling with the loudness ----
    Item {
        id: halo
        visible: np.hasTrack
        width: root.coverSize * 1.75
        height: width
        x: root.coverX + root.coverSize / 2 - width / 2
        y: root.coverY + root.coverSize / 2 - height / 2
        opacity: 0.45 + 0.45 * root.lv
        scale: 1 + 0.05 * root.lv
        transform: [
            Scale { origin.x: halo.width / 2; origin.y: halo.height / 2; yScale: np.ring.squash },
            Rotation { origin.x: halo.width / 2; origin.y: halo.height / 2; angle: np.ring.tilt }
        ]
        Image { anchors.fill: parent; source: np.ring.band; smooth: true; mipmap: true; rotation: np.ring.phase + root.t * np.ring.speed }
        Image { anchors.fill: parent; source: np.ring.edge; smooth: true; mipmap: true; rotation: np.ring.phase * 0.5 + root.t * np.ring.speed * 0.35 }
    }

    // ---- The cover: a soft shadow, rounded corners, breathing with the bass ----
    Item {
        id: cover
        x: root.coverX
        y: root.coverY
        width: root.coverSize
        height: root.coverSize
        scale: 1 + 0.035 * root.bs
        visible: np.hasTrack
        Rectangle {
            id: shadowShape
            anchors.fill: parent
            anchors.topMargin: parent.height * 0.08
            radius: parent.width * 0.07
            color: "black"
            visible: false
        }
        MultiEffect {
            anchors.fill: shadowShape
            source: shadowShape
            blurEnabled: true
            blur: 1.0
            blurMax: 64
            opacity: 0.75
            autoPaddingEnabled: true
        }
        FadeImage { id: art; anchors.fill: parent; source: np.cover; visible: false }
        Rectangle { id: corners; anchors.fill: parent; radius: parent.width * 0.07; visible: false; layer.enabled: true }
        MultiEffect {
            anchors.fill: parent
            source: art
            maskEnabled: true
            maskSource: corners
        }
        Rectangle { anchors.fill: parent; radius: parent.width * 0.07; color: "transparent"; border.color: Qt.rgba(1, 1, 1, 0.14); border.width: 1 }
    }

    // ---- Title, artist, bars ----
    Item {
        id: info
        x: root.clipMode ? root.coverX + root.coverSize + 24 : root.coverX
        y: root.clipMode ? root.coverY + root.coverSize * 0.18 : root.coverY + root.coverSize + 28
        width: root.clipMode ? root.width * 0.4 : root.coverSize
        height: column.implicitHeight
        Behavior on x { enabled: root.settled; NumberAnimation { duration: 750; easing.type: Easing.OutCubic } }
        Behavior on y { enabled: root.settled; NumberAnimation { duration: 750; easing.type: Easing.OutCubic } }
        Column {
            id: column
            width: parent.width
            spacing: 6
            Text {
                text: "СЕЙЧАС ИГРАЕТ"
                color: Qt.rgba(1, 1, 1, 0.55)
                font.family: "Inter"; font.pixelSize: 11; font.weight: Font.Bold; font.letterSpacing: 2
            }
            Text {
                id: title
                width: parent.width
                text: np.title
                elide: Text.ElideRight
                color: "white"
                font.family: "Inter Display"; font.weight: Font.ExtraBold
                font.pixelSize: root.clipMode ? 30 : Math.max(26, Math.min(40, root.coverSize * 0.07))
                property real appear: 1
                opacity: appear
                transform: Translate { y: (1 - title.appear) * 14 }
                layer.enabled: appear < 0.999
                layer.effect: MultiEffect { blurEnabled: true; blurMax: 32; blur: 1 - title.appear; autoPaddingEnabled: true }
                onTextChanged: { appear = 0; titleIn.restart() }
                NumberAnimation { id: titleIn; target: title; property: "appear"; to: 1; duration: 900; easing.type: Easing.OutCubic }
            }
            Row {
                spacing: 10
                Item {
                    width: np.artistPhoto ? 26 : 0
                    height: 26
                    visible: np.artistPhoto !== ""
                    Image { id: photo; anchors.fill: parent; source: np.artistPhoto; visible: false; smooth: true; fillMode: Image.PreserveAspectCrop }
                    Rectangle { id: round; anchors.fill: parent; radius: width / 2; visible: false; layer.enabled: true }
                    MultiEffect { anchors.fill: parent; source: photo; maskEnabled: true; maskSource: round }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: np.artist
                    color: Qt.rgba(1, 1, 1, npArtist.containsMouse ? 0.95 : 0.62)
                    font.family: "Inter"; font.pixelSize: 15; font.weight: Font.Medium
                    font.underline: npArtist.containsMouse
                    MouseArea { id: npArtist; anchors.fill: parent; enabled: np.artist !== ""; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: app.showArtist(np.artist) }
                }
            }
        }
    }

    Row {
        id: bars
        visible: np.hasTrack
        readonly property int count: root.clipMode ? 48 : 36
        width: root.clipMode ? root.width * 0.4 : root.coverSize
        height: root.clipMode ? 46 : Math.max(36, Math.min(70, root.coverSize * 0.13))
        x: root.clipMode ? (root.width - width) / 2 : root.coverX
        y: root.clipMode ? root.height - height - 30 : info.y + info.height + 26
        spacing: width / count * 0.45
        Behavior on y { enabled: root.settled; NumberAnimation { duration: 750; easing.type: Easing.OutCubic } }
        Repeater {
            model: bars.count
            Rectangle {
                readonly property real spread: 0.5 + 0.5 * Math.sin(index * 1.7 + root.t * 3.1) * Math.sin(index * 0.6 - root.t * 1.9)
                readonly property real weight: index % 3 === 0 ? root.bs : root.lv
                readonly property real amount: np.playing ? 0.12 + 0.88 * Math.pow(weight, 0.7) : 0.05
                width: bars.width / bars.count * 0.55
                height: 3 + (bars.height - 3) * Math.min(1, amount * (0.3 + 0.7 * spread))
                anchors.verticalCenter: parent.verticalCenter
                radius: width / 2
                color: index % 2 ? Qt.rgba(root.mood.r, root.mood.g, root.mood.b, 0.45 + 0.5 * amount) : Qt.rgba(1, 1, 1, 0.45 + 0.5 * amount)
            }
        }
    }

    // ---- The text as a list ----
    // Every line is laid out once, at its full size: the line being sung grows by scale, not by
    // font size, so nothing wraps anew or jumps while it changes. The list moves on a spring of
    // its own, which keeps its speed when the next line comes before it has settled, and the
    // lines further down follow a moment later, like the cars of a train.
    // The list is not clipped to a box: the glow and blur of its lines would end in a hard line at
    // the sides. It sits in a wider frame instead, faded out softly at the top and the bottom.
    readonly property real lyricsPad: 140
    Item {
        id: lyricsBox
        visible: opacity > 0.01
        opacity: root.clipMode ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 500 } }
        x: root.coverX + root.coverSize + root.width * 0.06 - root.lyricsPad
        y: 60
        width: root.width - (root.coverX + root.coverSize + root.width * 0.06) - root.width * 0.05 + root.lyricsPad * 2
        height: root.height - 60
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: fade
            maskThresholdMin: 0.0
            maskSpreadAtMin: 1.0
            maskThresholdMax: 1.0
            maskSpreadAtMax: 0.0
        }
        // The wheel looks ahead or back in the text; a few seconds later it returns to the music.
        WheelHandler {
            target: null
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: (event) => {
                var pad = event.pixelDelta.y !== 0 && event.phase !== Qt.NoScrollPhase
                var by = pad ? -event.pixelDelta.y : -event.angleDelta.y / 120 * root.lyricPx * 2.4
                var most = Math.max(0, rows.height - root.lyricPx * 2)
                list.nudge = Math.max(-list.goal, Math.min(most - list.goal, list.nudge + by))
                nudgeBack.restart()
            }
        }
        Timer { id: nudgeBack; interval: 4000; onTriggered: list.nudge = 0 }
    Item {
        id: list
        x: root.lyricsPad
        width: lyricsBox.width - root.lyricsPad * 2
        height: lyricsBox.height
        // The line being sung rests this far down the screen.
        readonly property real anchor: Math.round(height * 0.36)
        property real goal: 0           // where that line starts in the column
        property real nudge: 0          // what the wheel has added
        readonly property real target: goal + nudge
        property real scroll: 0
        property real speed: 0
        readonly property bool moving: Math.abs(target - scroll) > 0.4 || Math.abs(speed) > 3

        function aim() {
            var item = root.current >= 0 ? repeater.itemAt(root.current) : null
            if (!item) goal = 0
            // Text without timing glides on through each line; timed text steps from line to line.
            else if (np.rough) goal = item.y + (item.height + rows.spacing) * root.progressAt(root.now)
            else goal = Math.round(item.y)
        }
        // A critically damped spring: it sets off gently, never swings past, and arrives in about 0.7 s.
        function step(dt) {
            var stiff = 7.5
            speed += (stiff * stiff * (target - scroll) - 2 * stiff * speed) * dt
            scroll += speed * dt
            if (!moving) arrive()
        }
        function arrive() { scroll = target; speed = 0 }
        function jump() { aim(); arrive() }
        Component.onCompleted: jump()
        onVisibleChanged: if (visible) jump()
        Connections {
            target: root
            function onCurrentChanged() { list.aim() }
            function onLinesChanged() { list.nudge = 0; Qt.callLater(list.jump) }
            function onVisibleChanged() { if (root.visible) Qt.callLater(list.jump) }
        }
        // Timed text moves in short runs, drawn on every frame of the screen. (Text without timing
        // creeps all the time; the 60-a-second clock above moves it.)
        FrameAnimation {
            running: root.visible && lyricsBox.visible && !np.rough && list.moving
            onTriggered: root.settled ? list.step(Math.min(0.05, frameTime)) : list.arrive()
        }

        Column {
            id: rows
            width: list.width
            y: list.anchor - list.scroll
            spacing: Math.round(root.lyricPx * 0.36)
            onHeightChanged: { list.aim(); if (!root.settled) list.arrive() }
            // Before the first line: three dots that fill while the intro plays.
            Item {
                width: list.width
                height: Math.round(root.lyricPx * 1.3)
                Row {
                    y: parent.height * 0.25
                    spacing: root.lyricPx * 0.35
                    opacity: root.waiting(root.now) >= 0 && root.current < 0 ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 400 } }
                    Repeater {
                        model: 3
                        Rectangle {
                            readonly property real lit: Math.max(0, Math.min(1, root.waiting(root.now) * 3 - index))
                            width: root.lyricPx * 0.32 * (0.7 + 0.3 * lit) * (1 + 0.12 * Math.sin(root.t * 4 + index))
                            height: width
                            radius: width / 2
                            color: Qt.rgba(1, 1, 1, 0.25 + 0.75 * lit)
                        }
                    }
                }
            }
            Repeater {
                id: repeater
                model: root.lines
                delegate: Item {
                    id: row
                    required property int index
                    required property var modelData
                    width: list.width
                    height: line.implicitHeight
                    readonly property bool isCurrent: index === root.current
                    readonly property int distance: Math.abs(index - Math.max(0, root.current))
                    // Only the lines on the screen, and a little past it, are drawn.
                    readonly property real upper: rows.y + y
                    readonly property bool shown: upper + height > -260 && upper < list.height + 260
                    // Lit, 0…1. It rises softly and settles slowly; with the head start of root.lead
                    // the line is half lit when its first word is sung.
                    property real emph: isCurrent && np.synced ? 1 : 0
                    Behavior on emph { NumberAnimation { duration: 620; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.25, 0.1, 0.25, 1.0, 1.0, 1.0] } }
                    // How far from the line being sung, as blur; eased, so the lines around do not snap.
                    property real far: np.synced ? Math.min(0.28, distance * 0.06) : 0
                    Behavior on far { NumberAnimation { duration: 620; easing.type: Easing.InOutSine } }
                    // Lines further down set off a moment later.
                    transform: Translate { y: Math.max(-60, Math.min(60, list.speed * 0.022 * Math.max(-2, Math.min(7, row.index - root.current)))) }
                    Text {
                        id: line
                        width: parent.width * 0.96
                        text: row.modelData.text
                        wrapMode: Text.WordWrap
                        horizontalAlignment: np.centered ? Text.AlignHCenter : Text.AlignLeft
                        color: "white"
                        font.family: "Inter Display"
                        font.weight: Font.ExtraBold
                        font.pixelSize: Math.round(root.lyricPx)
                        visible: false
                    }
                    // The effect is its own item with padding, so the glow and the blur spill past the
                    // letters instead of being cut off in a box at the edge of the text.
                    Loader {
                        anchors.fill: line
                        active: row.shown
                        transformOrigin: np.centered ? Item.Center : Item.Left
                        scale: 0.86 + 0.14 * row.emph
                        opacity: np.synced ? (row.index < root.current ? 0.5 : 0.34) + (1 - (row.index < root.current ? 0.5 : 0.34)) * row.emph
                                           : 0.85
                        sourceComponent: MultiEffect {
                            source: line
                            // Room for the glow on every side, set by hand: the automatic padding leaves the
                            // glow of a long line cut off in a straight edge after its last word.
                            autoPaddingEnabled: false
                            paddingRect: Qt.rect(110, 80, 110, 80)
                            blurEnabled: true
                            blurMax: 32
                            blur: row.far * (1 - row.emph)
                            shadowEnabled: true
                            shadowColor: root.mood
                            shadowBlur: 1.0
                            shadowScale: 1.0
                            shadowOpacity: row.emph * (0.6 + 0.4 * root.bs)
                            shadowHorizontalOffset: 0
                            shadowVerticalOffset: 0
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: np.synced
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { list.nudge = 0; np.seek(row.modelData.start) }
                    }
                }
            }
        }
    }
    }
    Item {
        id: fade
        width: lyricsBox.width
        height: lyricsBox.height
        visible: false
        layer.enabled: true
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.1; color: "white" }
                GradientStop { position: 0.86; color: "white" }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
    }

    // ---- The clip: one huge line in the middle ----
    Item {
        id: clipView
        visible: opacity > 0.01
        opacity: root.clipMode ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 500 } }
        anchors.fill: parent
        property int shown: -2
        property bool first: true
        readonly property int wanted: root.clipCurrent
        onWantedChanged: {
            if (wanted === shown) return
            shown = wanted
            if (first) { lineA.rows = rowsOf(wanted); lineA.lineStart = startOf(wanted); lineA.active = true; lineB.active = false }
            else { lineB.rows = rowsOf(wanted); lineB.lineStart = startOf(wanted); lineB.active = true; lineA.active = false }
            first = !first
        }
        function rowsOf(i) { return i >= 0 && np.clipRows && i < np.clipRows.length ? np.clipRows[i] : [] }
        function startOf(i) { return i >= 0 && root.lines && i < root.lines.length ? root.lines[i].start : 0 }

        // Before the first line: the title itself, huge, as the intro card.
        Column {
            anchors.centerIn: parent
            spacing: 14
            opacity: root.clipCurrent < 0 ? 1 : 0
            scale: root.clipCurrent < 0 ? 1 : 0.92
            Behavior on opacity { NumberAnimation { duration: 600 } }
            Behavior on scale { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(implicitWidth, root.width * 0.86)
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: np.hasTrack ? np.title : "OpenMusic"
                color: "white"
                font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: root.clipPx
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: np.message !== "" ? np.message : np.artist
                color: Qt.rgba(1, 1, 1, 0.6)
                font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: root.clipPx * 0.34
            }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: root.clipPx * 0.22
                opacity: root.waiting(root.now) >= 0 ? 1 : 0
                Repeater {
                    model: 3
                    Rectangle {
                        readonly property real lit: Math.max(0, Math.min(1, root.waiting(root.now) * 3 - index))
                        width: root.clipPx * 0.16 * (0.7 + 0.3 * lit) * (1 + 0.12 * Math.sin(root.t * 4 + index))
                        height: width
                        radius: width / 2
                        color: Qt.rgba(1, 1, 1, 0.25 + 0.75 * lit)
                    }
                }
            }
        }
        ClipLine { id: lineA; anchors.fill: parent; anchors.bottomMargin: root.height * 0.08; now: root.now; px: root.clipPx }
        ClipLine { id: lineB; anchors.fill: parent; anchors.bottomMargin: root.height * 0.08; now: root.now; px: root.clipPx }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.68
            width: root.width * 0.8
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: root.clipCurrent >= 0 && root.lines && root.clipCurrent + 1 < root.lines.length ? root.lines[root.clipCurrent + 1].text : ""
            color: Qt.rgba(1, 1, 1, 0.32)
            font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: root.clipPx * 0.34
        }
    }

    // Shown in list mode when there is no text to scroll.
    Text {
        visible: !root.clipMode && (!root.lines || root.lines.length === 0)
        x: list.x
        width: list.width
        anchors.verticalCenter: parent.verticalCenter
        wrapMode: Text.WordWrap
        text: np.message
        color: Qt.rgba(1, 1, 1, 0.6)
        font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: root.lyricPx * 0.75
    }

    // ---- Controls: move the text against the music, switch the mode ----
    Row {
        anchors.right: parent.right
        anchors.rightMargin: 26
        y: 22
        spacing: 8
        PillButton { text: "−"; onClicked: np.shift(-250) }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: 150
            horizontalAlignment: Text.AlignHCenter
            text: np.offsetText
            color: Qt.rgba(1, 1, 1, 0.5)
            font.family: "Inter"; font.pixelSize: 12
        }
        PillButton { text: "+"; onClicked: np.shift(250) }
        Item { width: 10; height: 1 }
        PillButton { text: "A−"; visible: !root.clipMode; onClicked: np.scaleText(-0.1) }
        PillButton { text: "A+"; visible: !root.clipMode; onClicked: np.scaleText(0.1) }
        PillButton { text: np.centered ? "По центру" : "Слева"; visible: !root.clipMode; onClicked: np.toggleAlign() }
        Item { width: 10; height: 1 }
        PillButton { text: "Текст"; checked: !root.clipMode; onClicked: np.setMode("list") }
        PillButton { text: "Клип"; checked: root.clipMode; onClicked: np.setMode("clip") }
    }
    // What kind of timing the text has, when it is not exact.
    Text {
        x: root.coverX
        y: bars.y + bars.height + 22
        width: root.coverSize
        wrapMode: Text.WordWrap
        visible: opacity > 0.01
        opacity: np.note !== "" && !root.clipMode ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 400 } }
        text: np.note
        color: Qt.rgba(1, 1, 1, 0.45)
        font.family: "Inter"; font.pixelSize: 12
    }
}
