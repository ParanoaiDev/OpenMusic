import QtQuick

// A picture with rounded corners (or a circle), cross-fading when it changes, crisp at any size.
Item {
    id: holder
    property url source
    property real radius: 8
    property bool circle: false
    Art {
        anchors.fill: parent
        source: holder.source.toString()
        round: holder.circle ? 0.5 : holder.radius / Math.max(1, Math.max(holder.width, holder.height))
    }
}
