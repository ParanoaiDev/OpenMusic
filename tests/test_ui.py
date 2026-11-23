"""The pieces of the interface that work without a window: lists changed in place and pictures
made to exact pixels."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QImage

from ui.models import Items
from ui.pictures import Pictures, square


class Watched:
    """A list and a record of what it told the screen."""

    def __init__(self, entries):
        self.model = Items()
        self.model.replace(entries)
        self.said = []
        self.model.modelReset.connect(lambda: self.said.append("reset"))
        self.model.rowsInserted.connect(lambda parent, first, last: self.said.append(("added", first, last)))
        self.model.rowsRemoved.connect(lambda parent, first, last: self.said.append(("removed", first, last)))
        self.model.dataChanged.connect(lambda first, last, roles: self.said.append(("changed", first.row(), last.row())))
        self.model.countChanged.connect(lambda: self.said.append("count"))

    def shown(self):
        model = self.model
        return [model.data(model.index(row), Items.ROLE) for row in range(model.rowCount())]


class ItemsInPlace(unittest.TestCase):
    def test_the_same_list_says_nothing(self):
        watched = Watched([{"title": "a"}, {"title": "b"}])
        watched.model.replace([{"title": "a"}, {"title": "b"}])
        self.assertEqual(watched.said, [])

    def test_one_changed_row(self):
        watched = Watched([{"cover": "drawn"}, {"cover": "x"}, {"cover": "y"}])
        watched.model.replace([{"cover": "drawn"}, {"cover": "real"}, {"cover": "y"}])
        self.assertEqual(watched.said, [("changed", 1, 1)])
        self.assertEqual(watched.shown()[1], {"cover": "real"})

    def test_longer(self):
        watched = Watched(["a", "b"])
        watched.model.replace(["a", "c", "d", "e"])
        self.assertEqual(watched.said, [("added", 2, 3), ("changed", 1, 1), "count"])
        self.assertEqual(watched.shown(), ["a", "c", "d", "e"])
        self.assertEqual(watched.model.count, 4)

    def test_shorter(self):
        watched = Watched(["a", "b", "c"])
        watched.model.replace(["b"])
        self.assertEqual(watched.said, [("removed", 1, 2), ("changed", 0, 0), "count"])
        self.assertEqual(watched.shown(), ["b"])

    def test_emptied_and_filled(self):
        watched = Watched(["a"])
        watched.model.replace([])
        watched.model.replace(["z"])
        self.assertEqual(watched.said, [("removed", 0, 0), "count", ("added", 0, 0), "count"])
        self.assertNotIn("reset", watched.said)


def picture(width, height):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#ff0000"))
    for x in range(width):
        for y in range(height):
            if x < width // 4 or x >= width - width // 4:
                image.setPixelColor(x, y, QColor("#0000ff"))
    return image


class Square(unittest.TestCase):
    def test_wide_picture_is_cut_to_its_middle(self):
        cut = square(picture(400, 200), 100)
        self.assertEqual((cut.width(), cut.height()), (100, 100))
        # The blue sides of the wide picture are outside the middle square.
        self.assertEqual(cut.pixelColor(2, 50).name(), "#ff0000")
        self.assertEqual(cut.pixelColor(97, 50).name(), "#ff0000")

    def test_circle(self):
        cut = square(picture(200, 200), 100, 50)
        self.assertEqual(cut.pixelColor(0, 0).alpha(), 0)
        self.assertEqual(cut.pixelColor(99, 99).alpha(), 0)
        self.assertEqual(cut.pixelColor(50, 50).alpha(), 255)
        self.assertEqual(cut.pixelColor(50, 1).alpha(), 255)

    def test_chosen_corners(self):
        cut = square(picture(200, 200), 100, 20, "1000")
        self.assertEqual(cut.pixelColor(0, 0).alpha(), 0)
        for corner in ((99, 0), (99, 99), (0, 99)):
            self.assertEqual(cut.pixelColor(*corner).alpha(), 255)

    def test_the_edge_of_a_round_corner_is_soft(self):
        cut = square(picture(200, 200), 100, 50)
        alphas = {cut.pixelColor(x, 14).alpha() for x in range(0, 30)}
        self.assertTrue(any(0 < alpha < 255 for alpha in alphas))


class Provider(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "папка с пробелом" / "обложка #1.png"
        self.path.parent.mkdir()
        picture(300, 300).save(str(self.path))

    def ask(self, name, side):
        size = QSize()
        return Pictures().requestImage(name, size, QSize(side, side)), size

    def test_by_the_address_qml_sends(self):
        # Qt hands the provider the address with spaces and letters decoded and "#" still encoded.
        address = QUrl.fromLocalFile(str(self.path)).toString()
        image, size = self.ask("60-1111/" + address, 120)
        self.assertEqual((image.width(), image.height()), (120, 120))
        self.assertEqual((size.width(), size.height()), (120, 120))
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)

    def test_full_size_when_none_is_asked(self):
        image, _ = self.ask("0-1111/" + QUrl.fromLocalFile(str(self.path)).toString(), 0)
        self.assertEqual(image.width(), 300)

    def test_missing_file_and_bad_shape(self):
        self.assertTrue(self.ask("60-1111/file:///nowhere/at/all.png", 100)[0].isNull())
        self.assertTrue(self.ask("round/" + QUrl.fromLocalFile(str(self.path)).toString(), 100)[0].isNull())


if __name__ == "__main__":
    unittest.main()
