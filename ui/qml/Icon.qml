import QtQuick

// A drawn icon of ui/icons.py, white, made dim or tinted through opacity.
Image {
    property string name
    property string tint: "#ffffff"
    property real size: 20
    width: size
    height: size
    source: name ? app.tinted(name, tint) : ""
    sourceSize: Qt.size(size * 2, size * 2)
    smooth: true
    mipmap: true
}
