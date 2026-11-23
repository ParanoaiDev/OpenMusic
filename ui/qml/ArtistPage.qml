import QtQuick
import QtQuick.Controls
import QtQuick.Effects

// The page of an artist, the way Spotify has it: the photo across the top with the name over it,
// then the popular tracks, the artist's tracks in the library, the releases and similar artists. A
// release opens over the page with its tracks. The photo drifts slowly and stays behind as the page
// scrolls; the name rises in on every opening; a bar with the name comes down when the photo is gone.
Rectangle {
    id: page
    color: "#060608"
    readonly property var p: artist.page
    readonly property int pad: Math.round(Math.max(40, Math.min(90, width * 0.035)))
    readonly property int tile: Math.round(Math.max(156, Math.min(212, (width - pad * 2) / 7)) / 4) * 4
    readonly property bool loading: p.status === "loading"
    property color tone: p.tone || "#3a3040"
    Behavior on tone { ColorAnimation { duration: 900 } }

    property real t: 0
    FrameAnimation {
        running: page.visible && !app.settingsMap.calm && view.contentY < header.height && Qt.application.state === Qt.ApplicationActive
        onTriggered: page.t += Math.min(0.1, frameTime)
    }
    // Every opening, also from one artist to the next, plays the way in again from the top.
    property real enter: 1
    property int seen: -1
    function opened() {
        if (p.opened === seen) return
        seen = p.opened
        topMore = false; mineMore = false
        view.contentY = 0
        entry.restart()
    }
    Connections { target: artist; function onChanged() { page.opened() } }
    Component.onCompleted: opened()
    NumberAnimation { id: entry; target: page; property: "enter"; from: 0; to: 1; duration: 1200 }
    function step(from, span) { var x = Math.max(0, Math.min(1, (enter - from) / span)); return 1 - Math.pow(1 - x, 3) }

    property bool topMore: false
    property bool mineMore: false

    // The back button of the mouse goes back as well.
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.BackButton; onClicked: artist.back() }

    Flickable {
        id: view
        anchors.fill: parent
        contentWidth: width
        contentHeight: body.height + 90
        boundsBehavior: Flickable.StopAtBounds
        interactive: false
        clip: true
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 8 }

        Column {
            id: body
            width: view.width
            spacing: 40

            // ---- the photo and the name ----
            Item {
                id: header
                width: parent.width
                height: Math.round(Math.max(360, Math.min(520, page.height * 0.5)))
                clip: true
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.darker(page.tone, 1.3) }
                        GradientStop { position: 1.0; color: "#060608" }
                    }
                }
                // The photo is square; it fills the width and shows its upper middle, where faces are.
                Image {
                    id: photo
                    width: header.width
                    height: width
                    y: -(height - header.height) * 0.32 + view.contentY * 0.45
                    source: page.p.picture
                    asynchronous: true
                    fillMode: Image.PreserveAspectCrop
                    sourceSize.width: Math.min(1000, Math.round(width * Screen.devicePixelRatio))
                    smooth: true
                    mipmap: true
                    opacity: status === Image.Ready ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
                    scale: 1.12 - 0.06 * page.step(0, 0.9) + 0.025 * Math.sin(page.t * 0.09)
                    transformOrigin: Item.Center
                }
                // The colour of the photo over it, and the dark it fades into, so the name always reads.
                Rectangle { anchors.fill: parent; color: page.tone; opacity: 0.22 }
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(0.02, 0.02, 0.03, 0.25) }
                        GradientStop { position: 0.45; color: Qt.rgba(0.02, 0.02, 0.03, 0.05) }
                        GradientStop { position: 0.8; color: Qt.rgba(0.02, 0.02, 0.03, 0.7) }
                        GradientStop { position: 1.0; color: "#060608" }
                    }
                }
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Qt.rgba(0.02, 0.02, 0.03, 0.55) }
                        GradientStop { position: 0.6; color: "transparent" }
                    }
                }
                Column {
                    x: page.pad
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 26
                    width: parent.width - page.pad * 2
                    spacing: 6
                    opacity: 1 - Math.min(1, view.contentY / (header.height * 0.7))
                    Row {
                        spacing: 8
                        opacity: page.step(0.05, 0.4)
                        Rectangle {
                            width: 22; height: 22; radius: 11
                            color: "#ffffff"
                            anchors.verticalCenter: parent.verticalCenter
                            Icon { anchors.centerIn: parent; name: "wave"; size: 14; tint: "#0a0a0a" }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Исполнитель"
                            color: "white"
                            font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 14
                        }
                    }
                    Text {
                        id: nameText
                        width: parent.width
                        text: page.p.name
                        color: "white"
                        renderType: Text.QtRendering
                        elide: Text.ElideRight
                        font.family: "Inter Display"; font.weight: Font.Black
                        readonly property int size: Math.round(Math.max(46, Math.min(116, parent.width * 1.45 / Math.max(5, text.length))))
                        font.pixelSize: size
                        font.letterSpacing: size * (0.1 - 0.12 * page.step(0.1, 0.8))
                        opacity: page.step(0.1, 0.5)
                        transform: Translate { y: (1 - page.step(0.1, 0.8)) * 46 }
                        layer.enabled: true
                        layer.effect: MultiEffect { shadowEnabled: true; shadowBlur: 0.9; shadowOpacity: 0.6; shadowColor: "#000000"; autoPaddingEnabled: true }
                    }
                    Text {
                        width: parent.width
                        text: page.p.facts
                        visible: text !== ""
                        elide: Text.ElideRight
                        color: Qt.rgba(1, 1, 1, 0.82)
                        opacity: page.step(0.35, 0.5)
                        font.family: "Inter"; font.weight: Font.Medium; font.pixelSize: 16
                    }
                }
            }

            // ---- play, shuffle, the link ----
            Row {
                x: page.pad
                spacing: 18
                opacity: page.step(0.4, 0.5)
                Item {
                    width: 64; height: 64
                    anchors.verticalCenter: parent.verticalCenter
                    visible: artist.topModel.count > 0 || artist.mineModel.count > 0
                    RectangularShadow {
                        anchors.fill: playDisc
                        radius: width / 2
                        blur: 30
                        color: page.tone
                        opacity: playArea.containsMouse ? 0.9 : 0.5
                        Behavior on opacity { NumberAnimation { duration: 200 } }
                    }
                    Rectangle {
                        id: playDisc
                        anchors.centerIn: parent
                        width: 60; height: 60; radius: 30
                        color: playArea.containsMouse ? "#ffffff" : "#f0f0f0"
                        scale: playArea.pressed ? 0.93 : playArea.containsMouse ? 1.06 : 1
                        Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                        Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: 2; name: "play"; size: 24; tint: "#0a0a0a" }
                    }
                    MouseArea { id: playArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: artist.playTop(false) }
                    ToolTipText { text: "Слушать популярное"; shown: playArea.containsMouse }
                }
                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: artist.topModel.count > 1 || artist.mineModel.count > 1
                    size: 48; glyph: 24
                    name: "shuffle"
                    tip: "Перемешать"
                    onClicked: artist.playTop(true)
                }
                PillButton {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: page.p.link !== ""
                    text: "Открыть в Deezer"
                    onClicked: artist.openLink(page.p.link)
                }
                PillButton {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: artist.mineModel.count > 0
                    text: "Все треки в медиатеке"
                    onClicked: app.filterArtist(page.p.name)
                }
            }

            // ---- loading, no answer, nobody of that name ----
            Column {
                x: page.pad
                width: parent.width - page.pad * 2
                spacing: 8
                visible: page.loading
                Repeater {
                    model: 5
                    Rectangle {
                        width: parent.width * (0.62 - index * 0.04); height: 54; radius: 12
                        color: "white"
                        opacity: 0.045 + 0.03 * Math.sin(page.t * 3 - index * 0.6)
                    }
                }
            }
            Column {
                x: page.pad
                spacing: 14
                visible: page.p.status === "offline" || page.p.status === "missing"
                Text {
                    text: page.p.status === "offline" ? "Нет связи с Deezer" : "Страницы на Deezer нет"
                    color: "white"
                    font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 24
                }
                Text {
                    text: page.p.status === "offline" ? "Без интернета видно только то, что есть в медиатеке." : "Показываю треки этого артиста из медиатеки."
                    color: Qt.rgba(1, 1, 1, 0.55)
                    font.family: "Inter"; font.pixelSize: 15
                }
                PillButton { visible: page.p.status === "offline"; text: "Повторить"; primary: true; onClicked: artist.retry() }
            }

            // ---- popular tracks ----
            Column {
                x: page.pad - 10
                width: Math.min(parent.width - page.pad * 2 + 20, 1100)
                spacing: 6
                visible: artist.topModel.count > 0
                opacity: page.step(0.5, 0.5)
                Text {
                    x: 10
                    text: "Популярные треки"
                    color: "white"
                    font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 26
                    bottomPadding: 8
                }
                Repeater {
                    model: artist.topModel
                    TrackRow {
                        width: parent.width
                        list: "artist-top"
                        number: index + 1
                        visible: page.topMore || index < 5
                        height: visible ? 62 : 0
                    }
                }
                Text {
                    x: 10
                    visible: artist.topModel.count > 5
                    text: page.topMore ? "Свернуть" : "Ещё"
                    color: moreArea.containsMouse ? "white" : Qt.rgba(1, 1, 1, 0.6)
                    font.family: "Inter"; font.weight: Font.Bold; font.pixelSize: 14
                    topPadding: 8
                    MouseArea { id: moreArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: page.topMore = !page.topMore }
                }
            }

            // ---- in the library ----
            Column {
                x: page.pad - 10
                width: Math.min(parent.width - page.pad * 2 + 20, 1100)
                spacing: 6
                visible: artist.mineModel.count > 0
                opacity: page.step(0.55, 0.45)
                Text {
                    x: 10
                    text: "В вашей медиатеке"
                    color: "white"
                    font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 26
                }
                Text {
                    x: 10
                    text: page.p.mineText
                    color: Qt.rgba(1, 1, 1, 0.5)
                    font.family: "Inter"; font.pixelSize: 14
                    bottomPadding: 8
                }
                Repeater {
                    model: artist.mineModel
                    TrackRow {
                        width: parent.width
                        list: "artist-mine"
                        visible: page.mineMore ? index < 60 : index < 5
                        height: visible ? 62 : 0
                    }
                }
                Text {
                    x: 10
                    visible: artist.mineModel.count > 5
                    text: page.mineMore ? "Свернуть" : "Показать ещё"
                    color: mineArea.containsMouse ? "white" : Qt.rgba(1, 1, 1, 0.6)
                    font.family: "Inter"; font.weight: Font.Bold; font.pixelSize: 14
                    topPadding: 8
                    MouseArea { id: mineArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: page.mineMore = !page.mineMore }
                }
            }

            // ---- releases ----
            Item {
                x: page.pad
                width: parent.width - page.pad * 2
                height: releases.height
                visible: artist.releaseItems.count > 0 || page.p.filters.length > 0
                opacity: page.step(0.6, 0.4)
                Shelf {
                    id: releases
                    width: parent.width
                    title: "Дискография"
                    itemHeight: page.tile + 64
                    model: artist.releaseItems
                    delegate: HoverCard {
                        id: release
                        width: page.tile
                        height: page.tile + 64
                        onClicked: artist.openRelease(index)
                        RectangularShadow {
                            anchors.fill: cover
                            radius: cover.width * 0.06
                            blur: 40
                            color: page.tone
                            opacity: 0.8 * release.lift
                            visible: release.lift > 0.01
                        }
                        Rectangle { anchors.fill: cover; radius: cover.width * 0.06; color: Qt.rgba(1, 1, 1, 0.06); visible: !cover.ready }
                        Art { id: cover; width: parent.width; height: width; source: entry.cover; round: 0.06 }
                        Rectangle {
                            width: 44; height: 44; radius: 22
                            x: cover.width - width - 10
                            y: cover.height - height - 10 + (1 - release.lift) * 12
                            opacity: release.lift
                            color: "white"
                            Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: 1; name: "play"; size: 18; tint: "#0a0a0a" }
                        }
                        Text {
                            y: cover.height + 12
                            width: parent.width
                            elide: Text.ElideRight
                            text: entry.title
                            color: "white"
                            font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15
                        }
                        Text {
                            y: cover.height + 34
                            width: parent.width
                            elide: Text.ElideRight
                            text: entry.info
                            color: Qt.rgba(1, 1, 1, 0.5)
                            font.family: "Inter"; font.pixelSize: 13
                        }
                    }
                }
                // The kinds of release, beside the title.
                Row {
                    x: shelfTitle.advanceWidth + 26
                    height: 34
                    spacing: 8
                    Repeater {
                        model: page.p.filters
                        PillButton {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.title
                            checked: page.p.kind === modelData.kind
                            onClicked: artist.showKind(modelData.kind)
                        }
                    }
                }
                TextMetrics { id: shelfTitle; text: "Дискография"; font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 26 }
            }

            // ---- similar artists ----
            Shelf {
                x: page.pad
                width: parent.width - page.pad * 2
                title: "Похожие исполнители"
                visible: artist.relatedItems.count > 0
                opacity: page.step(0.65, 0.35)
                itemHeight: page.tile + 64
                model: artist.relatedItems
                delegate: HoverCard {
                    id: other
                    width: page.tile
                    height: page.tile + 64
                    onClicked: artist.openRelated(index)
                    Rectangle {
                        anchors.fill: face
                        radius: width / 2
                        color: Qt.rgba(1, 1, 1, 0.06)
                        visible: !face.ready
                        Text { anchors.centerIn: parent; text: entry.name.charAt(0); color: Qt.rgba(1, 1, 1, 0.4); font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: parent.width * 0.36 }
                    }
                    Art { id: face; width: parent.width; height: width; source: entry.picture; round: 0.5 }
                    Rectangle { anchors.fill: face; radius: width / 2; color: "transparent"; border.width: 2; border.color: Qt.rgba(1, 1, 1, 0.5 * other.lift) }
                    Text {
                        y: face.height + 12
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        text: entry.name
                        color: "white"
                        font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15
                    }
                    Text {
                        y: face.height + 34
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        text: entry.fans
                        color: Qt.rgba(1, 1, 1, 0.5)
                        font.family: "Inter"; font.pixelSize: 13
                    }
                }
            }
        }
    }
    SmoothWheel { flick: view }

    // ---- the bar that comes down once the photo has scrolled away ----
    Rectangle {
        id: bar
        width: parent.width
        height: 76
        readonly property real shown: Math.max(0, Math.min(1, (view.contentY - header.height + 160) / 70))
        opacity: shown
        visible: shown > 0
        color: Qt.rgba(page.tone.r * 0.32, page.tone.g * 0.32, page.tone.b * 0.32, 0.97)
        Behavior on color { ColorAnimation { duration: 600 } }
        Rectangle {
            id: barPlay
            x: page.pad + 50
            anchors.verticalCenter: parent.verticalCenter
            width: 42; height: 42; radius: 21
            color: "white"
            visible: artist.topModel.count > 0 || artist.mineModel.count > 0
            Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: 1; name: "play"; size: 17; tint: "#0a0a0a" }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: artist.playTop(false) }
        }
        Text {
            x: barPlay.x + 58
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x - page.pad
            elide: Text.ElideRight
            text: page.p.name
            color: "white"
            transform: Translate { y: (1 - bar.shown) * 12 }
            font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 26
        }
    }
    // ---- back ----
    Rectangle {
        x: page.pad - 4
        y: 18
        width: 40; height: 40; radius: 20
        color: Qt.rgba(0, 0, 0, backArea.containsMouse ? 0.7 : 0.45)
        Behavior on color { ColorAnimation { duration: 160 } }
        scale: backArea.pressed ? 0.92 : 1
        Behavior on scale { NumberAnimation { duration: 120 } }
        Icon { anchors.centerIn: parent; name: "back"; size: 20 }
        MouseArea { id: backArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: artist.back() }
        ToolTipText { text: "Назад"; shown: backArea.containsMouse }
    }

    // ---- a release, over the page ----
    Item {
        id: sheet
        anchors.fill: parent
        property real open: page.p.albumOpen ? 1 : 0
        Behavior on open { NumberAnimation { duration: 420; easing.type: Easing.OutCubic } }
        visible: open > 0.001
        z: 100
        Rectangle {
            anchors.fill: parent
            color: "black"
            opacity: 0.6 * sheet.open
            MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onClicked: artist.closeRelease(); onWheel: (wheel) => wheel.accepted = true }
        }
        Rectangle {
            id: panel
            width: Math.min(920, parent.width - page.pad * 2)
            height: parent.height - 48
            anchors.horizontalCenter: parent.horizontalCenter
            y: 24 + (1 - sheet.open) * 80
            opacity: sheet.open
            radius: 26
            clip: true
            color: "#0e0e12"
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.08)
            MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: (wheel) => wheel.accepted = false }
            Rectangle {
                width: parent.width; height: 300
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(page.tone.r, page.tone.g, page.tone.b, 0.5) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
            Art {
                id: albumArt
                x: 34; y: 34
                width: 196; height: 196
                source: page.p.albumCover
                round: 0.05
                scale: 0.92 + 0.08 * sheet.open
            }
            Column {
                x: albumArt.x + albumArt.width + 28
                anchors.bottom: albumArt.bottom
                width: panel.width - x - 34
                spacing: 8
                Text { text: "Релиз"; color: Qt.rgba(1, 1, 1, 0.7); font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 13 }
                Text {
                    width: parent.width
                    text: page.p.albumTitle
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    color: "white"
                    font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: text.length > 24 ? 34 : 46
                }
                Text { text: page.p.name + (page.p.albumFacts ? " · " + page.p.albumFacts : ""); color: Qt.rgba(1, 1, 1, 0.7); font.family: "Inter"; font.pixelSize: 14 }
                Row {
                    spacing: 12
                    topPadding: 6
                    Rectangle {
                        width: 46; height: 46; radius: 23
                        color: albumPlay.containsMouse ? "white" : "#ececec"
                        opacity: artist.albumModel.count > 0 ? 1 : 0.4
                        Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: 1; name: "play"; size: 19; tint: "#0a0a0a" }
                        MouseArea { id: albumPlay; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: artist.playRelease(false) }
                    }
                    IconButton { name: "shuffle"; size: 46; glyph: 21; tip: "Перемешать"; enabled2: artist.albumModel.count > 1; onClicked: artist.playRelease(true) }
                    PillButton { anchors.verticalCenter: parent.verticalCenter; visible: page.p.albumLink !== ""; text: "Открыть в Deezer"; onClicked: artist.openLink(page.p.albumLink) }
                }
            }
            IconButton {
                x: panel.width - width - 16; y: 16
                name: "close"
                tip: "Закрыть"
                onClicked: artist.closeRelease()
            }
            Text {
                x: 34
                y: albumArt.y + albumArt.height + 30
                visible: page.p.albumStatus !== "ready"
                text: page.p.albumStatus === "loading" ? "Загружаю треки…" : page.p.albumStatus
                color: Qt.rgba(1, 1, 1, 0.55)
                font.family: "Inter"; font.pixelSize: 15
            }
            TrackList {
                x: 20
                y: albumArt.y + albumArt.height + 22
                width: panel.width - 40
                height: panel.height - y - 12
                list: "artist-album"
                numbered: true
                model: artist.albumModel
            }
        }
    }
}
