import os
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np
from PIL import Image
from shapely.geometry import Point, Polygon

from generator import osm, pz_colors as C, renderer
from knoxbuild.props import _blocked_mask, place_props


class OutdoorProps(unittest.TestCase):
    def test_park_polygons_are_exported_for_outdoor_furnishing(self):
        park = osm.OSMFeature(
            1, "way", {"leisure": "park", "name": "Town Green"},
            [(5, 5), (5, 25), (25, 25), (25, 5), (5, 5)])

        exported = renderer._areas_geojson({"park": [park]})

        self.assertEqual(len(exported["features"]), 1)
        self.assertEqual(exported["features"][0]["properties"]["category"], "park")

    def test_road_and_sidewalk_colors_are_blocked_for_props(self):
        colors = (C.DARK_ASPHALT, C.MEDIUM_ASPHALT, C.LIGHT_ASPHALT,
                  C.DARKEST_ASPHALT, C.PALE_CONCRETE, C.DARK_POTHOLE,
                  C.LIGHT_POTHOLE, C.DARK_GRASS)
        ground = np.array([[color for color in colors]], dtype=np.uint8)

        blocked = _blocked_mask(ground)

        np.testing.assert_array_equal(blocked[0],
                                      [True] * (len(colors) - 1) + [False])

    def test_picnic_tables_stay_inside_parks_and_off_buildings_and_roads(self):
        with TemporaryDirectory() as directory:
            bdir = os.path.join(directory, "buildings")
            os.mkdir(bdir)
            ground = Image.new("RGB", (200, 200), C.MEDIUM_GRASS)
            pixels = ground.load()
            for y in range(200):
                pixels[100, y] = C.MEDIUM_ASPHALT
            ground.save(os.path.join(directory, "park.bmp"))
            Image.new("RGB", ground.size, C.TREES).save(
                os.path.join(directory, "park_veg.bmp"))
            occupied = np.zeros((200, 200), dtype=bool)
            occupied[90:98, 90:98] = True
            before = occupied.copy()
            park = Polygon([(2, 2), (198, 2), (198, 198), (2, 198)])
            areas = SimpleNamespace(_items=[(park, {"category": "park"})])

            placements, counts = place_props(
                directory, "park", bdir, occupied, areas, metres_per_tile=1.0,
                seed=42)

            self.assertGreater(counts["picnic_tables"], 0)
            self.assertTrue(placements)
            added = occupied & ~before
            self.assertEqual(int(added.sum()), counts["picnic_tables"] * 4)
            self.assertFalse(added[:, 100].any())
            self.assertFalse(added[90:98, 90:98].any())
            for y, x in zip(*np.nonzero(added)):
                self.assertTrue(park.contains(Point(x + 0.5, y + 0.5)))


if __name__ == "__main__":
    unittest.main()