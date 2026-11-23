import QtQuick
import QtQuick.Controls

// A thin slider whose track and knob grow a little under the pointer.
Slider {
    id: slider
    implicitHeight: 24
    property real hover: hovered || pressed ? 1 : 0
    Behavior on hover { NumberAnimation { duration: 160 } }
    background: Rectangle {
        x: slider.leftPadding
        y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: slider.availableWidth
        height: 4 + 2 * slider.hover
        radius: height / 2
        color: Qt.rgba(1, 1, 1, 0.16)
        Rectangle { width: slider.visualPosition * parent.width; height: parent.height; radius: height / 2; color: "#f4f4f4" }
    }
    handle: Rectangle {
        x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
        y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: 10 + 4 * slider.hover
        height: width
        radius: width / 2
        color: "white"
        opacity: 0.4 + 0.6 * slider.hover
    }
}
