import unittest
from types import SimpleNamespace

from generator import octilinear, osm, renderer
from knoxbuild.settings import Settings
from shapely.geometry import LineString, Point


class OctilinearRoadDefaults(unittest.TestCase):
    def test_straight_roads_are_default_but_can_be_disabled(self):
        self.assertEqual(Settings().straight_roads, 1)
        self.assertEqual(Settings.from_dict({}).straight_roads, 1)
        self.assertEqual(Settings.from_dict({"straight_roads": 0}).straight_roads, 0)
        self.assertIs(renderer.render.__defaults__[6], True)

    def test_curves_become_straight_runs_and_keep_shared_junctions(self):
        projection = SimpleNamespace(
            width=128,
            height=128,
            to_px=lambda lat, lon: (lon, lat),
            to_latlon=lambda x, y: (y, x),
        )
        main = osm.OSMFeature(
            1, "way", {"highway": "primary"},
            [(10, 10), (20, 18), (30, 25), (40, 34), (50, 45)])
        side = osm.OSMFeature(
            2, "way", {"highway": "residential"},
            [(20, 18), (25, 28), (30, 38)])

        count = octilinear.straighten_roads(
            [main, side], projection, osm.classify, renderer._is_polygon)

        self.assertEqual(count, 2)
        self.assertLess(Point(*side.geometry[0]).distance(LineString(main.geometry)), 1e-8)
        for feature in (main, side):
            pixels = [projection.to_px(*point) for point in feature.geometry]
            for (x0, y0), (x1, y1) in zip(pixels, pixels[1:]):
                dx, dy = round(x1 - x0), round(y1 - y0)
                self.assertTrue(dx == 0 or dy == 0 or abs(dx) == abs(dy))


if __name__ == "__main__":
    unittest.main()