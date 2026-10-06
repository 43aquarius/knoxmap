import unittest
from xml.etree import ElementTree

from knoxbuild import catalog
from knoxbuild import layout
from knoxbuild.tbx import render_tbx


class WindowWallStyles(unittest.TestCase):
    REQUIRED = {f"{side}Window{index}"
                for side in ("West", "North")
                for index in range(1, 20)}

    def test_every_interior_style_has_all_window_cutouts(self):
        for entry in catalog.INTERIOR_WALLS:
            with self.subTest(wall=entry["tiles"].get("West")):
                self.assertTrue(self.REQUIRED <= entry["tiles"].keys())

    def test_export_completes_special_style_wall_cutouts(self):
        room = layout.Room(0, 0, 3, 3, kind="hall")
        plan = layout.Plan(4, 4, rooms=[room], grid=[[1] * 4 for _ in range(4)],
                           windows=[(1, 0, "N")])
        style = catalog.SPECIAL_STYLES["school"]

        root = ElementTree.fromstring(render_tbx(plan, "window-style-test", style))

        entries = [entry for entry in root.findall("tile_entry")
                   if entry.get("category") in ("exterior_walls", "interior_walls")]
        self.assertTrue(entries)
        for entry in entries:
            tile_names = {tile.get("enum") for tile in entry.findall("tile")}
            with self.subTest(category=entry.get("category")):
                self.assertTrue(self.REQUIRED <= tile_names)


if __name__ == "__main__":
    unittest.main()
