import QtQuick

// Wheel scrolling for a Flickable that glides: a mouse wheel notch moves a fair distance with an
// eased glide, a touchpad moves by its own pixels. Place it on the Flickable's parent and make the
// Flickable non-interactive, so the wheel reaches this handler and not Flickable's own crawl.
//
// A handler takes every wheel event it is offered, and the items under it never see that event.
// So one for a row inside a page that scrolls must be offered only its own events: "horizontal"
// takes sideways scrolling alone, "shifted" takes the wheel turned with Shift held, and the plain
// wheel passes through both to the page.
WheelHandler {
    id: wheel
    property Flickable flick
    property bool horizontal: false
    property bool shifted: false
    // How far one notch of the wheel moves: about a third of what is on screen.
    property real step: flick ? Math.max(220, Math.min(460, (horizontal ? flick.width * 0.25 : flick.height * 0.32))) : 220
    target: null
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    orientation: horizontal && !shifted ? Qt.Horizontal : Qt.Vertical
    acceptedModifiers: shifted ? Qt.ShiftModifier : Qt.KeyboardModifierMask
    readonly property real span: flick ? Math.max(0, horizontal ? flick.contentWidth - flick.width : flick.contentHeight - flick.height) : 0
    property real goal: 0
    onWheel: (event) => {
        if (!flick || span <= 0) return
        var sideways = horizontal && !shifted
        var angle = sideways ? event.angleDelta.x : event.angleDelta.y
        var pixels = sideways ? event.pixelDelta.x : event.pixelDelta.y
        if (!angle && !pixels) return
        var now = horizontal ? flick.contentX : flick.contentY
        var base = glide.running ? goal : now
        // A touchpad says when a swipe begins and ends and how many pixels the fingers moved. A wheel
        // has no such phases; some systems give its notch a few pixels too, which are not its step.
        var fingers = pixels !== 0 && (event.phase !== Qt.NoScrollPhase || !angle)
        goal = Math.round(Math.max(0, Math.min(span, base - (fingers ? pixels : angle / 120 * step))))
        if (fingers) {
            glide.stop()
            if (horizontal) flick.contentX = goal; else flick.contentY = goal
        } else {
            glide.to = goal
            glide.restart()
        }
    }
    property NumberAnimation glide: NumberAnimation {
        target: wheel.flick
        property: wheel.horizontal ? "contentX" : "contentY"
        duration: 340
        easing.type: Easing.OutCubic
    }
}
