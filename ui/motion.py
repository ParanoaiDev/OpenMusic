"""Motion: every appearance, hover and transition in OpenMusic goes through here.

The vocabulary comes from the references: things arrive out of a blur while fading in and settling,
popovers grow from slightly smaller, lists come in one row after another, and text is revealed
left to right with a soft edge."""
from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPointF, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtWidgets import QGraphicsEffect
from shiboken6 import isValid

OUT = QEasingCurve.Type.OutCubic
SOFT = QEasingCurve.Type.InOutSine


_running = {}


def running(owner, name):
    animation = _running.get((id(owner), name))
    return animation is not None and isValid(animation) and animation.state() == QVariantAnimation.State.Running


def tween(owner, start, end, duration, step, done=None, curve=OUT, name="tween"):
    """Runs step(value) from start to end. A new tween with the same name on the owner replaces the old one."""
    slot = (id(owner), name)
    previous = _running.pop(slot, None)
    if previous is not None and isValid(previous):
        previous.stop()
        previous.deleteLater()
    animation = QVariantAnimation(owner)
    animation.setStartValue(float(start))
    animation.setEndValue(float(end))
    animation.setDuration(max(1, int(duration)))
    animation.setEasingCurve(curve)
    animation.valueChanged.connect(step)

    def finished():
        if _running.get(slot) is animation:
            del _running[slot]
        animation.deleteLater()
        if done:
            done()

    animation.finished.connect(finished)
    _running[slot] = animation
    animation.start()
    return animation


def mix(a, b, t):
    return a + (b - a) * t


class MotionEffect(QGraphicsEffect):
    """Draws a widget faded, blurred, scaled and shifted. Taken off again once it settles,
    so the widget renders normally between animations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.opacity = 1.0
        self.blur = 0.0
        self.scale = 1.0
        self.dx = 0.0
        self.dy = 0.0

    def set(self, opacity=None, blur=None, scale=None, dx=None, dy=None):
        for name, value in (("opacity", opacity), ("blur", blur), ("scale", scale), ("dx", dx), ("dy", dy)):
            if value is not None:
                setattr(self, name, value)
        self.update()

    def boundingRectFor(self, rect):
        return rect.adjusted(-abs(self.dx) - 2, -abs(self.dy) - 2, abs(self.dx) + 2, abs(self.dy) + 2)

    def draw(self, painter):
        if self.opacity <= 0.001:
            return
        # PySide returns only the pixmap; with NoPad it covers the source's bounding rect exactly.
        pixmap = self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates, mode=QGraphicsEffect.PixmapPadMode.NoPad)
        if pixmap.isNull():
            return
        offset = self.sourceBoundingRect(Qt.CoordinateSystem.LogicalCoordinates).topLeft()
        ratio = pixmap.devicePixelRatio()
        if self.blur > 0.6:
            factor = 1 + self.blur
            small = pixmap.scaled(max(1, int(pixmap.width() / factor)), max(1, int(pixmap.height() / factor)),
                                  Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pixmap = small.scaled(pixmap.width(), pixmap.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            pixmap.setDevicePixelRatio(ratio)
        painter.save()
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(painter.opacity() * self.opacity)
        area = QRectF(QPointF(offset), pixmap.deviceIndependentSize())
        centre = area.center()
        painter.translate(centre.x() + self.dx, centre.y() + self.dy)
        painter.scale(self.scale, self.scale)
        painter.translate(-centre.x(), -centre.y())
        painter.drawPixmap(QPointF(offset), pixmap)
        painter.restore()


def arrive(widget, duration=420, blur=7.0, scale=1.0, dx=0.0, dy=16.0, delay=0, done=None):
    """Brings a widget in out of a blur: transparent, soft and a little off its place, then sharp and settled."""
    effect = MotionEffect(widget)
    effect.set(0.0, blur, scale, dx, dy)
    widget.setGraphicsEffect(effect)

    def step(t):
        if widget.graphicsEffect() is effect:
            effect.set(min(1.0, t * 1.4), blur * (1 - t), mix(scale, 1.0, t), dx * (1 - t), dy * (1 - t))

    def settle():
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)
        if done:
            done()

    if delay:
        QTimer.singleShot(delay, lambda: tween(widget, 0, 1, duration, step, settle, name="arrive"))
    else:
        tween(widget, 0, 1, duration, step, settle, name="arrive")


def leave(widget, duration=200, blur=5.0, scale=1.0, dy=8.0, done=None):
    effect = MotionEffect(widget)
    widget.setGraphicsEffect(effect)

    def step(t):
        if widget.graphicsEffect() is effect:
            effect.set(1 - t, blur * t, mix(1.0, scale, t), 0, dy * t)

    def settle():
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)
        if done:
            done()

    return tween(widget, 0, 1, duration, step, settle, curve=QEasingCurve.Type.InCubic, name="arrive")


class SmoothWheel(QObject):
    """Turns wheel steps on a scroll area into a glide instead of a jump."""

    def __init__(self, area, horizontal=False):
        super().__init__(area)
        self.area = area
        self.bar = area.horizontalScrollBar() if horizontal else area.verticalScrollBar()
        self.target = None
        area.viewport().installEventFilter(self)

    # How far one notch of a mouse wheel scrolls, in pixels.
    NOTCH = 170

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            angle = event.angleDelta().y()
            pixels = event.pixelDelta().y()
            # A mouse wheel sends notches (120 each); on Wayland it also sends a small pixel figure
            # (about 15 per notch), which scrolled at a crawl. Pixels count only for a touchpad,
            # which scrolls in phases and sends no whole notches.
            touchpad = event.phase() != Qt.ScrollPhase.NoScrollPhase and pixels and abs(angle) < 120
            delta = pixels if touchpad else angle / 120 * self.NOTCH
            if not delta or self.bar.maximum() == 0:
                return False
            animating = running(self, "wheel")
            start = self.bar.value()
            base = self.target if (self.target is not None and animating) else start
            self.target = max(0, min(self.bar.maximum(), base - delta))
            tween(self, start, self.target, 120 if touchpad else 300, lambda v: self.bar.setValue(round(v)), self.settled, name="wheel")
            return True
        return False

    def settled(self):
        self.target = None


class Hover(QObject):
    """A 0..1 value that follows the pointer smoothly, for widgets that paint their own hover."""

    def __init__(self, widget, duration=180):
        super().__init__(widget)
        self.widget = widget
        self.value = 0.0
        self.duration = duration

    def to(self, target):
        def step(value):
            self.value = value
            self.widget.update()
        tween(self, self.value, target, self.duration * abs(target - self.value) + 1, step, name="hover")
