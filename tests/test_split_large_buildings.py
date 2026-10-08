"""Buildings past settings.max_size are split, not dropped (knoxbuild.build).

Run from the KnoxMap folder:  python -m unittest discover tests
No network, no files: one polygon placed straight into an empty grid.

The gate in footprint.place refuses a building whose long side is over
max_size - measured on the real polygon, before anything is claimed. build.py
answers "large" by placing it again without that gate and passing max_side
down to row_units, so every unit comes out inside the cap the gate used to
enforce. The factory and the hangar are the landmarks a place is known by;
dropping them left a hole in the map.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from knoxbuild.build import row_units  # noqa: E402
from knoxbuild.footprint import place  # noqa: E402

# 500 x 80 tiles: well over the 200-tile gate on its long side.
RECT = [(10.0, 10.0), (510.0, 10.0), (510.0, 90.0), (10.0, 90.0), (10.0, 10.0)]
GRID = np.zeros((600, 600), dtype=bool)


def placed(max_side: float):
    return place(list(RECT), GRID.copy(), max_side=max_side)


class Gate(unittest.TestCase):
    def test_the_gate_still_refuses_on_the_real_side(self):
        fp, reason = placed(200)
        self.assertIsNone(fp)
        self.assertEqual(reason, "large")

    def test_the_retry_places_it_whole(self):
        # What build.py does when place answers "large": try again without
        # the one gate that fired. place claimed nothing before refusing.
        fp, reason = placed(1e9)
        self.assertIsNotNone(fp, reason)
        self.assertEqual((fp.width, fp.height), (500, 80))


class Split(unittest.TestCase):
    def test_cut_units_fit_inside_the_cap(self):
        fp, reason = placed(1e9)
        self.assertIsNotNone(fp, reason)
        # At a quarter-metre tiles the area rule (BIG_BUILDING_M2, 6000 m2
        # = 95481 tiles squared here) stops before 200, so without the cap
        # this footprint is passed through whole - only the cap splits it.
        # "industrial" is not a row kind, so this is the plain _cut_big path.
        units = row_units(fp, "industrial", "industrial", 0, 0.25,
                          max_side=200)
        self.assertGreater(len(units), 1)
        self.assertTrue(all(max(u.width, u.height) <= 200 for u in units),
                        [(u.width, u.height) for u in units])

    def test_the_cuts_keep_every_tile(self):
        fp, _ = placed(1e9)
        units = row_units(fp, "industrial", "industrial", 0, 0.25,
                          max_side=200)
        self.assertEqual(sum(u.tiles for u in units), fp.tiles)

    def test_without_the_cap_the_area_rule_is_unchanged(self):
        fp, _ = placed(1e9)
        units = row_units(fp, "industrial", "industrial", 0, 0.25)
        self.assertEqual([(u.width, u.height) for u in units], [(500, 80)])

    def test_a_building_that_already_fits_is_cut_exactly_as_before(self):
        small = [(10.0, 10.0), (160.0, 10.0), (160.0, 60.0),
                 (10.0, 60.0), (10.0, 10.0)]
        fp, reason = place(list(small), GRID.copy(), max_side=200)
        self.assertIsNotNone(fp, reason)
        plain = row_units(fp, "industrial", "industrial", 0, 1.0)
        capped = row_units(fp, "industrial", "industrial", 0, 1.0,
                           max_side=200)
        self.assertEqual(
            [(u.x0, u.y0, u.width, u.height, u.tiles) for u in plain],
            [(u.x0, u.y0, u.width, u.height, u.tiles) for u in capped])


if __name__ == "__main__":
    unittest.main()
