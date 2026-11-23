from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTransform


def pixmap(name, size=24, color="#f2f2f2"):
    result = QPixmap(size * 2, size * 2)
    result.fill(Qt.GlobalColor.transparent)
    with QPainter(result) as painter:
        painter.scale(size * 2 / 24, size * 2 / 24)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        draw(painter, name, QColor(color))
    result.setDevicePixelRatio(2)
    return result


def icon(name, color="#f2f2f2", checked=None, disabled="#4a4a4a"):
    """A drawn icon. `checked` gives the tint of a checked button, so a rail item lights up when selected."""
    result = QIcon()
    result.addPixmap(pixmap(name, 24, color), QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(pixmap(name, 24, checked or color), QIcon.Mode.Normal, QIcon.State.On)
    result.addPixmap(pixmap(name, 24, disabled), QIcon.Mode.Disabled, QIcon.State.Off)
    return result


def draw(painter, name, tint):
    path = QPainterPath()
    filled = False
    if name == "wave":
        for x, height in ((4, 4), (8, 10), (12, 17), (16, 11), (20, 5)):
            path.moveTo(x, 12 - height / 2)
            path.lineTo(x, 12 + height / 2)
    elif name == "disc":
        path.addEllipse(QRectF(3, 3, 18, 18))
        path.addEllipse(QRectF(9, 9, 6, 6))
        path.moveTo(12, 5.7)
        path.quadTo(15.7, 5.7, 17.5, 9)
        path.moveTo(6.5, 15)
        path.quadTo(8.3, 18.3, 12, 18.3)
    elif name == "cloud":
        path.moveTo(10, 17.5)
        path.lineTo(10, 11)
        path.cubicTo(10, 5, 19, 5, 19, 11)
        path.cubicTo(23.8, 11, 23.5, 17.5, 19, 17.5)
        path.closeSubpath()
        for x, height in ((3, 3), (6, 6)):
            path.moveTo(x, 17.5 - height)
            path.lineTo(x, 17.5)
    elif name == "table":
        path.addRoundedRect(QRectF(4, 4.5, 16, 15), 2, 2)
        path.moveTo(4, 9.5)
        path.lineTo(20, 9.5)
        path.moveTo(10, 9.5)
        path.lineTo(10, 19.5)
        path.moveTo(4, 14.5)
        path.lineTo(20, 14.5)
    elif name == "archive":
        path.addRoundedRect(QRectF(3.5, 4.5, 17, 4.5), 1.5, 1.5)
        path.moveTo(5.5, 9)
        path.lineTo(5.5, 19.5)
        path.lineTo(18.5, 19.5)
        path.lineTo(18.5, 9)
        path.moveTo(10, 13)
        path.lineTo(14, 13)
    elif name == "folder":
        path.moveTo(3.5, 18)
        path.lineTo(3.5, 7)
        path.quadTo(3.5, 5.5, 5, 5.5)
        path.lineTo(10, 5.5)
        path.lineTo(12, 8)
        path.lineTo(19, 8)
        path.quadTo(20.5, 8, 20.5, 9.5)
        path.lineTo(20.5, 18)
        path.quadTo(20.5, 19.5, 19, 19.5)
        path.lineTo(5, 19.5)
        path.quadTo(3.5, 19.5, 3.5, 18)
    elif name == "home":
        path.moveTo(3.5, 11)
        path.lineTo(12, 4)
        path.lineTo(20.5, 11)
        path.moveTo(6, 9.2)
        path.lineTo(6, 19.5)
        path.lineTo(18, 19.5)
        path.lineTo(18, 9.2)
        path.moveTo(10, 19.5)
        path.lineTo(10, 14.5)
        path.lineTo(14, 14.5)
        path.lineTo(14, 19.5)
    elif name == "library":
        path.moveTo(5, 4.5)
        path.lineTo(5, 19.5)
        path.moveTo(9.5, 4.5)
        path.lineTo(9.5, 19.5)
        path.moveTo(14, 5.5)
        path.lineTo(19, 19)
    elif name == "lyrics":
        path.moveTo(4.5, 6.5)
        path.lineTo(15, 6.5)
        path.moveTo(4.5, 11)
        path.lineTo(12, 11)
        path.moveTo(4.5, 15.5)
        path.lineTo(10, 15.5)
        path.addEllipse(QRectF(14, 13.5, 4.5, 4))
        path.moveTo(18.5, 15.5)
        path.lineTo(18.5, 6)
        path.lineTo(20.5, 7)
    elif name in ("heart", "heart-filled"):
        path.moveTo(12, 19.5)
        path.cubicTo(5, 14.5, 3.5, 11.5, 3.5, 8.8)
        path.cubicTo(3.5, 6.2, 5.5, 4.5, 7.8, 4.5)
        path.cubicTo(9.6, 4.5, 11, 5.5, 12, 7)
        path.cubicTo(13, 5.5, 14.4, 4.5, 16.2, 4.5)
        path.cubicTo(18.5, 4.5, 20.5, 6.2, 20.5, 8.8)
        path.cubicTo(20.5, 11.5, 19, 14.5, 12, 19.5)
        path.closeSubpath()
        filled = name == "heart-filled"
    elif name == "shuffle":
        path.moveTo(3.5, 7)
        path.lineTo(7, 7)
        path.cubicTo(12, 7, 12, 17, 17, 17)
        path.lineTo(20, 17)
        path.moveTo(3.5, 17)
        path.lineTo(7, 17)
        path.cubicTo(9.2, 17, 10.3, 15.2, 11.2, 13.4)
        path.moveTo(12.8, 10.6)
        path.cubicTo(13.7, 8.8, 14.8, 7, 17, 7)
        path.lineTo(20, 7)
        path.moveTo(17.5, 4.5)
        path.lineTo(20, 7)
        path.lineTo(17.5, 9.5)
        path.moveTo(17.5, 14.5)
        path.lineTo(20, 17)
        path.lineTo(17.5, 19.5)
    elif name in ("repeat", "repeat-one"):
        path.moveTo(4.5, 11.5)
        path.lineTo(4.5, 9.5)
        path.quadTo(4.5, 7, 7, 7)
        path.lineTo(18.5, 7)
        path.moveTo(16, 4.5)
        path.lineTo(18.5, 7)
        path.lineTo(16, 9.5)
        path.moveTo(19.5, 12.5)
        path.lineTo(19.5, 14.5)
        path.quadTo(19.5, 17, 17, 17)
        path.lineTo(5.5, 17)
        path.moveTo(8, 14.5)
        path.lineTo(5.5, 17)
        path.lineTo(8, 19.5)
        if name == "repeat-one":
            path.moveTo(11.2, 10.8)
            path.lineTo(12.4, 10)
            path.lineTo(12.4, 14)
    elif name == "queue":
        path.moveTo(4, 6.5)
        path.lineTo(16, 6.5)
        path.moveTo(4, 11)
        path.lineTo(16, 11)
        path.moveTo(4, 15.5)
        path.lineTo(11, 15.5)
        path.moveTo(15, 13.5)
        path.lineTo(20, 16.5)
        path.lineTo(15, 19.5)
        path.closeSubpath()
    elif name == "radio":
        path.addEllipse(QRectF(9.5, 9.5, 5, 5))
        path.moveTo(7, 7)
        path.quadTo(4, 12, 7, 17)
        path.moveTo(17, 7)
        path.quadTo(20, 12, 17, 17)
        path.moveTo(4.5, 4.5)
        path.quadTo(-0.5, 12, 4.5, 19.5)
        path.moveTo(19.5, 4.5)
        path.quadTo(24.5, 12, 19.5, 19.5)
    elif name == "video":
        path.addRoundedRect(QRectF(3, 5.5, 18, 13), 4, 4)
        path.moveTo(10.5, 9)
        path.lineTo(15, 12)
        path.lineTo(10.5, 15)
        path.closeSubpath()
    elif name == "sliders":
        for x, knob in ((6, 9), (12, 15), (18, 7)):
            path.moveTo(x, 4.5)
            path.lineTo(x, 19.5)
            path.addEllipse(QPointF(x, knob), 2.2, 2.2)
    elif name == "settings":
        import math
        points = []
        for tooth in range(8):
            base = tooth * 45
            for radius, angle in ((7.0, base - 17), (9.4, base - 8), (9.4, base + 8), (7.0, base + 17)):
                points.append(QPointF(12 + radius * math.cos(math.radians(angle)), 12 + radius * math.sin(math.radians(angle))))
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        path.addEllipse(QPointF(12, 12), 3.1, 3.1)
    elif name == "plus":
        path.moveTo(12, 5)
        path.lineTo(12, 19)
        path.moveTo(5, 12)
        path.lineTo(19, 12)
    elif name == "close":
        path.moveTo(6.5, 6.5)
        path.lineTo(17.5, 17.5)
        path.moveTo(17.5, 6.5)
        path.lineTo(6.5, 17.5)
    elif name == "back":
        path.moveTo(14.5, 5.5)
        path.lineTo(8, 12)
        path.lineTo(14.5, 18.5)
    elif name == "chevron":
        path.moveTo(9.5, 5.5)
        path.lineTo(16, 12)
        path.lineTo(9.5, 18.5)
    elif name == "link":
        links = QPainterPath()
        links.addRoundedRect(QRectF(1.5, 8.5, 11.5, 7), 3.5, 3.5)
        links.addRoundedRect(QRectF(11, 8.5, 11.5, 7), 3.5, 3.5)
        path = QTransform().translate(12, 12).rotate(-45).translate(-12, -12).map(links)
    elif name == "external":
        path.moveTo(7, 17)
        path.lineTo(17, 7)
        path.moveTo(8.5, 7)
        path.lineTo(17, 7)
        path.lineTo(17, 15.5)
    elif name == "search":
        path.addEllipse(QRectF(4, 4, 11.5, 11.5))
        path.moveTo(14.5, 14.5)
        path.lineTo(20, 20)
    elif name == "trash":
        path.moveTo(4.5, 7)
        path.lineTo(19.5, 7)
        path.moveTo(9.5, 7)
        path.lineTo(10, 4.5)
        path.lineTo(14, 4.5)
        path.lineTo(14.5, 7)
        path.moveTo(6.5, 7)
        path.lineTo(7.5, 19.5)
        path.lineTo(16.5, 19.5)
        path.lineTo(17.5, 7)
    elif name == "note":
        path.addEllipse(QRectF(4.5, 14.5, 5.5, 4.5))
        path.addEllipse(QRectF(13, 13, 5.5, 4.5))
        path.moveTo(10, 16.8)
        path.lineTo(10, 5.5)
        path.lineTo(18.5, 4)
        path.lineTo(18.5, 15.2)
    elif name == "volume":
        path.moveTo(4, 10)
        path.lineTo(7, 10)
        path.lineTo(11, 6)
        path.lineTo(11, 18)
        path.lineTo(7, 14)
        path.lineTo(4, 14)
        path.closeSubpath()
        path.moveTo(15, 9)
        path.quadTo(18, 12, 15, 15)
        path.moveTo(18, 6)
        path.quadTo(24, 12, 18, 18)
    elif name == "more":
        for x in (6, 12, 18):
            path.addEllipse(QPointF(x, 12), 1.6, 1.6)
        filled = True
    elif name in ("previous", "next"):
        flip = QTransform()
        if name == "previous":
            flip = QTransform(-1, 0, 0, 1, 24, 0)
        shape = QPainterPath()
        shape.moveTo(6, 6)
        shape.lineTo(15, 12)
        shape.lineTo(6, 18)
        shape.closeSubpath()
        shape.addRoundedRect(QRectF(16, 6, 2.6, 12), 1, 1)
        path = flip.map(shape)
        filled = True
    elif name == "play":
        path.moveTo(8, 5)
        path.lineTo(19, 12)
        path.lineTo(8, 19)
        path.closeSubpath()
        filled = True
    elif name == "pause":
        path.addRoundedRect(QRectF(6.5, 5, 3.8, 14), 0.9, 0.9)
        path.addRoundedRect(QRectF(13.7, 5, 3.8, 14), 0.9, 0.9)
        filled = True
    if filled:
        painter.fillPath(path, tint)
    else:
        painter.drawPath(path)


SIZE = QSize(24, 24)
