import QtQuick
import QtQuick.Controls

// "Звук", three tabs that slide into each other.
//   Сцены — ready-made sounds, one press each.
//   Эквалайзер — a curve to draw over a live analyser, on 5, 10, 15 or 31 bands; presets by group
//   and of one's own; automatic fitting to the track; preamp, bass, clarity, low and high cut.
//   Эффекты — space, 8D, echo, stereo; vinyl, tape, lo-fi, cassette wow, chorus, flanger, voice
//   removal; compressor, even loudness, speed.
Sheet {
    id: panel
    width: 1000
    readonly property var s: app.stateMap.sound
    property var bands: s.bands || [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    readonly property var freqs: s.freqs && s.freqs.length === bands.length ? s.freqs : [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    readonly property int count: bands.length
    property var shown: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    property int dragging: -1
    property int near: -1
    property int tab: 0
    property int group: 0
    readonly property var groups: app.stateMap.presetGroups || []
    readonly property bool custom: (s.custom || []).indexOf(s.preset) >= 0
    onBandsChanged: {
        if (dragging >= 0) return
        // Another number of bands is another drawing: it is shown at once, not glided into.
        if (shown.length !== bands.length) { shown = bands.slice(); curve.requestPaint() }
        else glideTo(bands)
    }
    onSChanged: if (opened) curve.requestPaint()
    function glideTo(target) {
        var from = shown.slice()
        glide.from = from; glide.target = target.slice(); glide.restart()
    }
    function db(value) { return (value > 0 ? "+" : value < 0 ? "−" : "") + Math.abs(value).toFixed(1).replace(".", ",") + " дБ" }
    function percent(value) { return Math.round(value * 100) + "%" }
    function amount(value) { return value < 0.005 ? "выкл" : percent(value) }
    function hertz(value) { return value >= 1000 ? (value / 1000).toFixed(value >= 10000 ? 0 : 1).replace(".", ",") + " кГц" : Math.round(value) + " Гц" }
    // The curve between its points, as the sound engine reads it: straight lines in pitch.
    function between(values, f) {
        var fr = panel.freqs, n = Math.min(fr.length, values.length)
        if (n < 1) return 0
        if (f <= fr[0]) return values[0]
        if (f >= fr[n - 1]) return values[n - 1]
        for (var i = 1; i < n; i++) {
            if (f <= fr[i]) {
                var t = Math.log(f / fr[i - 1]) / Math.log(fr[i] / fr[i - 1])
                return values[i - 1] + (values[i] - values[i - 1]) * t
            }
        }
        return values[n - 1]
    }
    QtObject {
        id: glide
        property var from: []
        property var target: []
        property real t: 1
        readonly property bool running: anim.running
        function restart() { anim.restart() }
    }
    NumberAnimation { id: anim; target: glide; property: "t"; from: 0; to: 1; duration: 420 }

    // The analyser: what plays, in 48 bands, rising fast and falling slowly.
    property var levels: []
    Connections {
        target: app
        enabled: panel.opened
        function onSpectrumChanged() {
            var now = app.spectrum, before = panel.levels, next = []
            for (var i = 0; i < now.length; i++) {
                var was = before[i] || 0, v = now[i]
                next.push(v > was ? was + (v - was) * 0.65 : was * 0.84 + v * 0.16)
            }
            panel.levels = next
        }
    }
    onOpened: {
        shown = bands.slice(); curve.requestPaint(); app.soundWatch(true)
        // The group of the preset in use is the one shown.
        for (var g = 0; g < groups.length; g++) if (groups[g].presets.indexOf(s.preset) >= 0) group = g
    }
    onClosed: { app.soundWatch(false); levels = [] }

    component Card: Rectangle {
        id: card
        default property alias content: inner.data
        property string title
        property string text: ""
        property string value: ""
        height: 128
        radius: 16
        color: Qt.rgba(1, 1, 1, 0.045)
        border.color: Qt.rgba(1, 1, 1, 0.05)
        Text { x: 16; y: 14; text: card.title; color: "white"; font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15 }
        Text { anchors.right: parent.right; anchors.rightMargin: card.switchable ? 74 : 16; y: 15; text: card.value; color: Qt.rgba(1, 1, 1, 0.6); font.family: "Inter"; font.pixelSize: 13 }
        Text { x: 16; y: 36; width: parent.width - 32 - (card.switchable ? 62 : 0); text: card.text; visible: text !== ""; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
               color: Qt.rgba(1, 1, 1, 0.48); font.family: "Inter"; font.pixelSize: 12 }
        // A card with a switch takes a click anywhere; what is inside it (a slider) stays on top.
        property bool switchable: false
        property bool on: false
        signal flipped()
        MouseArea { id: swArea; anchors.fill: parent; enabled: card.switchable; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: card.flipped() }
        Toggle { visible: card.switchable; anchors.right: parent.right; anchors.rightMargin: 16; y: 12; checked: card.on; hot: swArea.containsMouse }
        Item { id: inner; z: 3; x: 16; y: 70; width: parent.width - 32; height: parent.height - 80 }
    }
    // A card with one slider for one setting of the sound, 0 (off) to 1.
    component Dial: Card {
        id: dial
        property string key
        readonly property real v: panel.s[key] || 0
        value: panel.amount(v)
        SoftSlider { y: 10; width: parent.width; from: 0; to: 1; value: dial.v; onMoved: app.soundSet(dial.key, value < 0.02 ? 0.0 : value) }
    }
    component Heading: Text {
        width: parent ? parent.width : 0
        height: 30
        verticalAlignment: Text.AlignBottom
        color: Qt.rgba(1, 1, 1, 0.5)
        font.family: "Inter"; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 1.6
    }
    // A scene: its name and what it does, lit when it is the one playing.
    component SceneCard: Rectangle {
        id: sc
        property string name
        property string about
        readonly property bool on: panel.s.scene === name
        radius: 16
        color: on ? (scArea.containsMouse ? "#ffffff" : "#ececec") : Qt.rgba(1, 1, 1, scArea.containsMouse ? 0.11 : 0.045)
        border.color: Qt.rgba(1, 1, 1, on ? 0 : scArea.containsMouse ? 0.3 : 0.06)
        scale: scArea.pressed ? 0.97 : 1
        Behavior on color { ColorAnimation { duration: 200 } }
        Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        Text { x: 16; y: 12; width: parent.width - 32; elide: Text.ElideRight; text: sc.name; color: sc.on ? "#0a0a0a" : "white"
               font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15; Behavior on color { ColorAnimation { duration: 200 } } }
        Text { x: 16; y: 35; width: parent.width - 32; elide: Text.ElideRight; text: sc.about
               color: sc.on ? Qt.rgba(0, 0, 0, 0.6) : Qt.rgba(1, 1, 1, 0.48); font.family: "Inter"; font.pixelSize: 12
               Behavior on color { ColorAnimation { duration: 200 } } }
        MouseArea { id: scArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: app.soundScene(sc.name) }
    }

    contentItem: Column {
        spacing: 14
        Item {
            width: parent.width; height: 40
            Text { text: "Звук"; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 28 }
            // ---- the tabs ----
            Rectangle {
                id: tabs
                x: 96
                width: 390; height: 40; radius: 20
                color: Qt.rgba(1, 1, 1, 0.06)
                Rectangle {
                    width: parent.width / 3 - 4; height: parent.height - 8; radius: height / 2; y: 4
                    x: 4 + panel.tab * (parent.width - 4) / 3
                    color: "#f4f4f4"
                    Behavior on x { SpringAnimation { spring: 4.5; damping: 0.42; epsilon: 0.2 } }
                }
                Repeater {
                    model: ["Сцены", "Эквалайзер", "Эффекты"]
                    Item {
                        x: index * tabs.width / 3; width: tabs.width / 3; height: tabs.height
                        Text { anchors.centerIn: parent; text: modelData; font.family: "Inter"; font.pixelSize: 14; font.weight: Font.DemiBold
                               color: panel.tab === index ? "#0a0a0a" : Qt.rgba(1, 1, 1, tabArea.containsMouse ? 0.95 : 0.65)
                               Behavior on color { ColorAnimation { duration: 200 } } }
                        MouseArea { id: tabArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: panel.tab = index }
                    }
                }
            }
            Row {
                anchors.right: parent.right
                spacing: 8
                PillButton { anchors.verticalCenter: parent.verticalCenter; text: panel.s.enabled === false ? "Эффекты выключены" : "Эффекты включены"
                             checked: panel.s.enabled !== false; onClicked: app.soundSet("enabled", panel.s.enabled === false) }
                PillButton { anchors.verticalCenter: parent.verticalCenter; text: "Сбросить всё"; onClicked: app.soundReset() }
                IconButton { name: "close"; onClicked: panel.close() }
            }
        }
        Text { visible: !panel.s.available; width: parent.width; wrapMode: Text.WordWrap; color: Qt.rgba(1, 1, 1, 0.6); font.family: "Inter"; font.pixelSize: 14
               text: "Для эффектов нужен Python-пакет numpy (pacman -S python-numpy), затем перезапустите OpenMusic." }

        Item {
            id: pages
            width: parent.width
            height: 474
            clip: true
            property real slide: panel.tab
            Behavior on slide { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }
            function shift(index) { return (index - slide) * 60 }
            function shade(index) { return Math.max(0, 1 - Math.abs(index - slide) * 1.6) }

            // ---- scenes ----
            Grid {
                id: scenes
                width: parent.width
                columns: 4
                spacing: 10
                x: pages.shift(0)
                opacity: pages.shade(0)
                visible: opacity > 0.01
                Repeater {
                    model: app.stateMap.scenes
                    SceneCard { width: (scenes.width - 30) / 4; height: 62; name: modelData.name; about: modelData.about }
                }
            }

            // ---- equalizer ----
            Column {
                id: eqPage
                width: parent.width
                spacing: 10
                x: pages.shift(1)
                opacity: pages.shade(1)
                visible: opacity > 0.01
                Item {
                    width: parent.width; height: 34
                    Row {
                        spacing: 6
                        Repeater { model: panel.groups; PillButton { text: modelData.name; checked: panel.group === index; onClicked: panel.group = index } }
                    }
                    Row {
                        anchors.right: parent.right
                        spacing: 6
                        PillButton { visible: panel.custom; text: "Удалить «" + panel.s.preset + "»"; onClicked: app.soundDeletePreset(panel.s.preset) }
                        PillButton { text: "+ Сохранить как…"; onClicked: app.askPresetName() }
                    }
                }
                Flow {
                    width: parent.width; height: 74; spacing: 6; clip: true
                    Repeater {
                        model: panel.groups.length > panel.group ? panel.groups[panel.group].presets : []
                        PillButton { text: modelData; checked: panel.s.preset === modelData; onClicked: app.soundPreset(modelData) }
                    }
                }
                Item {
                    width: parent.width; height: 34
                    Row {
                        spacing: 6
                        Text { height: 34; verticalAlignment: Text.AlignVCenter; text: "Полосы  "; color: Qt.rgba(1, 1, 1, 0.5); font.family: "Inter"; font.pixelSize: 13 }
                        Repeater { model: [5, 10, 15, 31]; PillButton { text: String(modelData); checked: panel.count === modelData; onClicked: app.soundLayout(modelData) } }
                    }
                    Row {
                        anchors.right: parent.right
                        spacing: 6
                        PillButton { text: "Авто — под этот трек"; checked: panel.s.preset === "Авто"; onClicked: app.soundAuto() }
                        PillButton { text: "Сгладить"; onClicked: {
                            var v = panel.bands, out = []
                            for (var i = 0; i < v.length; i++) out.push(Math.round((v[Math.max(0, i - 1)] + 2 * v[i] + v[Math.min(v.length - 1, i + 1)]) / 4 * 2) / 2)
                            app.soundBands(out) } }
                        PillButton { text: "Обнулить"; onClicked: { var out = []; for (var i = 0; i < panel.count; i++) out.push(0); app.soundBands(out) } }
                    }
                }
                Item {
                    width: parent.width
                    height: 190
                    // The analyser behind the curve, on the same scale of pitch.
                    Repeater {
                        model: 48
                        Rectangle {
                            readonly property real level: panel.levels[index] || 0
                            readonly property real from: curve.fx(30 * Math.pow(16000 / 30, index / 48))
                            readonly property real to: curve.fx(30 * Math.pow(16000 / 30, (index + 1) / 48))
                            x: from + 1
                            width: Math.max(2, to - from - 3)
                            height: Math.max(0, level * curve.ch)
                            y: curve.ty + curve.ch - height
                            radius: 2
                            color: Qt.rgba(1, 1, 1, 0.05 + 0.1 * level)
                        }
                    }
                Canvas {
                    id: curve
                    width: parent.width
                    height: 190
                    readonly property real lx: 40
                    readonly property real ty: 12
                    readonly property real cw: width - 56
                    readonly property real ch: height - 40
                    // Pitch runs from 20 Hz at the left to 20 kHz at the right, evenly by octaves.
                    function fx(f) { return lx + cw * Math.log(Math.max(20, Math.min(20000, f)) / 20) / Math.log(1000) }
                    function px(i) { return fx(panel.freqs[i]) }
                    function py(v) { return ty + ch / 2 - Math.max(-13.5, Math.min(13.5, v)) / 12 * ch / 2 }
                    function trace(c, v) {
                        var n = v.length
                        c.beginPath(); c.moveTo(lx, py(v[0])); c.lineTo(px(0), py(v[0]))
                        for (var i = 0; i < n - 1; i++) { var mx = (px(i) + px(i + 1)) / 2; c.bezierCurveTo(mx, py(v[i]), mx, py(v[i + 1]), px(i + 1), py(v[i + 1])) }
                        c.lineTo(lx + cw, py(v[n - 1]))
                    }
                    onPaint: {
                        var c = getContext("2d")
                        c.reset()
                        c.font = "12px Inter"
                        c.textAlign = "right"
                        for (var d = -12; d <= 12; d += 6) {
                            var y = py(d)
                            c.strokeStyle = d === 0 ? "rgba(255,255,255,0.16)" : "rgba(255,255,255,0.06)"
                            c.beginPath(); c.moveTo(lx, y); c.lineTo(lx + cw, y); c.stroke()
                            c.fillStyle = "rgba(255,255,255,0.4)"
                            c.fillText(d > 0 ? "+" + d : String(d), lx - 8, y + 4)
                        }
                        c.textAlign = "center"
                        var marks = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000], names = ["31", "62", "125", "250", "500", "1к", "2к", "4к", "8к", "16к"]
                        for (var a = 0; a < marks.length; a++) { c.fillStyle = "rgba(255,255,255,0.5)"; c.fillText(names[a], fx(marks[a]), ty + ch + 24) }
                        var v = panel.shown, n = Math.min(v.length, panel.freqs.length)
                        if (n < 2) return
                        v = v.slice(0, n)
                        trace(c, v)
                        c.lineTo(lx + cw, py(0)); c.lineTo(lx, py(0)); c.closePath()
                        var g = c.createLinearGradient(0, ty, 0, ty + ch)
                        g.addColorStop(0, "rgba(255,255,255,0.28)"); g.addColorStop(0.5, "rgba(255,255,255,0.05)"); g.addColorStop(1, "rgba(255,255,255,0.28)")
                        c.fillStyle = g; c.fill()
                        trace(c, v)
                        c.strokeStyle = "rgba(255,255,255,0.92)"; c.lineWidth = 2.2; c.stroke()
                        // What is heard in the end: the bands with bass, clarity and the cuts on top.
                        var bass = panel.s.bass || 0, treble = panel.s.treble || 0, low = panel.s.low_cut || 0, high = panel.s.high_cut || 0
                        if (bass > 0.01 || treble > 0.01 || low > 0 || high > 0) {
                            c.beginPath()
                            for (var q = 0; q <= 96; q++) {
                                var f = 20 * Math.pow(1000, q / 96), r = Math.pow(f / 4500, 2)
                                var total = panel.between(v, f) + bass * 9 / (1 + Math.pow(f / 100, 2)) + treble * 7 * r / (1 + r)
                                if (low > 0) total -= 10 * Math.log(1 + Math.pow(low / f, 6)) / Math.LN10
                                if (high > 0) total -= 10 * Math.log(1 + Math.pow(f / high, 6)) / Math.LN10
                                if (q === 0) c.moveTo(fx(f), py(total)); else c.lineTo(fx(f), py(total))
                            }
                            c.setLineDash([5, 5]); c.strokeStyle = "rgba(255,255,255,0.5)"; c.lineWidth = 1.6; c.stroke(); c.setLineDash([])
                        }
                        var small = n > 15
                        for (var k = 0; k < n; k++) {
                            var active = k === panel.dragging || k === panel.near
                            if (active) { c.fillStyle = "rgba(255,255,255,0.18)"; c.beginPath(); c.arc(px(k), py(v[k]), 14, 0, Math.PI * 2); c.fill() }
                            c.fillStyle = "#f4f4f4"; c.beginPath(); c.arc(px(k), py(v[k]), active ? 8 : small ? 3.5 : 6, 0, Math.PI * 2); c.fill()
                        }
                        var at = panel.dragging >= 0 ? panel.dragging : panel.near
                        if (at >= 0 && at < n) {
                            var note = panel.hertz(panel.freqs[at]) + "  ·  " + (v[at] > 0 ? "+" : "") + v[at].toFixed(1).replace(".", ",") + " дБ"
                            var nx = Math.max(lx + 60, Math.min(lx + cw - 60, px(at))), ny = py(v[at]) - 18
                            if (ny < ty + 8) ny = py(v[at]) + 30
                            c.fillStyle = "white"; c.fillText(note, nx, ny)
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        function band(x) {
                            var best = 0, far = 1e9
                            for (var i = 0; i < panel.count; i++) { var d = Math.abs(curve.px(i) - x); if (d < far) { far = d; best = i } }
                            return best
                        }
                        function value(y) { return Math.round(Math.max(-12, Math.min(12, (curve.ty + curve.ch / 2 - y) / (curve.ch / 2) * 12)) * 2) / 2 }
                        onPressed: (m) => { panel.dragging = band(m.x); set(m.y) }
                        // Held down and moved across, the pointer draws the curve band by band.
                        onPositionChanged: (m) => { if (pressed) { panel.dragging = band(m.x); set(m.y) } else { panel.near = band(m.x); curve.requestPaint() } }
                        onReleased: { if (panel.dragging >= 0) app.soundBands(panel.shown); panel.dragging = -1 }
                        onExited: { panel.near = -1; curve.requestPaint() }
                        onDoubleClicked: (m) => { var v = panel.shown.slice(); v[band(m.x)] = 0; panel.shown = v; app.soundBands(v); curve.requestPaint() }
                        function set(y) { var v = panel.shown.slice(); v[panel.dragging] = value(y); panel.shown = v; curve.requestPaint() }
                    }
                }
                }
                Row {
                    id: knobs
                    width: parent.width
                    spacing: 10
                    readonly property real cell: (width - 40) / 5
                    Card {
                        width: knobs.cell; height: 96
                        title: "Усиление"; value: panel.db(panel.s.preamp || 0)
                        SoftSlider { y: -30; width: parent.width; from: -12; to: 12; stepSize: 0.5; value: panel.s.preamp || 0; onMoved: app.soundSet("preamp", value) }
                    }
                    Card {
                        width: knobs.cell; height: 96
                        title: "Бас-буст"; value: panel.percent(panel.s.bass || 0)
                        SoftSlider { y: -30; width: parent.width; from: 0; to: 1; value: panel.s.bass || 0; onMoved: app.soundSet("bass", value) }
                    }
                    Card {
                        width: knobs.cell; height: 96
                        title: "Чёткость"; value: panel.percent(panel.s.treble || 0)
                        SoftSlider { y: -30; width: parent.width; from: 0; to: 1; value: panel.s.treble || 0; onMoved: app.soundSet("treble", value) }
                    }
                    Card {
                        // Everything below this pitch falls away: 20 Hz to 600 Hz, the far left is off.
                        width: knobs.cell; height: 96
                        readonly property real cut: panel.s.low_cut || 0
                        title: "Срез низа"; value: cut > 0 ? panel.hertz(cut) : "выкл"
                        SoftSlider { y: -30; width: parent.width; from: 0; to: 1
                                     value: parent.parent.cut > 0 ? Math.log(parent.parent.cut / 20) / Math.log(30) : 0
                                     onMoved: app.soundSet("low_cut", value < 0.02 ? 0.0 : Math.round(20 * Math.pow(30, value))) }
                    }
                    Card {
                        // Everything above this pitch falls away: 300 Hz to 20 kHz, the far right is off.
                        width: knobs.cell; height: 96
                        readonly property real cut: panel.s.high_cut || 0
                        title: "Срез верха"; value: cut > 0 ? panel.hertz(cut) : "выкл"
                        SoftSlider { y: -30; width: parent.width; from: 0; to: 1
                                     value: parent.parent.cut > 0 ? Math.log(parent.parent.cut / 300) / Math.log(20000 / 300) : 1
                                     onMoved: app.soundSet("high_cut", value > 0.98 ? 0.0 : Math.round(300 * Math.pow(20000 / 300, value))) }
                    }
                }
            }

            // ---- effects ----
            Item {
                width: parent.width
                height: parent.height
                x: pages.shift(2)
                opacity: pages.shade(2)
                visible: opacity > 0.01
                Flickable {
                    id: fxFlick
                    anchors.fill: parent
                    contentWidth: width
                    contentHeight: fxColumn.height + 6
                    interactive: false
                    clip: true
                    pixelAligned: true
                    Column {
                        id: fxColumn
                        width: fxFlick.width - 14
                        spacing: 10
                        readonly property real cell: (width - 20) / 3

                        Heading { text: "ПРОСТРАНСТВО"; height: 18 }
                        Card {
                            width: parent.width; title: "Помещение"; text: "Где звучит музыка: от глухой студии до пещеры"
                            value: panel.s.space ? panel.s.space + " · " + panel.percent(panel.s.space_mix || 0.35) : "выкл"
                            Row { y: -6; spacing: 6
                                // The chosen one pressed again turns the space off.
                                Repeater { model: app.stateMap.spaces
                                    PillButton { text: modelData; checked: panel.s.space === modelData; onClicked: app.soundSet("space", panel.s.space === modelData ? null : modelData) } } }
                            SoftSlider { anchors.right: parent.right; y: -1; width: 250; from: 0; to: 1; value: panel.s.space_mix || 0.35; onMoved: app.soundSet("space_mix", value) }
                        }
                        Row {
                            spacing: 10
                            Card {
                                switchable: true; width: fxColumn.cell; title: "8D — звук вокруг"; text: "Звук плывёт вокруг головы"; on: !!panel.s.orbit
                                onFlipped: app.soundSet("orbit", !panel.s.orbit)
                                SoftSlider { y: 10; width: parent.width; from: 0.03; to: 0.4; value: panel.s.orbit_speed || 0.12; onMoved: app.soundSet("orbit_speed", value) }
                            }
                            Card {
                                width: fxColumn.cell; title: "Ширина стерео"
                                readonly property real w: panel.s.width === undefined ? 1 : panel.s.width
                                value: w < 0.05 ? "моно" : Math.abs(w - 1) < 0.03 ? "как записано" : panel.percent(w)
                                text: "Уже — ближе к моно, шире — звук раскрывается по сторонам"
                                SoftSlider { y: 10; width: parent.width; from: 0; to: 2; value: parent.parent.w; onMoved: app.soundSet("width", Math.abs(value - 1) < 0.04 ? 1.0 : value) }
                            }
                            Card {
                                width: fxColumn.cell; title: "Баланс"
                                readonly property real b: panel.s.balance || 0
                                value: Math.abs(b) < 0.02 ? "по центру" : (b < 0 ? "левее " : "правее ") + panel.percent(Math.abs(b))
                                text: "Громкость левого и правого канала"
                                SoftSlider { y: 10; width: parent.width; from: -1; to: 1; value: parent.parent.b; onMoved: app.soundSet("balance", Math.abs(value) < 0.04 ? 0.0 : value) }
                            }
                        }
                        Card {
                            id: echoCard
                            width: parent.width; title: "Эхо"; text: "Звук возвращается, каждый раз тише, то слева, то справа"
                            value: panel.amount(panel.s.echo || 0)
                            readonly property real third: (width - 32 - 40) / 3
                            Row {
                                y: -8; spacing: 20
                                Column {
                                    width: echoCard.third; spacing: 2
                                    Text { text: "Громкость эха"; color: Qt.rgba(1, 1, 1, 0.48); font.family: "Inter"; font.pixelSize: 12 }
                                    SoftSlider { width: parent.width; from: 0; to: 1; value: panel.s.echo || 0; onMoved: app.soundSet("echo", value < 0.02 ? 0.0 : value) }
                                }
                                Column {
                                    width: echoCard.third; spacing: 2
                                    Text { text: "Задержка · " + Math.round((panel.s.echo_time || 0.32) * 1000) + " мс"; color: Qt.rgba(1, 1, 1, 0.48); font.family: "Inter"; font.pixelSize: 12 }
                                    SoftSlider { width: parent.width; from: 0.06; to: 0.9; value: panel.s.echo_time || 0.32; onMoved: app.soundSet("echo_time", Math.round(value * 100) / 100) }
                                }
                                Column {
                                    width: echoCard.third; spacing: 2
                                    Text { text: "Повторы · " + panel.percent(panel.s.echo_feedback === undefined ? 0.35 : panel.s.echo_feedback); color: Qt.rgba(1, 1, 1, 0.48); font.family: "Inter"; font.pixelSize: 12 }
                                    SoftSlider { width: parent.width; from: 0; to: 0.8; value: panel.s.echo_feedback === undefined ? 0.35 : panel.s.echo_feedback; onMoved: app.soundSet("echo_feedback", value) }
                                }
                            }
                        }
                        Row {
                            spacing: 10
                            Card {
                                switchable: true; width: (fxColumn.width - 10) / 2; height: 96; title: "Для наушников"; on: !!panel.s.crossfeed
                                text: "Каждое ухо слышит немного другой стороны, как от колонок"
                                onFlipped: app.soundSet("crossfeed", !panel.s.crossfeed)
                            }
                            Card {
                                switchable: true; width: (fxColumn.width - 10) / 2; height: 96; title: "Поменять стороны"; on: !!panel.s.swap
                                text: "Левое играет справа, правое — слева"
                                onFlipped: app.soundSet("swap", !panel.s.swap)
                            }
                        }

                        Heading { text: "ХАРАКТЕР" }
                        Row {
                            spacing: 10
                            Dial { width: fxColumn.cell; key: "vinyl"; title: "Винил"; text: "Треск и тёплый звук пластинки" }
                            Dial { width: fxColumn.cell; key: "drive"; title: "Тёплая лента"; text: "Громкие места мягко скругляются, звук плотнее" }
                            Dial { width: fxColumn.cell; key: "wobble"; title: "Кассета плывёт"; text: "Тон чуть гуляет вверх и вниз, как на старой плёнке" }
                        }
                        Row {
                            spacing: 10
                            Dial { width: fxColumn.cell; key: "crush"; title: "Lo-fi"; text: "Зернистый звук старого сэмплера" }
                            Dial { width: fxColumn.cell; key: "chorus"; title: "Хорус"; text: "Один голос превращается в несколько" }
                            Dial { width: fxColumn.cell; key: "flanger"; title: "Фленджер"; text: "Звук закручивается, как пролетающий самолёт" }
                        }

                        Heading { text: "ГОЛОС, ГРОМКОСТЬ, СКОРОСТЬ" }
                        Row {
                            spacing: 10
                            Dial { width: fxColumn.cell; key: "voice"; title: "Убрать голос"; text: "Караоке: убирает то, что звучит по центру" }
                            Dial { width: fxColumn.cell; key: "compress"; title: "Компрессор"; text: "Громкое тише, тихое слышнее — для ночи и малой громкости" }
                            Card {
                                switchable: true; width: fxColumn.cell; title: "Ровная громкость"; on: !!panel.s.level
                                text: "Тихие треки чуть громче, громкие чуть тише — плейлист звучит ровно"
                                onFlipped: app.soundSet("level", !panel.s.level)
                            }
                        }
                        Card {
                            width: parent.width; title: "Скорость"; text: "Тон меняется вместе со скоростью, как у пластинки"
                            value: String(panel.s.speed || 1).replace(".", ",") + "×"
                            Row { y: -6; spacing: 6
                                Repeater { model: [0.75, 0.85, 0.9, 1.0, 1.1, 1.15, 1.25, 1.5]
                                    PillButton { text: String(modelData).replace(".", ",") + "×"; checked: Math.abs((panel.s.speed || 1) - modelData) < 0.01; onClicked: app.setSpeed(modelData) } } }
                        }
                    }
                }
                SmoothWheel { flick: fxFlick }
                // How far down the effects the view is.
                Rectangle {
                    anchors.right: parent.right
                    width: 4; radius: 2
                    color: Qt.rgba(1, 1, 1, 0.22)
                    visible: fxFlick.contentHeight > fxFlick.height
                    height: Math.max(40, fxFlick.height * fxFlick.height / Math.max(1, fxFlick.contentHeight))
                    y: (fxFlick.height - height) * fxFlick.contentY / Math.max(1, fxFlick.contentHeight - fxFlick.height)
                }
            }
        }
    }
    Timer {
        // The curve glides into a new preset's shape.
        id: easeTimer
        interval: 16; repeat: true
        running: glide.running
        onRunningChanged: if (!running) { panel.shown = glide.target.slice(); curve.requestPaint() }
        onTriggered: {
            var t = 1 - Math.pow(1 - Math.min(1, glide.t), 3), v = []
            for (var i = 0; i < glide.target.length; i++) v.push((glide.from[i] || 0) + ((glide.target[i] || 0) - (glide.from[i] || 0)) * t)
            panel.shown = v
            curve.requestPaint()
        }
    }
}
