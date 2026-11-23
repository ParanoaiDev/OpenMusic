import QtQuick
import QtQuick.Controls
import QtQuick.Window

// The window of OpenMusic: the rail on the left, the pages, the player at the bottom, and the
// panels, menus and messages over them. Everything is drawn by the graphics card.
ApplicationWindow {
    id: win
    width: 1440
    height: 900
    minimumWidth: 1080
    minimumHeight: 700
    visible: true
    title: "OpenMusic"
    color: "#060608"
    property bool importOpen: false
    onImportOpenChanged: if (importOpen) { importer.open(); importOpen = false }
    // Ways for the app and its tests to open the panels.
    property string openPanel: ""
    onOpenPanelChanged: {
        if (openPanel === "queue") queue.open()
        else if (openPanel === "sound") sound.open()
        else if (openPanel === "none") { queue.close(); sound.close(); importer.close(); menu.close() }
        openPanel = ""
    }
    onClosing: (close) => { close.accepted = app.requestClose() }

    // At the start the interface comes in from the edges as the start screen lets it show.
    Rail {
        id: rail
        x: -(1 - intro.reveal) * width
        height: parent.height - bar.height
        showLogo: intro.done
        onAddClicked: importer.open()
    }
    Item {
        id: pages
        x: rail.width
        width: parent.width - rail.width
        height: parent.height - bar.height
        clip: true
        transform: Translate { y: (1 - intro.reveal) * 40 }
        PageHost { index: 0; Home { anchors.fill: parent; shown: intro.reveal > 0.3 } }
        PageHost { index: 1; SearchPage { id: search; anchors.fill: parent } }
        PageHost { index: 2; LibraryPage { anchors.fill: parent } }
        PageHost { index: 3; NowPlaying { anchors.fill: parent } }
        PageHost { index: 4; SettingsPage { anchors.fill: parent } }
        PageHost { index: 5; ArtistPage { anchors.fill: parent } }
    }
    PlayerBar {
        id: bar
        anchors.bottom: parent.bottom
        width: parent.width
        transform: Translate { y: (1 - intro.reveal) * bar.height }
        onLyricsClicked: app.setPage(app.stateMap.page === 3 ? 0 : 3)
        onQueueClicked: queue.opened ? queue.close() : queue.open()
        onSoundClicked: sound.open()
    }
    Toast {
        id: toast
        anchors.horizontalCenter: pages.horizontalCenter
        anchors.bottom: bar.top
        anchors.bottomMargin: 18
        z: 50
    }
    Intro { id: intro; wanted: app.stateMap.intro; mark: app.stateMap.logoBig }
    ImportSheet { id: importer }
    QueueDrawer { id: queue }
    SoundPanel { id: sound }
    TrackMenu { id: menu }
    NameDialog { id: nameDialog }
    ConfirmDialog { id: confirm }
    Connections {
        target: app
        function onMenuRequested(info) { menu.openFor(info) }
        function onToast(message, error, sticky) { toast.say(message, error, sticky) }
        function onAskName(title, value, action, arg) { nameDialog.ask(title, value, action, arg) }
        function onAskConfirm(text, action, arg) { confirm.ask(text, action, arg) }
    }
    Shortcut { sequences: ["Ctrl+K"]; onActivated: { app.setPage(1); search.focusField() } }
    Shortcut { sequences: [StandardKey.Find]; onActivated: { app.setPage(1); search.focusField() } }
    Shortcut { sequences: ["Ctrl+I"]; onActivated: importer.open() }
    Shortcut { sequences: ["Ctrl+L"]; onActivated: app.setPage(app.stateMap.page === 3 ? 0 : 3) }
    Shortcut { sequences: ["Ctrl+,"]; onActivated: app.setPage(4) }
    Shortcut { sequences: ["Alt+Left"]; enabled: app.stateMap.page === 5; onActivated: artist.back() }
    Shortcut { sequences: ["Ctrl+Up"]; onActivated: app.setVolume(Math.min(1, app.playerMap.volume + 0.05)) }
    Shortcut { sequences: ["Ctrl+Down"]; onActivated: app.setVolume(Math.max(0, app.playerMap.volume - 0.05)) }
    Shortcut { sequences: ["Ctrl+O"]; onActivated: app.openFile() }
    Shortcut { sequences: ["Ctrl+Right", "Media Next"]; onActivated: app.next() }
    Shortcut { sequences: ["Ctrl+Left", "Media Previous"]; onActivated: app.previous() }
    Shortcut { sequences: ["Media Play", "Toggle Media Play/Pause", "Ctrl+Space"]; onActivated: app.toggle() }
}
