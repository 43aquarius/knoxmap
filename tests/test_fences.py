import os
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from xml.etree import ElementTree

import numpy as np

from knoxbuild.fences import build_fences


class FenceCollisionTests(unittest.TestCase):
    def test_mapped_fence_is_cut_around_building_footprint(self):
        with TemporaryDirectory() as directory:
            bdir = os.path.join(directory, "buildings")
            os.mkdir(bdir)
            occupied = np.zeros((16, 16), dtype=bool)
            occupied[5:8, 5:7] = True
            projection = SimpleNamespace(width=16, height=16,
                                         to_px=lambda lat, lon: (lon, lat))

            placements, count = build_fences(
                directory, "map", projection, occupied, None, bdir,
                extra=[([(2, 6), (10, 6)], "short_wooden", [])])

            self.assertTrue(placements)
            placed = set()
            for placement in placements:
                root = ElementTree.parse(os.path.join(directory, placement.tbx_path))
                for obj in root.findall(".//floor/object"):
                    x = placement.tile_x + int(obj.get("x"))
                    y = placement.tile_y + int(obj.get("y"))
                    placed.add((x, y))
            self.assertEqual(len(placed), count)
            self.assertFalse(any(occupied[y, x] for x, y in placed))


if __name__ == "__main__":
    unittest.main()