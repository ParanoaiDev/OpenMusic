import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from library import key, track_link
from . import covers
from .art import avatar, cover, disc, initial, logo_mark, ring, soft_light, soft_shadow, tinted_light
from .icons import icon
from .motion import SmoothWheel, arrive, mix, tween
from .theme import MUTED, TEXT
from .widgets import Clickable, Shelf, button, elided, icon_button, label, listening, measure, overline, plural


class Live:
    """A frame clock for things that keep moving. It ticks only while its widget is on screen and the
    window is active, and asks for a repaint of just the area that moves."""

    def __init__(self, widget, area=None, interval=40):
        self.widget = widget
        self.area = area
        self.clock = QElapsedTimer()
        self.clock.start()
        self.timer = QTimer(widget)
        self.timer.setInterval(interval)
        self.timer.timeout.connect(self.tick)

    def seconds(self):
        return self.clock.elapsed() / 1000

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def tick(self):
        window = self.widget.window()
        if self.widget.isVisible() and window.isActiveWindow() and not window.isMinimized():
            self.widget.update(self.area() if self.area else self.widget.rect())


class RevealText(QWidget):
    """Big text that appears left to right with a soft edge, the way lyric videos bring in a line."""

    def __init__(self, font_size=42, weight=QFont.Weight.Black):
        super().__init__()
        self.text = ""
        self.progress = 1.0
        self.text_font = QFont("Inter Display")
        self.text_font.setPointSizeF(font_size)
        self.text_font.setWeight(weight)
        self.setFixedHeight(QFontMetrics(self.text_font).height() + 6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def show_text(self, text, animate=True):
        self.text = text
        self.setToolTip(text)
        if animate:
            tween(self, 0, 1, 1100, self.set_progress, name="reveal")
        else:
            self.set_progress(1)

    def set_progress(self, value):
        self.progress = value
        self.update()

    def paintEvent(self, event):
        if not self.text:
            return
        metrics = QFontMetrics(self.text_font)
        shown = elided(metrics, self.text, self.width() - 4)
        width = metrics.horizontalAdvance(shown) + 8
        ratio = self.devicePixelRatioF()
        layer = QPixmap(int(width * ratio) + 2, int(self.height() * ratio) + 2)
        layer.setDevicePixelRatio(ratio)
        layer.fill(Qt.GlobalColor.transparent)
        with QPainter(layer) as painter:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setFont(self.text_font)
            painter.setPen(QColor(TEXT))
            painter.drawText(QRectF(0, 0, width, self.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, shown)
            if self.progress < 1:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                edge = mix(-0.35, 1.0, self.progress) * width
                mask = QLinearGradient(edge, 0, edge + width * 0.35, 0)
                mask.setColorAt(0, QColor(0, 0, 0, 255))
                mask.setColorAt(1, QColor(0, 0, 0, 0))
                painter.fillRect(QRectF(0, 0, width, self.height()), mask)
        painter = QPainter(self)
        painter.drawPixmap(QPointF(0, (1 - self.progress) ** 2 * 10), layer)


class Counter(QWidget):
    """A figure that counts up to its value."""

    def __init__(self):
        super().__init__()
        self.value = 0
        self.shown = 0.0
        self.suffix = ""
        self.caption = ""
        self.formatter = str
        self.big = QFont("Inter Display")
        self.big.setPointSizeF(24)
        self.big.setWeight(QFont.Weight.ExtraBold)
        self.small = QFont(self.font())
        self.small.setPointSizeF(9)
        self.setFixedSize(170, 56)

    def show_value(self, value, caption, formatter=str, delay=0):
        self.value, self.caption, self.formatter = value, caption, formatter
        self.shown = 0
        QTimer.singleShot(delay, lambda: tween(self, 0, value, 1100, self.set_shown, name="count"))

    def set_shown(self, value):
        self.shown = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.big)
        painter.setPen(QColor(TEXT))
        painter.drawText(QRectF(0, 0, self.width(), 34), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         self.formatter(round(self.shown)))
        painter.setFont(self.small)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(0, 34, self.width(), 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.caption)


class Hero(QFrame):
    """The top artist: the ring of the logo orbiting the initial, covers of their tracks floating
    around it, and a light that breathes slowly."""

    ART = QRect(26, 18, 250, 250)

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(286)
        self.artist = ""
        self.letter = ""
        self.floating = []
        self.queue = []
        self.live = Live(self, self.art_area)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(330, 30, 34, 30)
        layout.setSpacing(24)
        text = QVBoxLayout()
        text.setSpacing(6)
        text.addStretch()
        text.addWidget(overline("Чаще всего в медиатеке"))
        self.name = RevealText()
        text.addWidget(self.name)
        self.detail = label("", "muted")
        text.addWidget(self.detail)
        text.addSpacing(14)
        actions = QHBoxLayout()
        self.listen = button("Слушать", lambda: None, "primary", "play")
        actions.addWidget(self.listen)
        actions.addSpacing(6)
        self.tracks = button("Все треки", lambda: None, "ghost", "chevron")
        actions.addWidget(self.tracks)
        actions.addStretch()
        text.addLayout(actions)
        text.addStretch()
        layout.addLayout(text, 1)
        figures = QVBoxLayout()
        figures.setSpacing(6)
        figures.addStretch()
        self.counters = [Counter() for _ in range(3)]
        for counter in self.counters:
            figures.addWidget(counter, alignment=Qt.AlignmentFlag.AlignRight)
        figures.addStretch()
        layout.addLayout(figures)

    def art_area(self):
        return QRect(0, 0, 320, self.height())

    def show_artist(self, name, detail, covers, figures):
        self.artist, self.letter = name, initial(name)
        self.floating = list(covers[:3])
        self.name.show_text(name)
        self.detail.setText(detail)
        for index, (counter, (value, caption, formatter)) in enumerate(zip(self.counters, figures)):
            counter.show_value(value, caption, formatter, 120 * index)

    def showEvent(self, event):
        self.live.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.live.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        time = self.live.seconds()
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 28, 28)
        painter.fillPath(shape, QColor(255, 255, 255, 9))
        painter.setClipPath(shape)
        breath = 0.75 + 0.25 * math.sin(time * 0.9)
        painter.setOpacity(breath)
        glow = soft_light(34)
        painter.drawPixmap(QRectF(self.ART.center().x() - 420, self.ART.center().y() - 420, 840, 840), glow, QRectF(glow.rect()))
        if self.floating and covers.STORE:
            mood = covers.STORE.colour(self.floating[0])
            tint = tinted_light(mood.red(), mood.green(), mood.blue(), 120)
            painter.setOpacity(0.5 * breath)
            painter.drawPixmap(QRectF(self.ART.center().x() - 380, self.ART.center().y() - 300, 760, 600), tint, QRectF(tint.rect()))
        painter.setOpacity(1)
        if self.artist:
            orbit = []
            for index, track in enumerate(self.floating):
                pixmap = covers.STORE.pixmap(track, 58) if covers.STORE else cover(f"{track.artist}\n{track.title}", 58)
                angle = time * 0.22 + index * math.tau / 3
                centre = QPointF(self.ART.center()) + QPointF(math.cos(angle) * 128, math.sin(angle) * 58 + math.sin(time * 1.3 + index) * 6)
                orbit.append((0.5 + 0.5 * math.sin(angle), index, centre, pixmap))
            self.paint_orbit(painter, [item for item in orbit if item[0] < 0.5], time)
            photo = covers.STORE.artist_pixmap(self.artist, 150) if covers.STORE else None
            if photo is not None:
                # The artist's photo in the middle of the ring, where the initial stands without one.
                side = 150
                place = QRectF(self.ART.center().x() - side / 2, self.ART.center().y() - side / 2, side, side)
                painter.drawPixmap(place, photo, QRectF(photo.rect()))
                painter.setPen(QPen(QColor(255, 255, 255, 60), 1.2))
                painter.drawEllipse(place)
                ring(self.artist).paint(painter, QRectF(self.ART).adjusted(-14, -14, 14, 14), time, "", breath)
            else:
                ring(self.artist).paint(painter, QRectF(self.ART).adjusted(-14, -14, 14, 14), time, self.letter, breath)
            self.paint_orbit(painter, [item for item in orbit if item[0] >= 0.5], time)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
        painter.drawPath(shape)

    def paint_orbit(self, painter, items, time):
        for depth, index, centre, pixmap in items:
            painter.save()
            painter.translate(centre)
            painter.rotate(math.sin(time * 0.7 + index * 2) * 6)
            scale = 0.62 + 0.38 * depth
            painter.scale(scale, scale)
            painter.setOpacity(0.25 + 0.75 * depth)
            painter.drawPixmap(QRectF(-48, -36, 96, 96), soft_shadow(), QRectF(soft_shadow().rect()))
            painter.drawPixmap(QPointF(-29, -29), pixmap)
            edge = QPainterPath()
            edge.addRoundedRect(QRectF(-29, -29, 58, 58), 5, 5)
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
            painter.drawPath(edge)
            painter.restore()


class Tile(Clickable):
    """A shelf tile that paints itself, so it can rise in, lift on hover and glow under the pointer."""

    def __init__(self, width, height):
        super().__init__("tile")
        self.setFixedSize(width, height)
        self.reveal = 1.0
        self.title_font = QFont(self.font())
        self.title_font.setWeight(QFont.Weight.DemiBold)
        self.caption_font = QFont(self.font())
        self.caption_font.setPointSizeF(self.font().pointSizeF() * 0.9)

    def rise(self, delay):
        self.reveal = 0.0
        QTimer.singleShot(delay, lambda: tween(self, 0, 1, 520, self.set_reveal, name="rise"))

    def set_reveal(self, value):
        self.reveal = value
        self.update()

    def paint_art(self, painter, area, hover):
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(self.reveal)
        # Room above the art, so it can lift and grow on hover without being cut off.
        painter.translate(0, 8 + (1 - self.reveal) * 22)
        h = self.hover.value
        side = self.width()
        art = QRectF(0, 0, side, side)
        if h > 0.01:
            # The glow must fade to nothing before the tile's edge, or its square bounds show.
            painter.save()
            painter.setOpacity(self.reveal * h)
            glow = soft_light(60)
            reach = side / 2 - 1
            painter.drawPixmap(QRectF(art.center().x() - reach, art.center().y() - reach, reach * 2, reach * 2), glow, QRectF(glow.rect()))
            painter.restore()
        painter.save()
        grow = 1 + 0.045 * h
        painter.translate(art.center() + QPointF(0, -3 * h))
        painter.scale(grow, grow)
        painter.translate(-art.center())
        self.paint_art(painter, art.adjusted(4, 4, -4, -4), h)
        painter.restore()
        self.paint_text(painter, side + 10, h)


class ArtistTile(Tile):
    def __init__(self, name, metric):
        super().__init__(140, 200)
        self.name, self.caption_text = name, metric
        self.picture = avatar(name, 132, initial(name))
        self.live = Live(self)
        self.setAccessibleName(f"{name}, {metric}. Показать треки")

    def enterEvent(self, event):
        self.live.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        QTimer.singleShot(400, lambda: self.hover.value < 0.05 and self.live.stop())
        super().leaveEvent(event)

    def paint_art(self, painter, area, hover):
        photo = covers.STORE.artist_pixmap(self.name, 132) if covers.STORE else None
        if photo is not None:
            # The photo, with the ring of the logo turning around it under the pointer.
            painter.drawPixmap(area, photo, QRectF(photo.rect()))
            if hover > 0.01 and self.live.timer.isActive():
                painter.save()
                painter.setOpacity(painter.opacity() * hover)
                ring(self.name).paint(painter, area.adjusted(-10, -10, 10, 10), self.live.seconds(), "", 0.4)
                painter.restore()
            painter.setPen(QPen(QColor(255, 255, 255, int(30 + 60 * hover)), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(area)
        elif hover > 0.01 and self.live.timer.isActive():
            disc(painter, area, self.name)
            clip = QPainterPath()
            clip.addEllipse(area)
            painter.setClipPath(clip)
            ring(self.name).paint(painter, area, self.live.seconds(), initial(self.name), 1 + hover)
        else:
            painter.drawPixmap(area, self.picture, QRectF(self.picture.rect()))

    def paint_text(self, painter, top, hover):
        painter.setFont(self.title_font)
        painter.setPen(QColor(TEXT))
        painter.drawText(QRectF(0, top, self.width(), 22), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                         elided(QFontMetrics(self.title_font), self.name, self.width()))
        painter.setFont(self.caption_font)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(0, top + 22, self.width(), 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.caption_text)


class TrackTile(Tile):
    entered = Signal()

    def enterEvent(self, event):
        self.entered.emit()
        super().enterEvent(event)

    def __init__(self, track):
        super().__init__(160, 224)
        self.track = track
        self.setAccessibleName(f"{track.title}, {track.artist}. Слушать")

    def paint_art(self, painter, area, hover):
        if covers.STORE:
            covers.STORE.paint(painter, area, self.track, 152)
            if covers.STORE.fading(self.track) < 1:
                QTimer.singleShot(30, self.update)
        else:
            picture = cover(f"{self.track.artist}\n{self.track.title}", 152)
            painter.drawPixmap(area, picture, QRectF(picture.rect()))
        if hover > 0.01:
            painter.setOpacity(painter.opacity() * hover)
            centre = area.bottomRight() - QPointF(28, 28) + QPointF(0, (1 - hover) * 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#f4f4f4"))
            painter.drawEllipse(centre, 20, 20)
            painter.drawPixmap(centre - QPointF(9, 9), icon("play", "#0a0a0a").pixmap(QSize(18, 18)))

    def paint_text(self, painter, top, hover):
        painter.setFont(self.title_font)
        painter.setPen(QColor(TEXT))
        painter.drawText(QRectF(4, top, self.width() - 8, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         elided(QFontMetrics(self.title_font), self.track.title, self.width() - 8))
        painter.setFont(self.caption_font)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(4, top + 22, self.width() - 8, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         elided(QFontMetrics(self.caption_font), self.track.artist, self.width() - 8))


class StreamCard(Clickable):
    """"Мой поток": a wide card in the colour of a favourite cover, waves running across it while
    the pointer is on it, and a big play button. A click starts an endless radio from the taste."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(132)
        self.mood = QColor(150, 150, 150)
        self.covers = []
        self.live = Live(self)
        self.setAccessibleName("Мой поток")
        self.title_font = QFont("Inter Display")
        self.title_font.setPixelSize(30)
        self.title_font.setWeight(QFont.Weight.ExtraBold)
        self.small = QFont(self.font())

    def show_tracks(self, tracks):
        self.covers = tracks[:5]
        self.mood = covers.STORE.colour(tracks[0]) if covers.STORE and tracks else QColor(150, 150, 150)
        self.update()

    def enterEvent(self, event):
        self.live.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        QTimer.singleShot(400, lambda: self.hover.value < 0.05 and self.live.stop())
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.hover.value
        time = self.live.seconds()
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 24, 24)
        fill = QLinearGradient(0, 0, self.width(), 0)
        tone = QColor(self.mood)
        tone.setAlpha(int(110 + 50 * h))
        fill.setColorAt(0, tone)
        fill.setColorAt(0.65, QColor(20, 20, 22, 235))
        fill.setColorAt(1, QColor(12, 12, 14, 245))
        painter.fillPath(shape, fill)
        painter.setClipPath(shape)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for line in range(7):
            path = QPainterPath()
            base = self.height() * (0.25 + line * 0.09)
            for step in range(0, 81):
                x = self.width() * step / 80
                y = base + 10 * math.sin(step / 80 * math.tau * 1.6 + time * (0.8 + line * 0.15) + line) * (0.4 + 0.6 * h)
                path.moveTo(x, y) if step == 0 else path.lineTo(x, y)
            painter.setPen(QPen(QColor(255, 255, 255, int(16 + 26 * h)), 1.4))
            painter.drawPath(path)
        x = self.width() - 250 - 70
        for index, track in enumerate(self.covers):
            picture = covers.STORE.pixmap(track, 72) if covers.STORE else cover(f"{track.artist}\n{track.title}", 72)
            spot = QRectF(x + index * 42, self.height() / 2 - 36 + math.sin(time * 1.2 + index) * 4 * h, 72, 72)
            painter.setOpacity(0.55 + 0.45 * (index / max(1, len(self.covers) - 1)))
            painter.drawPixmap(spot, picture, QRectF(picture.rect()))
        painter.setOpacity(1)
        painter.setClipping(False)
        painter.setPen(QColor(TEXT))
        painter.setFont(self.title_font)
        painter.drawText(QRectF(34, 26, 600, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Мой поток")
        painter.setFont(self.small)
        painter.setPen(QColor(255, 255, 255, 170))
        painter.drawText(QRectF(34, 70, self.width() - 460, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                         "Бесконечная музыка по вашему вкусу: любимые треки и похожие на них с SoundCloud")
        centre = QPointF(self.width() - 66, self.height() / 2)
        radius = 28 * (1 + 0.08 * h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f4f4f4"))
        painter.drawEllipse(centre, radius, radius)
        glyph = icon("radio" if not h else "play", "#0a0a0a").pixmap(QSize(24, 24))
        painter.drawPixmap(QRectF(centre.x() - 12, centre.y() - 12, 24, 24), glyph, QRectF(glyph.rect()))
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(shape)


class MixTile(Tile):
    """A mix: four covers in a square, its number, the artists it is made of."""

    def __init__(self, number, tracks, artists):
        super().__init__(160, 224)
        self.number = number
        self.tracks = tracks
        self.artists = artists
        self.setAccessibleName(f"Микс {number}: {artists}")

    def paint_art(self, painter, area, hover):
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(area, area.width() * 0.07, area.width() * 0.07)
        painter.setClipPath(clip)
        half = area.width() / 2
        for index, track in enumerate(self.tracks[:4]):
            spot = QRectF(area.left() + (index % 2) * half, area.top() + (index // 2) * half, half, half)
            if covers.STORE:
                picture = covers.STORE.pixmap(track, 80)
            else:
                picture = cover(f"{track.artist}\n{track.title}", 80)
            painter.drawPixmap(spot, picture, QRectF(picture.rect()))
        shade = QLinearGradient(0, area.top(), 0, area.bottom())
        shade.setColorAt(0.45, QColor(0, 0, 0, 0))
        shade.setColorAt(1, QColor(0, 0, 0, 190))
        painter.fillRect(area, shade)
        big = QFont("Inter Display")
        big.setPixelSize(26)
        big.setWeight(QFont.Weight.Black)
        painter.setFont(big)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(area.adjusted(12, 0, -12, -10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, f"Микс {self.number}")
        painter.restore()
        if hover > 0.01:
            painter.setOpacity(painter.opacity() * hover)
            centre = area.bottomRight() - QPointF(28, 28) + QPointF(0, (1 - hover) * 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#f4f4f4"))
            painter.drawEllipse(centre, 20, 20)
            painter.drawPixmap(centre - QPointF(9, 9), icon("play", "#0a0a0a").pixmap(QSize(18, 18)))

    def paint_text(self, painter, top, hover):
        painter.setFont(self.title_font)
        painter.setPen(QColor(TEXT))
        painter.drawText(QRectF(4, top, self.width() - 8, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         plural(len(self.tracks), ("трек", "трека", "треков")))
        painter.setFont(self.caption_font)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(4, top + 22, self.width() - 8, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         elided(QFontMetrics(self.caption_font), self.artists, self.width() - 8))


def greeting():
    import datetime
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return "Доброе утро"
    if 12 <= hour < 17:
        return "Добрый день"
    if 17 <= hour < 23:
        return "Добрый вечер"
    return "Доброй ночи"


def mixes(tracks, artists, count=4):
    """Mixes made of the favourite artists: each gets every count-th artist of the ranking, their
    tracks shuffled together. [(number, tracks, artist names)]"""
    import random
    ranked = [name for name, _, _ in artists]
    result = []
    for number in range(count):
        names = ranked[number::count][:4]
        wanted = {key(name) for name in names}
        chosen = [track for track in tracks if key(track.artist) in wanted]
        if len(chosen) < 4:
            continue
        random.Random(number * 7 + len(tracks)).shuffle(chosen)
        result.append((number + 1, chosen, ", ".join(names[:2]) + (" и др." if len(names) > 2 else "")))
    return result


class EmptyMark(QWidget):
    """The logo on the empty screen, breathing."""

    def __init__(self):
        super().__init__()
        self.mark = logo_mark(176)
        self.setFixedSize(260, 230)
        self.live = Live(self)

    def showEvent(self, event):
        self.live.start()

    def hideEvent(self, event):
        self.live.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        time = self.live.seconds()
        breath = 0.5 + 0.5 * math.sin(time * 1.1)
        centre = QPointF(self.width() / 2, self.height() / 2)
        light = QRadialGradient(centre, 130)
        light.setColorAt(0, QColor(255, 255, 255, int(18 + 22 * breath)))
        light.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), light)
        painter.translate(centre + QPointF(0, math.sin(time * 0.8) * 4))
        scale = 1 + 0.015 * breath
        painter.scale(scale, scale)
        size = self.mark.deviceIndependentSize()
        painter.drawPixmap(QPointF(-size.width() / 2, -size.height() / 2), self.mark)


class HomePage(QScrollArea):
    import_requested = Signal()
    artist_chosen = Signal(str)
    play_requested = Signal(object, int)
    open_requested = Signal(object)
    hovered = Signal(object)
    radio_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.states = QStackedWidget()
        self.states.setObjectName("pageBody")
        self.setWidget(self.states)
        self.viewport().setAutoFillBackground(False)
        SmoothWheel(self)

        empty = QWidget()
        column = QVBoxLayout(empty)
        column.setContentsMargins(40, 40, 40, 60)
        column.setSpacing(10)
        column.addStretch()
        self.empty_mark = EmptyMark()
        column.addWidget(self.empty_mark, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.empty_title = label("Соберите свой вкус", "emptyTitle")
        column.addWidget(self.empty_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.empty_hint = label("Добавьте плейлист Spotify, лайки SoundCloud или CSV —\nздесь появятся ваши любимые артисты.", "muted")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        column.addWidget(self.empty_hint, alignment=Qt.AlignmentFlag.AlignHCenter)
        column.addSpacing(16)
        self.empty_button = button("Добавить музыку", self.import_requested.emit, "primary", "plus")
        column.addWidget(self.empty_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        column.addStretch()
        self.states.addWidget(empty)

        body = QWidget()
        self.content = QVBoxLayout(body)
        self.content.setContentsMargins(40, 30, 40, 36)
        self.content.setSpacing(0)
        top = QHBoxLayout()
        self.title = label(greeting(), "pageTitle")
        top.addWidget(self.title)
        top.addStretch()
        self.basis = label("", "muted")
        top.addWidget(self.basis, alignment=Qt.AlignmentFlag.AlignBottom)
        self.content.addLayout(top)
        self.content.addSpacing(20)
        self.hero = Hero(body)
        self.hero.tracks.clicked.connect(lambda: self.artist_chosen.emit(self.hero.artist))
        self.hero.listen.clicked.connect(lambda: self.hero.queue and self.play_requested.emit(self.hero.queue, 0))
        self.content.addWidget(self.hero)
        self.content.addSpacing(18)
        self.stream = StreamCard()
        self.stream.clicked.connect(self.radio_requested.emit)
        self.content.addWidget(self.stream)
        self.content.addSpacing(30)
        self.recent_head, self.recent = self.section("Недавно играли", 228)
        self.recent_gap = QWidget()
        self.recent_gap.setFixedHeight(26)
        self.content.addWidget(self.recent_gap)
        self.artists_head, self.artists = self.section("Любимые артисты", 204)
        self.content.addSpacing(26)
        self.mixes_head, self.mixes = self.section("Ваши миксы", 228)
        self.content.addSpacing(26)
        self.tracks_head, self.tracks = self.section("Треки", 228)
        self.content.addStretch()
        self.states.addWidget(body)

    def section(self, title, height):
        head = QWidget()
        row = QHBoxLayout(head)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(label(title, "sectionTitle"))
        row.addStretch()
        shelf = Shelf(height)
        row.addWidget(icon_button("back", lambda: shelf.page(-1), "Назад"))
        row.addWidget(icon_button("chevron", lambda: shelf.page(1), "Дальше"))
        self.content.addWidget(head)
        self.content.addSpacing(12)
        self.content.addWidget(shelf)
        return head, shelf

    def tile_menu(self, widget, point, track):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction(icon("play", "#d8d8d8"), "Слушать", lambda: self.play_requested.emit([track], 0))
        action = menu.addAction(icon("external", "#d8d8d8"), f"Открыть в {track.source}", lambda: self.open_requested.emit(track))
        action.setEnabled(bool(track_link(track)))
        menu.exec(widget.mapToGlobal(point))

    def update_covers(self):
        for shelf in (self.tracks, self.artists, self.recent, self.mixes):
            for tile in shelf.findChildren(Tile):
                tile.update()
        self.hero.update()
        self.stream.update()

    def show_state(self, index):
        # Only the shown state may size the page, or the empty screen scrolls by the height of the full one.
        for page in range(self.states.count()):
            policy = QSizePolicy.Policy.Preferred if page == index else QSizePolicy.Policy.Ignored
            self.states.widget(page).setSizePolicy(policy, policy)
        self.states.setCurrentIndex(index)
        self.states.adjustSize()

    def show_recent(self, recent):
        for widget in (self.recent_head, self.recent, self.recent_gap):
            widget.setVisible(bool(recent))
        tiles = []
        for index, track in enumerate(recent[:20]):
            item = TrackTile(track)
            item.clicked.connect(lambda number=index, shelf=recent[:20]: self.play_requested.emit(shelf, number))
            item.entered.connect(lambda chosen=track: self.hovered.emit(chosen))
            tiles.append(item)
        self.recent.fill(tiles)
        for index, item in enumerate(tiles):
            item.rise(200 + 50 * min(index, 9))

    def show_library(self, tracks, artists):
        if not tracks:
            self.show_state(0)
            for delay, widget in enumerate((self.empty_mark, self.empty_title, self.empty_hint, self.empty_button)):
                arrive(widget, 620, blur=8, dy=18, delay=90 * delay)
            return
        self.show_state(1)
        has_history = any(duration for _, duration, _ in artists)
        sources = sorted({track.source for track in tracks})
        self.basis.setText(f"{'По времени прослушивания' if has_history else 'По числу треков'} · {', '.join(sources)}")
        total = sum(track.milliseconds for track in tracks)
        figures = [(len(tracks), plural(len(tracks), ("трек", "трека", "треков")).split(" ", 1)[1], str),
                   (len(artists), plural(len(artists), ("артист", "артиста", "артистов")).split(" ", 1)[1], str)]
        if total:
            figures.append((total // 60000, "прослушано", lambda minutes: listening(minutes * 60000)))
        else:
            figures.append((len(sources), plural(len(sources), ("источник", "источника", "источников")).split(" ", 1)[1], str))
        name, duration, count = artists[0]
        mine = [track for track in tracks if key(track.artist) == key(name)]
        self.hero.queue = mine
        self.hero.show_artist(name, measure(duration, count) + (" прослушивания" if duration else " в медиатеке"), mine, figures)
        arrive(self.hero, 700, blur=10, scale=0.985, dy=20)
        rest = artists[1:21]
        self.artists_head.setVisible(bool(rest))
        self.artists.setVisible(bool(rest))
        tiles = []
        for name, duration, count in rest:
            artist = ArtistTile(name, measure(duration, count))
            artist.clicked.connect(lambda chosen=name: self.artist_chosen.emit(chosen))
            tiles.append(artist)
        self.artists.fill(tiles)
        for index, item in enumerate(tiles):
            item.rise(260 + 55 * min(index, 9))
        tiles = []
        shelf = tracks[:20]
        for index, track in enumerate(shelf):
            item = TrackTile(track)
            item.clicked.connect(lambda number=index: self.play_requested.emit(shelf, number))
            item.entered.connect(lambda chosen=track: self.hovered.emit(chosen))
            item.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            item.customContextMenuRequested.connect(lambda point, chosen=track, widget=item: self.tile_menu(widget, point, chosen))
            tiles.append(item)
        self.tracks.fill(tiles)
        for index, item in enumerate(tiles):
            item.rise(420 + 55 * min(index, 9))
        self.stream.show_tracks(tracks[:5])
        made = mixes(tracks, artists)
        self.mixes_head.setVisible(bool(made))
        self.mixes.setVisible(bool(made))
        tiles = []
        for number, chosen, names in made:
            item = MixTile(number, chosen, names)
            item.clicked.connect(lambda chosen=chosen: self.play_requested.emit(chosen, 0))
            tiles.append(item)
        self.mixes.fill(tiles)
        for index, item in enumerate(tiles):
            item.rise(380 + 60 * index)
