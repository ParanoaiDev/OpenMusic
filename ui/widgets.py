from html import escape

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolButton, QWidget

from .icons import icon
from .motion import Hover, arrive, leave, mix


def label(value, name="", wrap=False):
    widget = QLabel(value)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def overline(value):
    widget = label(value.upper(), "overline")
    font = widget.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.6)
    widget.setFont(font)
    return widget


def blend(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(int(mix(a.red(), b.red(), t)), int(mix(a.green(), b.green(), t)),
                  int(mix(a.blue(), b.blue(), t)), int(mix(a.alpha(), b.alpha(), t)))


class Pill(QPushButton):
    """A rounded button that eases into its hover and sinks a little when pressed.
    kind: primary (white), ghost (glass), text (no fill) or chip (checkable filter)."""

    def __init__(self, text, kind="ghost", glyph=None, height=36):
        super().__init__(text)
        self.kind = kind
        self.glyph = glyph
        self.hover = Hover(self)
        self.press = Hover(self, 110)
        self.setObjectName("pill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(height)
        font = self.font()
        font.setWeight(QFont.Weight.Medium if kind == "chip" else QFont.Weight.DemiBold)
        self.setFont(font)
        if kind == "chip":
            self.setCheckable(True)
            self.toggled.connect(lambda _: self.update())

    def sizeHint(self):
        width = QFontMetrics(self.font()).horizontalAdvance(self.text()) + (28 if self.kind == "chip" else 40)
        return QSize(width + (24 if self.glyph else 0), self.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def enterEvent(self, event):
        self.hover.to(1)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover.to(0)
        self.press.to(0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.press.to(1)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.press.to(0)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h, p = self.hover.value, self.press.value
        enabled = self.isEnabled()
        area = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        scale = 1 - 0.04 * p
        painter.translate(area.center())
        painter.scale(scale, scale)
        painter.translate(-area.center())
        shape = QPainterPath()
        shape.addRoundedRect(area, area.height() / 2, area.height() / 2)
        border = None
        if self.kind == "primary" or (self.kind == "chip" and self.isChecked()):
            fill = blend("#e9e9e9", "#ffffff", h) if enabled else QColor(255, 255, 255, 34)
            ink = QColor("#0a0a0a") if enabled else QColor(255, 255, 255, 90)
        elif self.kind == "chip":
            fill = QColor(255, 255, 255, int(10 * h))
            border = QColor(255, 255, 255, int(30 + 60 * h))
            ink = blend("#8e8e8e", "#f2f2f2", h)
        elif self.kind == "text":
            fill = QColor(255, 255, 255, int(14 * h))
            ink = blend("#8e8e8e", "#f2f2f2", h)
        else:
            fill = QColor(255, 255, 255, int(16 + 20 * h)) if enabled else QColor(255, 255, 255, 8)
            border = QColor(255, 255, 255, int(28 + 44 * h))
            ink = QColor("#f2f2f2") if enabled else QColor("#5a5a5a")
        painter.fillPath(shape, fill)
        if self.hasFocus() and self.focusPolicy() != Qt.FocusPolicy.NoFocus and self.property("keyboard"):
            border = QColor(255, 255, 255, 150)
        if border is not None:
            painter.setPen(QPen(border, 1))
            painter.drawPath(shape)
        metrics = QFontMetrics(self.font())
        text_width = metrics.horizontalAdvance(self.text())
        icon_width = 22 if self.glyph else 0
        left = area.center().x() - (text_width + icon_width) / 2
        if self.glyph:
            tint = "#0a0a0a" if ink.lightness() < 128 else "#f2f2f2"
            painter.drawPixmap(QPointF(left, area.center().y() - 8), icon(self.glyph, tint).pixmap(QSize(16, 16)))
        painter.setFont(self.font())
        painter.setPen(ink)
        painter.drawText(QRectF(left + icon_width, area.top(), text_width + 2, area.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

    def focusInEvent(self, event):
        self.setProperty("keyboard", event.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason))
        super().focusInEvent(event)


def button(value, action, name="ghost", glyph=None):
    widget = Pill(value, name or "ghost", glyph)
    widget.clicked.connect(action)
    return widget


def icon_button(glyph, action, tip, size=34, glyph_size=18, color="#d8d8d8"):
    widget = QToolButton()
    widget.setIcon(icon(glyph, color))
    widget.setIconSize(QSize(glyph_size, glyph_size))
    widget.setFixedSize(size, size)
    widget.setToolTip(tip)
    widget.setAccessibleName(tip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if action:
        widget.clicked.connect(action)
    return widget


def picture(pixmap, name=""):
    widget = QLabel()
    widget.setObjectName(name)
    widget.setPixmap(pixmap)
    widget.setFixedSize(pixmap.deviceIndependentSize().toSize())
    return widget


def tile(glyph, size=44, glyph_size=22):
    widget = QLabel()
    widget.setObjectName("serviceTile")
    widget.setFixedSize(size, size)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setPixmap(icon(glyph).pixmap(QSize(glyph_size, glyph_size)))
    return widget


def set_elided(widget, value, width):
    widget.setText(widget.fontMetrics().elidedText(value, Qt.TextElideMode.ElideRight, width))
    widget.setToolTip(f"<qt>{escape(value)}</qt>" if widget.text() != value else "")


def elided(metrics, value, width):
    return metrics.elidedText(value, Qt.TextElideMode.ElideRight, int(width))


def clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear(item.layout())


def plural(count, forms):
    tail = count % 100
    if 11 <= tail <= 14:
        form = forms[2]
    else:
        form = forms[0] if count % 10 == 1 else forms[1] if 2 <= count % 10 <= 4 else forms[2]
    return f"{count} {form}"


def listening(milliseconds):
    seconds = milliseconds // 1000
    if seconds >= 3600:
        return f"{seconds // 3600} ч {seconds // 60 % 60} мин"
    if seconds >= 60:
        return f"{seconds // 60} мин"
    return f"{seconds} с"


def measure(duration, count):
    return listening(duration) if duration else plural(count, ("трек", "трека", "треков"))


class Clickable(QFrame):
    clicked = Signal()

    def __init__(self, name=""):
        super().__init__()
        self.setObjectName(name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hover = Hover(self)

    def enterEvent(self, event):
        self.hover.to(1)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover.to(0)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class Shelf(QScrollArea):
    """A horizontal row of tiles that scrolls sideways, with the wheel too, and glides when it does."""

    def __init__(self, height):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(height)
        body = QWidget()
        body.setObjectName("shelfBody")
        self.row = QHBoxLayout(body)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(18)
        self.setWidget(body)
        self.viewport().setAutoFillBackground(False)
        body.setAutoFillBackground(False)
        self.target = 0

    def fill(self, widgets):
        clear(self.row)
        for widget in widgets:
            self.row.addWidget(widget)
        self.row.addStretch()
        self.horizontalScrollBar().setValue(0)
        self.target = 0

    def wheelEvent(self, event):
        bar = self.horizontalScrollBar()
        angle = event.angleDelta().x() or (event.angleDelta().y() if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0)
        pixels = event.pixelDelta().x()
        touchpad = event.phase() != Qt.ScrollPhase.NoScrollPhase and pixels and abs(angle) < 120
        delta = pixels if touchpad else angle / 120 * 200
        if not delta or bar.maximum() == 0:
            event.ignore()
            return
        self.glide(self.target - delta)
        event.accept()

    def glide(self, value):
        from .motion import tween
        bar = self.horizontalScrollBar()
        self.target = max(0, min(bar.maximum(), value))
        tween(self, bar.value(), self.target, 420, lambda v: bar.setValue(int(v)), name="glide")

    def page(self, direction):
        self.glide(self.target + direction * self.viewport().width() * 0.8)


class Toast(QWidget):
    """A short message above the player that rises in out of a blur. While an import runs it carries
    a thin light running along its bottom edge."""

    def __init__(self, parent):
        super().__init__(parent)
        self.message = ""
        self.error = False
        self.busy = False
        self.clock = QElapsedTimer()
        self.clock.start()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.dismiss)
        self.ticker = QTimer(self)
        self.ticker.setInterval(33)
        self.ticker.timeout.connect(self.update)
        font = self.font()
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)
        self.hide()

    def say(self, message, sticky=False, error=False):
        self.message, self.error, self.busy = message, error, sticky and not error
        metrics = QFontMetrics(self.font())
        lines = message.splitlines() or [""]
        width = min(600, max(metrics.horizontalAdvance(line) for line in lines) + 52)
        height = metrics.boundingRect(0, 0, width - 44, 400, Qt.TextFlag.TextWordWrap, message).height() + 24
        self.setFixedSize(width, max(40, height))
        self.ticker.start() if self.busy else self.ticker.stop()
        if not self.isVisible():
            self.show()
            arrive(self, 380, blur=5, scale=0.96, dy=14)
        self.raise_()
        self.update()
        self.timer.stop()
        if not sticky:
            self.timer.start(6500)

    def dismiss(self):
        self.ticker.stop()
        leave(self, 240, dy=10, done=self.hide)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        shape = QPainterPath()
        shape.addRoundedRect(area, min(20, area.height() / 2), min(20, area.height() / 2))
        painter.fillPath(shape, QColor("#1b1b1b") if self.error else QColor("#f4f4f4"))
        if self.error:
            painter.setPen(QPen(QColor(255, 255, 255, 70), 1))
            painter.drawPath(shape)
        painter.setPen(QColor("#f2f2f2") if self.error else QColor("#0a0a0a"))
        painter.setFont(self.font())
        painter.drawText(area.adjusted(22, 0, -22, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)
        if self.busy:
            painter.setClipPath(shape)
            run = (self.clock.elapsed() / 1400) % 1
            x = mix(-0.4, 1.4, run) * area.width()
            light = QLinearGradient(x - 90, 0, x + 90, 0)
            light.setColorAt(0, QColor(0, 0, 0, 0))
            light.setColorAt(0.5, QColor(0, 0, 0, 120))
            light.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(QRectF(area.left(), area.bottom() - 3, area.width(), 3), light)
