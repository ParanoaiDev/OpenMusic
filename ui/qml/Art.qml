import QtQuick

// A square picture with rounded corners, crisp: ui/pictures.py makes it to the exact pixels it is
// shown at, so nothing is scaled or masked here. It comes in softly when it has loaded, and a new
// picture fades in over the one before it.
Item {
    id: art
    property string source                 // the address of the file
    property real round: 0.06              // the radius as a share of the side; 0.5 is a circle
    property string corners: "1111"        // top left, top right, bottom right, bottom left
    property bool turning: false           // set for a picture that is turned or moves between pixels
    readonly property bool ready: fresh.status === Image.Ready
    readonly property int wanted: Math.round(Math.max(width, height) * Screen.devicePixelRatio)
    // While the window is being resized the picture is stretched; it is made anew when the size settles.
    property int pixels: 0
    onWantedChanged: if (pixels === 0 && wanted > 0) pixels = wanted; else settle.restart()
    Timer { id: settle; interval: 180; onTriggered: if (art.wanted > 0) art.pixels = art.wanted }
    readonly property string address: source !== "" && pixels > 0
                                      ? "image://art/" + Math.round(round * 1000) + "-" + corners + "/" + source : ""
    onAddressChanged: show()
    Component.onCompleted: { if (wanted > 0) pixels = wanted; show() }
    function show() {
        if (fresh.source.toString() === address) return
        appear.stop()
        if (address === "") { old.source = ""; fresh.source = ""; return }
        old.source = fresh.status === Image.Ready && fresh.opacity > 0.5 ? fresh.source : ""
        fresh.opacity = 0
        fresh.source = address
        if (fresh.status === Image.Ready) appear.start()
    }
    Image {
        id: old
        anchors.fill: parent
        sourceSize: fresh.sourceSize
        visible: source.toString() !== ""
        mipmap: art.turning
        antialiasing: art.turning
    }
    Image {
        id: fresh
        anchors.fill: parent
        sourceSize: Qt.size(art.pixels, art.pixels)
        asynchronous: true
        retainWhileLoading: true
        mipmap: art.turning
        antialiasing: art.turning
        opacity: 0
        onStatusChanged: if (status === Image.Ready && opacity < 1 && !appear.running) appear.start()
    }
    NumberAnimation {
        id: appear
        target: fresh; property: "opacity"; to: 1
        duration: 380; easing.type: Easing.OutCubic
        onFinished: old.source = ""
    }
}
