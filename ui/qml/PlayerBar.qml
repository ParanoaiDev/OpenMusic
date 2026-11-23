import QtQuick
import QtQuick.Controls

// The bar at the bottom: what plays on the left, the controls and the sound shape of the track in
// the middle (never wider than 820 px), the rest on the right.
Rectangle {
    id: bar
    height: 98
    color: "#0a0a0c"
    readonly property var p: app.playerMap
    signal lyricsClicked()
    signal queueClicked()
    signal soundClicked()
    Rectangle { width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.06) }
    // A glow in the colour of the cover behind what plays.
    Rectangle {
        width: 420; height: parent.height
        opacity: bar.p.hasTrack ? 0.5 : 0
        Behavior on opacity { NumberAnimation { duration: 600 } }
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(Qt.color(bar.p.colour).r, Qt.color(bar.p.colour).g, Qt.color(bar.p.colour).b, 0.35) }
            GradientStop { position: 1; color: "transparent" }
        }
    }

    Item {
        id: now
        x: 18
        width: 340
        height: parent.height
        RoundImage {
            id: art
            width: 60; height: 60
            anchors.verticalCenter: parent.verticalCenter
            radius: 10
            source: bar.p.cover
            visible: bar.p.cover !== ""
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bar.lyricsClicked() }
        }
        Rectangle { anchors.fill: art; radius: 10; visible: bar.p.cover === ""; color: Qt.rgba(1, 1, 1, 0.07); Icon { anchors.centerIn: parent; name: "note"; size: 24; opacity: 0.5 } }
        Column {
            x: 76
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x - 46
            spacing: 4
            Text { width: parent.width; text: bar.p.title; elide: Text.ElideRight; color: "white"; font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15 }
            Text {
                width: Math.min(parent.width, implicitWidth); text: bar.p.caption; elide: Text.ElideRight
                color: Qt.rgba(1, 1, 1, artistArea.containsMouse ? 0.9 : 0.55); font.family: "Inter"; font.pixelSize: 13
                font.underline: artistArea.containsMouse
                // The artist opens their page.
                MouseArea { id: artistArea; anchors.fill: parent; enabled: bar.p.artist !== ""; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: app.showArtist(bar.p.artist) }
            }
        }
        IconButton {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            name: bar.p.liked ? "heart-filled" : "heart"
            active: bar.p.liked
            enabled2: bar.p.hasTrack
            tip: bar.p.liked ? "Убрать из «Мне нравится»" : "Нравится"
            onClicked: app.likeCurrent()
        }
    }

    Item {
        id: middle
        width: Math.min(820, bar.width - 760)
        x: (bar.width - width) / 2
        height: parent.height
        Row {
            id: controls
            anchors.horizontalCenter: parent.horizontalCenter
            y: 10
            spacing: 14
            IconButton { anchors.verticalCenter: parent.verticalCenter; name: "shuffle"; active: bar.p.shuffle; tip: "Перемешать"; onClicked: app.toggleShuffle() }
            IconButton { anchors.verticalCenter: parent.verticalCenter; name: "previous"; tip: "Предыдущий"; enabled2: bar.p.hasTrack; onClicked: app.previous() }
            Item {
                width: 48; height: 48
                Rectangle {
                    anchors.centerIn: parent
                    width: 44 * (playArea.pressed ? 0.92 : playArea.containsMouse ? 1.06 : 1); height: width
                    radius: width / 2
                    color: bar.p.hasTrack ? "#f4f4f4" : Qt.rgba(1, 1, 1, 0.12)
                    Behavior on width { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                }
                Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: bar.p.playing || bar.p.loading ? 0 : 1; name: bar.p.playing || bar.p.loading ? "pause" : "play"; tint: "#0a0a0a"; size: 20 }
                // The arc that runs while sound is being found.
                Canvas {
                    id: spinner
                    anchors.centerIn: parent
                    width: 58; height: 58
                    visible: bar.p.loading
                    property real turn: 0
                    NumberAnimation on turn { from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: spinner.visible }
                    rotation: turn
                    onPaint: { var c = getContext("2d"); c.reset(); c.strokeStyle = "white"; c.lineWidth = 2.4; c.lineCap = "round"; c.beginPath(); c.arc(29, 29, 26, 0, Math.PI * 0.6); c.stroke() }
                    Component.onCompleted: requestPaint()
                }
                MouseArea { id: playArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: app.toggle() }
            }
            IconButton { anchors.verticalCenter: parent.verticalCenter; name: "next"; tip: "Следующий"; enabled2: bar.p.canNext; onClicked: app.next() }
            IconButton { anchors.verticalCenter: parent.verticalCenter; name: bar.p.repeat === "one" ? "repeat-one" : "repeat"; active: bar.p.repeat !== "off"
                         tip: bar.p.repeat === "off" ? "Повтор выключен" : bar.p.repeat === "all" ? "Повтор очереди" : "Повтор трека"; onClicked: app.cycleRepeat() }
        }
        Item {
            id: timeline
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 10
            width: parent.width
            height: 30
            readonly property real share: app.duration > 0 ? (scrub.dragging ? scrub.dragShare : app.position / app.duration) : 0
            Text { id: elapsed; anchors.verticalCenter: parent.verticalCenter; width: 40; horizontalAlignment: Text.AlignRight
                   text: bar.clock(scrub.dragging ? scrub.dragShare * app.duration : app.position); color: Qt.rgba(1, 1, 1, 0.45); font.family: "Inter"; font.pixelSize: 12 }
            Text { id: total; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 40
                   text: bar.clock(app.duration); color: Qt.rgba(1, 1, 1, 0.45); font.family: "Inter"; font.pixelSize: 12 }
            Item {
                id: scrub
                x: 52
                width: parent.width - 104
                height: parent.height
                property bool dragging: false
                property real dragShare: 0
                property real hover: scrubArea.containsMouse ? 1 : 0
                Behavior on hover { NumberAnimation { duration: 160 } }
                readonly property var wave: bar.p.wave
                Row {
                    visible: scrub.wave.length > 0
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 0
                    Repeater {
                        model: scrub.wave
                        Item {
                            width: scrub.width / Math.max(1, scrub.wave.length)
                            height: scrub.height
                            Rectangle {
                                anchors.centerIn: parent
                                width: Math.max(1.5, parent.width * 0.6)
                                height: Math.max(2, modelData * (scrub.height - 6) * (1 + 0.1 * scrub.hover))
                                radius: width / 2
                                color: (index + 0.5) / scrub.wave.length <= timeline.share ? "#f4f4f4" : Qt.rgba(1, 1, 1, 0.25 + 0.1 * scrub.hover)
                            }
                        }
                    }
                }
                Rectangle {
                    visible: scrub.wave.length === 0
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width; height: 4 + 2 * scrub.hover; radius: height / 2
                    color: Qt.rgba(1, 1, 1, 0.16)
                    Rectangle { width: parent.width * timeline.share; height: parent.height; radius: height / 2; color: "#f4f4f4" }
                    Rectangle { x: parent.width * timeline.share - width / 2; anchors.verticalCenter: parent.verticalCenter
                                width: 10 + 4 * scrub.hover; height: width; radius: width / 2; color: "white"; opacity: 0.4 + 0.6 * scrub.hover }
                }
                MouseArea {
                    id: scrubArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    enabled: app.duration > 0
                    onPressed: (mouse) => { scrub.dragging = true; scrub.dragShare = Math.max(0, Math.min(1, mouse.x / width)) }
                    onPositionChanged: (mouse) => { if (scrub.dragging) scrub.dragShare = Math.max(0, Math.min(1, mouse.x / width)) }
                    onReleased: { app.seek(scrub.dragShare * app.duration); scrub.dragging = false }
                }
            }
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 20
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6
        Icon { anchors.verticalCenter: parent.verticalCenter; name: "volume"; size: 18; opacity: 0.55 }
        SoftSlider {
            anchors.verticalCenter: parent.verticalCenter
            width: 110
            from: 0; to: 1
            value: bar.p.volume
            onMoved: app.setVolume(value)
        }
        Item { width: 8; height: 1 }
        IconButton { name: "lyrics"; tip: "Сейчас играет и текст"; active: app.stateMap.page === 3; onClicked: bar.lyricsClicked() }
        IconButton { name: "queue"; tip: "Очередь"; onClicked: bar.queueClicked() }
        IconButton { name: "sliders"; tip: "Звук: эквалайзер и эффекты"; onClicked: bar.soundClicked() }
        IconButton {
            name: "more"
            tip: "Скорость и таймер сна"
            onClicked: more.popup()
            Menu2 {
                id: more
                Menu2 {
                    title: "Скорость"
                    MenuItem2 { text: "0,75×"; onTriggered: app.setSpeed(0.75) }
                    MenuItem2 { text: "0,9×"; onTriggered: app.setSpeed(0.9) }
                    MenuItem2 { text: "1×"; onTriggered: app.setSpeed(1.0) }
                    MenuItem2 { text: "1,1×"; onTriggered: app.setSpeed(1.1) }
                    MenuItem2 { text: "1,25×"; onTriggered: app.setSpeed(1.25) }
                    MenuItem2 { text: "1,5×"; onTriggered: app.setSpeed(1.5) }
                }
                Menu2 {
                    title: bar.p.sleep !== "" ? "Таймер сна · " + bar.p.sleep : "Таймер сна"
                    MenuItem2 { text: "Выключен"; onTriggered: app.sleepIn(0) }
                    MenuItem2 { text: "Через 15 минут"; onTriggered: app.sleepIn(15) }
                    MenuItem2 { text: "Через 30 минут"; onTriggered: app.sleepIn(30) }
                    MenuItem2 { text: "Через 45 минут"; onTriggered: app.sleepIn(45) }
                    MenuItem2 { text: "Через час"; onTriggered: app.sleepIn(60) }
                    MenuItem2 { text: "После этого трека"; onTriggered: app.sleepIn(-1) }
                }
                MenuItem2 { text: "Открыть аудиофайл…"; onTriggered: app.openFile() }
            }
        }
    }

    function clock(ms) {
        var seconds = Math.floor(ms / 1000)
        return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0")
    }
}
