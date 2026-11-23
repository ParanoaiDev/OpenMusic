"""Pictures for the Qt Quick screens, made to the exact pixels they are shown at. A cover squeezed
to a third of its size by the graphics card comes out soft and ragged; here Qt scales it smoothly
once, cuts it to a square and rounds its corners, so a tile is one plain picture with no mask.

The address is image://art/<radius>-<corners>/<file address>: the radius in thousandths of the
side (500 is a circle), the corners as four digits for top left, top right, bottom right, bottom
left, 1 where the corner is rounded."""
from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QBrush, QImage, QImageReader, QPainter, QPainterPath
from PySide6.QtQuick import QQuickImageProvider


def outline(side, radius, corners):
    left_top, right_top, right_bottom, left_bottom = (radius if corner == "1" else 0 for corner in corners)
    path = QPainterPath()
    path.moveTo(left_top, 0)
    path.lineTo(side - right_top, 0)
    if right_top:
        path.arcTo(side - 2 * right_top, 0, 2 * right_top, 2 * right_top, 90, -90)
    path.lineTo(side, side - right_bottom)
    if right_bottom:
        path.arcTo(side - 2 * right_bottom, side - 2 * right_bottom, 2 * right_bottom, 2 * right_bottom, 0, -90)
    path.lineTo(left_bottom, side)
    if left_bottom:
        path.arcTo(0, side - 2 * left_bottom, 2 * left_bottom, 2 * left_bottom, 270, -90)
    path.lineTo(0, left_top)
    if left_top:
        path.arcTo(0, 0, 2 * left_top, 2 * left_top, 180, -90)
    path.closeSubpath()
    return path


def square(image, side, radius=0, corners="1111"):
    """The middle square of an image, side pixels wide, its chosen corners rounded by radius pixels."""
    edge = min(image.width(), image.height())
    image = image.copy((image.width() - edge) // 2, (image.height() - edge) // 2, edge, edge)
    image = image.scaled(side, side, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    radius = min(radius, side / 2)
    if radius <= 0 or "1" not in corners:
        return image
    cut = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
    cut.fill(Qt.GlobalColor.transparent)
    painter = QPainter(cut)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillPath(outline(side, radius, corners), QBrush(image))
    painter.end()
    return cut


class Pictures(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, name, size, requested):
        shape, _, address = name.partition("/")
        share, _, corners = shape.partition("-")
        reader = QImageReader(QUrl(address).toLocalFile() if "://" in address else address)
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull() or not share.isdigit() or len(corners) != 4:
            return QImage()
        side = max(requested.width(), requested.height())
        if side <= 0:
            side = min(image.width(), image.height())
        image = square(image, side, side * int(share) / 1000, corners)
        if size is not None:
            size.setWidth(side)
            size.setHeight(side)
        return image
