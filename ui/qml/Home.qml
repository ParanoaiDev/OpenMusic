import QtQuick
import QtQuick.Controls
import QtQuick.Effects

// The home screen, drawn by the graphics card. Python (ui/home_quick.py) hands over the lists
// through "home"; scrolling, hovering and every animation happen here at the screen's own pace.
Rectangle {
    id: root
    color: "#060608"
    // False while the start screen still covers the window, so the title comes in when it can be seen.
    property bool shown: true
    // The moving top steps with the screen's own frames: a timer of its own drifts against them and
    // the movement stutters. It stops while scrolled out of sight or while the window is in the back.
    property real t: 0
    // The bass comes from Python twenty times a second; followed here every frame, so what sways with
    // it moves smoothly instead of in steps.
    property real beat: 0
    property bool heroSeen: page.contentY < hero.height * 0.9
    FrameAnimation {
        running: root.visible && root.heroSeen && Qt.application.state === Qt.ApplicationActive && !app.settingsMap.calm
        onRunningChanged: if (!running) root.beat = 0
        onTriggered: {
            var dt = Math.min(0.1, frameTime)
            root.t += dt
            root.beat += (home.bass - root.beat) * (1 - Math.exp(-dt * 12))
            var k = 1 - Math.exp(-dt * 6)
            cloud.mx += (cloud.tx - cloud.mx) * k
            cloud.my += (cloud.ty - cloud.my) * k
        }
    }
    // Whole pixels everywhere: a tile that starts between two pixels is drawn blurred.
    readonly property int pad: Math.round(Math.max(40, Math.min(90, width * 0.035)))
    readonly property int tile: Math.round(Math.max(170, Math.min(240, (width - pad * 2) / 9)) / 4) * 4
    readonly property int mixTile: Math.round(tile * 1.35 / 4) * 4

    // The mood of the top of the screen: the colours of the favourite covers, or of what plays.
    property color col0: home.colours[0]
    property color col1: home.colours[1]
    property color col2: home.colours[2]
    property color col3: home.colours[3]
    Behavior on col0 { ColorAnimation { duration: 1600 } }
    Behavior on col1 { ColorAnimation { duration: 1600 } }
    Behavior on col2 { ColorAnimation { duration: 1600 } }
    Behavior on col3 { ColorAnimation { duration: 1600 } }

    Flickable {
        id: page
        anchors.fill: parent
        contentWidth: width
        contentHeight: content.height + 80
        boundsBehavior: Flickable.StopAtBounds
        interactive: false
        pixelAligned: true
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 8 }

        Column {
            id: content
            width: page.width
            spacing: 44

            // ---- "Мой поток": the big panel at the top, as in the references ----
            Item {
                id: hero
                width: parent.width
                height: Math.round(Math.max(460, Math.min(680, root.height * 0.56)))
                ShaderEffect {
                    anchors.fill: parent
                    property real time: root.t
                    property real bass: root.beat
                    property real aspect: width / Math.max(1, height)
                    property color c0: root.col0
                    property color c1: root.col1
                    property color c2: root.col2
                    property color c3: root.col3
                    property color mood: root.col0
                    property vector4d spot: Qt.vector4d(0.5, 0.55, 0.5, 0.6)
                    fragmentShader: "mesh.frag.qsb"
                }
                // Fades into the page below.
                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(0.02, 0.02, 0.03, 0.0) }
                        GradientStop { position: 0.7; color: Qt.rgba(0.02, 0.02, 0.03, 0.2) }
                        GradientStop { position: 1.0; color: "#060608" }
                    }
                }
                // Covers floating around the middle, drifting and turning a little, following the pointer.
                Item {
                    id: cloud
                    anchors.fill: parent
                    // Where the pointer is, and where the covers lean to: the lean follows it smoothly,
                    // stepped with the same frames as the drift. An animation restarted on every move
                    // of the mouse made the covers jerk.
                    readonly property real tx: hover.hovered ? hover.point.position.x / Math.max(1, width) - 0.5 : 0
                    readonly property real ty: hover.hovered ? hover.point.position.y / Math.max(1, height) - 0.5 : 0
                    property real mx: 0
                    property real my: 0
                    HoverHandler { id: hover }
                    Repeater {
                        model: home.floating
                        Item {
                            readonly property real angle: index / Math.max(1, home.floating.count) * Math.PI * 2 + root.t * 0.05
                            readonly property real depth: 0.55 + 0.45 * ((index * 37) % 10) / 10
                            readonly property int size: Math.round(hero.height * 0.24 * depth)
                            width: size; height: size
                            // On a wide ellipse that leaves the middle free for the title and the button.
                            readonly property real side: Math.cos(angle)
                            x: cloud.width / 2 + (side < 0 ? -1 : 1) * (0.24 + 0.2 * Math.abs(side)) * cloud.width - size / 2 + cloud.mx * 40 * depth
                            y: cloud.height * 0.5 + Math.sin(angle) * cloud.height * 0.29 - size / 2 + Math.sin(root.t * 0.7 + index) * 10 + cloud.my * 30 * depth
                            // The path keeps the middle free, so at the top and the bottom of its round a
                            // cover crosses from one side to the other: it fades out there and comes in on
                            // the other side instead of jumping across.
                            readonly property real edge: Math.max(0, Math.min(1, (Math.abs(side) - 0.04) / 0.22))
                            property real arrived: floatArt.ready ? 1 : 0
                            Behavior on arrived { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
                            opacity: (0.45 + 0.5 * depth) * arrived * edge * edge * (3 - 2 * edge)
                            visible: opacity > 0.003
                            scale: 0.86 + 0.14 * edge
                            z: depth * 10
                            transform: Rotation { origin.x: width / 2; origin.y: height / 2; axis { x: 0; y: 1; z: 0 }
                                                  angle: Math.sin(root.t * 0.3 + index) * 16 - cloud.mx * 20 }
                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: -1
                                anchors.topMargin: 10
                                radius: width * 0.08
                                color: "black"
                                opacity: 0.35
                                antialiasing: true
                            }
                            Art { id: floatArt; anchors.fill: parent; source: entry; round: 0.08; turning: true }
                        }
                    }
                }
                Column {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: hero.height * 0.02
                    spacing: 14
                    z: 20
                    HeroTitle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        t: root.t
                        bass: root.beat
                        c0: root.col0; c1: root.col1; c2: root.col2
                        greeting: home.greeting
                        caption: home.streamCaption
                        size: Math.round(Math.min(120, hero.height * 0.17))
                        go: root.shown
                    }
                    Item { width: 1; height: 10 }
                    Item {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 96; height: 96
                        HoverCard {
                            id: bigPlay
                            anchors.fill: parent
                            onClicked: home.startStream()
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: 84 + 10 * bigPlay.lift + 8 * root.beat; height: width
                            radius: width / 2
                            color: "white"
                            opacity: 0.18 * (1 + bigPlay.lift)
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: 76 * bigPlay.scale; height: width
                            radius: width / 2
                            color: "#f4f4f4"
                            Text {
                                anchors.centerIn: parent
                                anchors.horizontalCenterOffset: home.streaming ? 0 : 3
                                text: home.streaming ? "❚❚" : "▶"
                                color: "#0a0a0a"
                                font.pixelSize: home.streaming ? 24 : 30
                            }
                        }
                    }
                }
                // Our name in the corner, in the two weights of the logo, with a light passing over it.
                Item {
                    x: root.pad; y: 26
                    z: 30
                    width: brand.width + 40; height: 36
                    layer.enabled: true
                    layer.effect: ShaderEffect {
                        property real time: root.t
                        property real shine: (root.t * 0.09 + 0.6) % 2.4 - 0.4
                        property real lift: 0.86
                        property color c0: root.col0
                        property color c1: root.col1
                        property color c2: root.col2
                        fragmentShader: "fill.frag.qsb"
                    }
                    Row {
                        id: brand
                        anchors.verticalCenter: parent.verticalCenter
                        Text { text: "Open"; color: "white"; font.family: "Inter Display"; font.weight: Font.Light; font.pixelSize: 25; font.letterSpacing: 0.3 }
                        Text { text: "Music"; color: "white"; font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 25; font.letterSpacing: 0.3 }
                    }
                }
                // Search and import, as at the top of the references.
                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: root.pad
                    y: 26
                    spacing: 10
                    z: 30
                    PillButton { text: "Поиск"; onClicked: home.openSearch() }
                    PillButton { text: "+ Добавить музыку"; primary: true; onClicked: home.openImport() }
                }
            }

            // ---- Quick access: circles, as the speed dial of the references ----
            Column {
                x: root.pad
                width: parent.width - root.pad * 2
                spacing: 18
                visible: home.dial.count > 0
                Text { text: "Быстрый доступ"; color: "white"; font.family: "Inter Display"; font.weight: Font.Bold; font.pixelSize: 26 }
                Row {
                    spacing: 26
                    Repeater {
                        model: home.dial
                        HoverCard {
                            width: 124; height: 160
                            onClicked: home.dialChosen(index)
                            Rectangle {
                                id: ring
                                width: 124; height: 124
                                radius: 62
                                gradient: Gradient {
                                    GradientStop { position: 0; color: entry.colour }
                                    GradientStop { position: 1; color: Qt.darker(entry.colour, 2.2) }
                                }
                                Art { anchors.fill: parent; source: entry.picture; round: 0.5; visible: entry.picture !== "" }
                                Image {
                                    anchors.centerIn: parent
                                    width: 56; height: 56
                                    visible: entry.picture === ""
                                    source: entry.glyph
                                    sourceSize: Qt.size(56 * Screen.devicePixelRatio, 56 * Screen.devicePixelRatio)
                                }
                                Rectangle { anchors.fill: parent; radius: 62; color: "transparent"; border.width: 2; border.color: Qt.rgba(1, 1, 1, parent.parent.hovered ? 0.6 : 0.12)
                                            Behavior on border.color { ColorAnimation { duration: 200 } } }
                            }
                            Text {
                                anchors.horizontalCenter: ring.horizontalCenter
                                y: 134
                                width: 140
                                horizontalAlignment: Text.AlignHCenter
                                elide: Text.ElideRight
                                text: entry.name
                                color: Qt.rgba(1, 1, 1, 0.85)
                                font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 14
                            }
                        }
                    }
                }
            }

            // ---- Mixes: big tiles in the colour of their covers, as "Your Mixes" ----
            Shelf {
                x: root.pad
                width: parent.width - root.pad * 2
                title: "Ваши миксы"
                visible: home.mixes.count > 0
                itemHeight: root.mixTile + 60
                model: home.mixes
                delegate: HoverCard {
                    id: mixCard
                    readonly property color tone: entry.colour
                    width: root.mixTile
                    height: width + 60
                    onClicked: home.playMix(index)
                    RectangularShadow {
                        anchors.fill: mixArt
                        radius: mixArt.width * 0.06
                        blur: 60
                        spread: 2
                        color: entry.colour
                        opacity: 0.7 * mixCard.lift
                        visible: mixCard.lift > 0.01
                    }
                    Item {
                        id: mixArt
                        width: parent.width; height: width
                        Repeater {
                            model: entry.covers
                            Art {
                                x: index % 2 * mixArt.width / 2
                                y: Math.floor(index / 2) * mixArt.width / 2
                                width: mixArt.width / 2; height: width
                                source: modelData
                                round: 0.12
                                corners: ["1000", "0100", "0001", "0010"][index]
                            }
                        }
                        Rectangle {
                            anchors.fill: parent
                            radius: width * 0.06
                            gradient: Gradient {
                                GradientStop { position: 0.35; color: "transparent" }
                                GradientStop { position: 1.0; color: Qt.rgba(mixCard.tone.r * 0.6, mixCard.tone.g * 0.6, mixCard.tone.b * 0.6, 0.95) }
                            }
                        }
                        Text {
                            x: 18; anchors.bottom: parent.bottom; anchors.bottomMargin: 14
                            text: "МИКС " + entry.number
                            color: "white"
                            font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: Math.round(parent.width * 0.14)
                        }
                    }
                    Text {
                        y: mixArt.height + 12
                        width: parent.width
                        elide: Text.ElideRight
                        text: entry.artists
                        color: Qt.rgba(1, 1, 1, 0.75)
                        font.family: "Inter"; font.pixelSize: 14
                    }
                }
            }

            // ---- Artists ----
            Shelf {
                x: root.pad
                width: parent.width - root.pad * 2
                title: "Любимые артисты"
                visible: home.artists.count > 0
                itemHeight: root.tile + 70
                model: home.artists
                delegate: HoverCard {
                    id: artistCard
                    width: root.tile
                    height: width + 70
                    onClicked: home.showArtist(entry.name)
                    RectangularShadow {
                        anchors.fill: face
                        radius: face.width / 2
                        blur: 50
                        color: entry.colour
                        opacity: 0.7 * artistCard.lift
                        visible: artistCard.lift > 0.01
                    }
                    Art { id: face; width: parent.width; height: width; source: entry.picture; round: 0.5 }
                    Text {
                        y: face.height + 14
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        text: entry.name
                        color: "white"
                        font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15
                    }
                    Text {
                        y: face.height + 36
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: entry.caption
                        color: Qt.rgba(1, 1, 1, 0.5)
                        font.family: "Inter"; font.pixelSize: 13
                    }
                }
            }

            // ---- Tracks: recently played, then the library's ----
            Repeater {
                model: [ { title: "Недавно играли", list: "recent" }, { title: "Треки из медиатеки", list: "tracks" } ]
                Shelf {
                    id: trackShelf
                    x: root.pad
                    width: content.width - root.pad * 2
                    title: modelData.title
                    readonly property var items: modelData.list === "recent" ? home.recent : home.tracks
                    readonly property string kind: modelData.list
                    visible: items.count > 0
                    itemHeight: root.tile + 66
                    model: items
                    delegate: HoverCard {
                        id: trackCard
                        width: root.tile
                        height: width + 66
                        onClicked: home.playTrack(trackShelf.kind, index)
                        onRightClicked: home.trackMenu(trackShelf.kind, index)
                        onEntered: home.hovered(trackShelf.kind, index)
                        RectangularShadow {
                            anchors.fill: art
                            radius: art.width * 0.06
                            blur: 56
                            spread: 2
                            color: entry.colour
                            opacity: 0.8 * trackCard.lift
                            visible: trackCard.lift > 0.01
                        }
                        Art { id: art; width: parent.width; height: width; source: entry.cover }
                        Rectangle {
                            x: art.width - width - 12; y: Math.round(art.height - height - 12 + (1 - trackCard.lift) * 10)
                            width: 48; height: 48; radius: 24
                            color: "#f4f4f4"
                            opacity: trackCard.lift
                            Text { anchors.centerIn: parent; anchors.horizontalCenterOffset: 2; text: "▶"; color: "#0a0a0a"; font.pixelSize: 18 }
                        }
                        Text {
                            y: art.height + 12
                            width: parent.width
                            elide: Text.ElideRight
                            text: entry.title
                            color: "white"
                            font.family: "Inter"; font.weight: Font.DemiBold; font.pixelSize: 15
                        }
                        Text {
                            y: art.height + 34
                            width: parent.width
                            elide: Text.ElideRight
                            text: entry.artist
                            color: Qt.rgba(1, 1, 1, 0.5)
                            font.family: "Inter"; font.pixelSize: 13
                        }
                    }
                }
            }
        }
    }

    // Shown with an empty library, under the panel of "Мой поток" (in the middle of the page it
    // lay over the play button).
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.round(Math.max(460, Math.min(680, root.height * 0.56))) + 28
        spacing: 16
        visible: home.empty
        z: 50
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Соберите свой вкус"; color: "white"; font.family: "Inter Display"; font.weight: Font.Black; font.pixelSize: 44 }
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Добавьте плейлист Spotify, Deezer, Яндекс Музыки, лайки SoundCloud или папку с музыкой"; color: Qt.rgba(1, 1, 1, 0.6); font.family: "Inter"; font.pixelSize: 16 }
        PillButton { anchors.horizontalCenter: parent.horizontalCenter; text: "+ Добавить музыку"; primary: true; onClicked: home.openImport() }
    }
    SmoothWheel { flick: page }
}
