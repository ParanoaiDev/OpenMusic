"""Artwork. The library has no album covers yet, so every track and artist gets its own smooth
monochrome picture drawn from its name. Artists get the particle ring of the logo, which can also
be drawn live, so the ring of the top artist and of a hovered artist keeps orbiting."""
import hashlib
import math
import random
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QConicalGradient, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
    QRadialGradient,
)

from .theme import ASSETS

SCALE = 2


def _random(seed):
    return random.Random(int.from_bytes(hashlib.blake2b(seed.encode("utf-8"), digest_size=8).digest(), "big"))


def initial(name):
    return next((char.upper() for char in name if char.isalnum()), "♪")


@lru_cache(maxsize=8)
def logo_mark(size):
    """The M in its particle ring, cut out of the logo as a white mark on transparency."""
    source = QImage(str(ASSETS / "logo.png"))
    if source.isNull():
        return QPixmap()
    side = int(source.width() * 0.545)
    crop = source.copy(int(source.width() * 0.232), int(source.height() * 0.155), side, side)
    crop = crop.scaled(size * SCALE, size * SCALE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    mark = QImage(crop.size(), QImage.Format.Format_ARGB32_Premultiplied)
    mark.fill(QColor("#ffffff"))
    mark.setAlphaChannel(crop.convertToFormat(QImage.Format.Format_Grayscale8))
    result = QPixmap.fromImage(mark)
    result.setDevicePixelRatio(SCALE)
    return result


class Ring:
    """A tilted band of particles around a centre, like the ring of the logo.

    The particles are drawn once onto a flat circle; each frame only turns that picture and lays it
    down tilted and squashed, so the particles orbit along an ellipse for the price of two pixmaps."""

    def __init__(self, seed, count=1100):
        rng = _random("ring\n" + seed)
        self.tilt = math.degrees(rng.uniform(-0.75, 0.75))
        self.squash = rng.uniform(0.58, 0.86)
        self.phase = rng.random() * 360
        self.speed = rng.uniform(9, 14) * rng.choice((-1, 1))
        self.seed = seed
        self.count = count
        self.sprites = {}

    def sprite(self, pixels):
        """The flat band at a given size in device pixels: particles and the smooth bright edge."""
        if pixels in self.sprites:
            return self.sprites[pixels]
        rng = _random("ring-sprite\n" + self.seed)
        band = QPixmap(pixels, pixels)
        band.fill(Qt.GlobalColor.transparent)
        edge = QPixmap(pixels, pixels)
        edge.fill(Qt.GlobalColor.transparent)
        half = pixels / 2
        radius = pixels * 0.33
        with QPainter(band) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            for _ in range(self.count):
                t = rng.random() * math.tau
                lit = 0.5 + 0.5 * math.sin(t)
                r = radius + rng.gauss(0, 1) * pixels * 0.028 * (0.35 + 0.65 * lit)
                size = pixels * rng.uniform(0.0016, 0.0042) * (0.7 + 0.5 * lit)
                painter.setBrush(QColor(255, 255, 255, int(40 + 200 * lit * rng.random())))
                painter.drawEllipse(QPointF(half + math.cos(t) * r, half + math.sin(t) * r), size, size)
            for _ in range(self.count // 6):
                t = rng.random() * math.tau
                r = radius * rng.uniform(1.12, 1.6)
                painter.setBrush(QColor(255, 255, 255, rng.randrange(25, 110)))
                painter.drawEllipse(QPointF(half + math.cos(t) * r, half + math.sin(t) * r), pixels * 0.0016, pixels * 0.0016)
        with QPainter(edge) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for width, alpha in ((pixels * 0.04, 22), (pixels * 0.014, 60), (max(1.5, pixels * 0.0045), 220)):
                sweep = QConicalGradient(QPointF(half, half), 270)
                sweep.setColorAt(0, QColor(255, 255, 255, alpha))
                sweep.setColorAt(0.2, QColor(255, 255, 255, 0))
                sweep.setColorAt(0.8, QColor(255, 255, 255, 0))
                sweep.setColorAt(1, QColor(255, 255, 255, alpha))
                painter.setPen(QPen(sweep, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawEllipse(QPointF(half, half), radius, radius)
        self.sprites[pixels] = (band, edge)
        return band, edge

    def paint(self, painter, rect, time=0.0, letter="", glow=1.0):
        side = min(rect.width(), rect.height())
        centre = rect.center()
        ratio = painter.device().devicePixelRatioF() if painter.device() else 1.0
        # Particles stay crisp enough on a big ring at this size, and the sprite stays cheap to turn.
        pixels = max(32, min(640, int(side * ratio / 16) * 16))
        band, edge = self.sprite(pixels)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(painter.opacity() * min(1.0, glow))
        painter.drawPixmap(QRectF(centre.x() - side * 0.55, centre.y() - side * 0.55, side * 1.1, side * 1.1), soft_light(), QRectF(soft_light().rect()))
        painter.setOpacity(painter.opacity() / max(0.01, min(1.0, glow)))
        turn = time * self.speed
        target = QRectF(-side / 2, -side / 2, side, side)
        painter.translate(centre)
        painter.rotate(self.tilt)
        painter.scale(1, self.squash)
        painter.save()
        painter.rotate(self.phase + turn)
        painter.drawPixmap(target, band, QRectF(band.rect()))
        painter.restore()
        painter.rotate(self.phase * 0.5 + turn * 0.35)
        painter.drawPixmap(target, edge, QRectF(edge.rect()))
        painter.restore()
        if letter:
            painter.save()
            font = QFont("Inter Display")
            font.setPixelSize(max(8, int(side * 0.28)))
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 240))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, letter)
            painter.restore()


@lru_cache(maxsize=4)
def soft_light(alpha=26, pixels=256):
    """A round soft glow, drawn once and stretched wherever a light is needed."""
    image = QPixmap(pixels, pixels)
    image.fill(Qt.GlobalColor.transparent)
    with QPainter(image) as painter:
        light = QRadialGradient(QPointF(pixels / 2, pixels / 2), pixels / 2)
        light.setColorAt(0, QColor(255, 255, 255, alpha))
        light.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(image.rect(), light)
    return image


@lru_cache(maxsize=32)
def tinted_light(red, green, blue, alpha=255, pixels=640):
    """A round soft glow in a colour, drawn once and stretched where the mood of a cover shows."""
    image = QPixmap(pixels, pixels)
    image.fill(Qt.GlobalColor.transparent)
    with QPainter(image) as painter:
        light = QRadialGradient(QPointF(pixels / 2, pixels / 2), pixels / 2)
        light.setColorAt(0, QColor(red, green, blue, alpha))
        light.setColorAt(0.45, QColor(red, green, blue, alpha // 3))
        light.setColorAt(1, QColor(red, green, blue, 0))
        painter.fillRect(image.rect(), light)
    return image


@lru_cache(maxsize=4)
def soft_shadow(pixels=128):
    image = QPixmap(pixels, pixels)
    image.fill(Qt.GlobalColor.transparent)
    with QPainter(image) as painter:
        shade = QRadialGradient(QPointF(pixels / 2, pixels / 2), pixels / 2)
        shade.setColorAt(0, QColor(0, 0, 0, 160))
        shade.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(image.rect(), shade)
    return image


@lru_cache(maxsize=256)
def ring(seed):
    return Ring(seed)


def disc(painter, rect, seed):
    """The dark disc an artist ring sits on."""
    rng = _random("disc\n" + seed)
    tone = rng.randint(24, 36)
    fill = QRadialGradient(rect.center() + QPointF(-rect.width() * 0.18, -rect.height() * 0.22), rect.width() * 0.75)
    fill.setColorAt(0, QColor(tone + 12, tone + 12, tone + 12))
    fill.setColorAt(1, QColor(8, 8, 8))
    path = QPainterPath()
    path.addEllipse(rect)
    painter.fillPath(path, fill)


@lru_cache(maxsize=600)
def avatar(seed, size, letter=""):
    side = size * SCALE
    result = QPixmap(side, side)
    result.fill(Qt.GlobalColor.transparent)
    with QPainter(result) as painter:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(0, 0, side, side)
        disc(painter, area, seed)
        clip = QPainterPath()
        clip.addEllipse(area)
        painter.setClipPath(clip)
        ring(seed).paint(painter, area, 0.0, letter)
    result.setDevicePixelRatio(SCALE)
    return result


@lru_cache(maxsize=1500)
def cover(seed, size):
    rng = _random(seed)
    side = size * SCALE
    result = QPixmap(side, side)
    result.fill(Qt.GlobalColor.transparent)
    with QPainter(result) as painter:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, side, side), side * 0.07, side * 0.07)
        painter.setClipPath(clip)
        angle = rng.random() * math.tau
        half = side / 2
        base = QLinearGradient(half - math.cos(angle) * half, half - math.sin(angle) * half,
                               half + math.cos(angle) * half, half + math.sin(angle) * half)
        tone = rng.randint(30, 52)
        base.setColorAt(0, QColor(tone, tone, tone))
        base.setColorAt(1, QColor(9, 9, 9))
        painter.fillRect(QRectF(0, 0, side, side), base)
        (_glow, _waves, _grooves, _orbit)[rng.randrange(4)](painter, side, rng)
    result.setDevicePixelRatio(SCALE)
    return result


def _glow(painter, side, rng):
    for _ in range(rng.randint(2, 3)):
        point = QPointF(side * rng.uniform(0.15, 0.85), side * rng.uniform(0.15, 0.85))
        light = QRadialGradient(point, side * rng.uniform(0.3, 0.65))
        light.setColorAt(0, QColor(255, 255, 255, rng.randrange(120, 210)))
        light.setColorAt(0.3, QColor(255, 255, 255, 50))
        light.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, side, side), light)


def _waves(painter, side, rng):
    lines = rng.randint(6, 10)
    amplitude = side * rng.uniform(0.025, 0.06)
    frequency = rng.uniform(1.1, 2.2)
    phase = rng.random() * math.tau
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for line in range(lines):
        y0 = side * (0.2 + 0.6 * line / (lines - 1))
        path = QPainterPath(QPointF(-side * 0.05, y0))
        for step in range(1, 61):
            x = side * (step / 60 * 1.1 - 0.05)
            path.lineTo(x, y0 + amplitude * math.sin(frequency * math.tau * step / 60 + phase + line * 0.4))
        bright = 1 - abs(line - (lines - 1) / 2) / (lines / 2)
        painter.setPen(QPen(QColor(255, 255, 255, int(40 + 190 * bright)), side * 0.012, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)


def _grooves(painter, side, rng):
    centre = QPointF(side * rng.uniform(0.3, 0.8), side * rng.uniform(0.3, 0.8))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    step = side * rng.uniform(0.03, 0.045)
    radius = step * 2
    while radius < side * 1.3:
        painter.setPen(QPen(QColor(255, 255, 255, rng.randrange(14, 50)), side * 0.005))
        painter.drawEllipse(centre, radius, radius)
        radius += step
    sweep = QConicalGradient(centre, rng.uniform(0, 360))
    sweep.setColorAt(0, QColor(255, 255, 255, 120))
    sweep.setColorAt(0.25, QColor(255, 255, 255, 0))
    sweep.setColorAt(1, QColor(255, 255, 255, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(sweep)
    painter.drawEllipse(centre, side * 1.2, side * 1.2)


def _orbit(painter, side, rng):
    centre = QPointF(side * 0.5, side * 0.5)
    for index in range(3):
        radius = side * (0.16 + 0.12 * index)
        painter.setPen(QPen(QColor(255, 255, 255, 40 + 50 * index), side * 0.008))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(centre, radius, radius * rng.uniform(0.55, 1.0))
    light = QRadialGradient(centre, side * 0.12)
    light.setColorAt(0, QColor(255, 255, 255, 230))
    light.setColorAt(1, QColor(255, 255, 255, 0))
    painter.fillRect(QRectF(0, 0, side, side), light)
