"""Per-district street grid rotation (renderer.dominant_road_angle).

Run from the KnoxMap folder:  python -m unittest discover tests
No network: the streets are synthesised here.

The two-district case is the measured failure this feature fixes: a town that
grew in two phases (one grid over here, another over there) used to be turned
by the *average* of the two - an angle that straightens neither district, so
both kept their staircases. Now the district holding the most street picks the
turn; the losing grid keeps its offset and "Knox County roads" bends it.
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import renderer  # noqa: E402
from generator.osm import OSMFeature  # noqa: E402

# A town near 40N, about 600 m square - the box tools/selftest.py draws.
SOUTH, WEST = 40.0000, 20.0000
NORTH, EAST = 40.0054, 20.0070
CX = CY = 300.0                      # town centre, metres from the SW corner
_ids = iter(range(1, 10 ** 6))


def ll(x_m: float, y_m: float, deg: float = 0.0) -> tuple[float, float]:
    """Metres east/north of the SW corner, turned by deg about the town
    centre, to (lat, lon)."""
    a = math.radians(deg)
    dx, dy = x_m - CX, y_m - CY
    rx = CX + dx * math.cos(a) - dy * math.sin(a)
    ry = CY + dx * math.sin(a) + dy * math.cos(a)
    return (SOUTH + ry / 111320.0,
            WEST + rx / (111320.0 * math.cos(math.radians(SOUTH))))


def seg(x0: float, y0: float, x1: float, y1: float, deg: float = 0.0) -> OSMFeature:
    """One street: ends in metres, optionally turned by deg about the centre."""
    return OSMFeature(next(_ids), "way", {"highway": "residential"},
                      [ll(x0, y0, deg), ll(x1, y1, deg)])


def grid(deg: float, spacing: int = 80, half: int = 280) -> list[OSMFeature]:
    """A whole town on one grid at `deg`, streets every `spacing` metres."""
    a = math.radians(deg)
    ax, ay = math.cos(a), math.sin(a)        # along a street
    px, py = -math.sin(a), math.cos(a)       # across the streets
    out = []
    for k in range(-half, half + 1, spacing):
        # Street running along the grid at cross-offset k...
        out.append(seg(CX + k * px - half * ax, CY + k * py - half * ay,
                       CX + k * px + half * ax, CY + k * py + half * ay))
        # ...and the cross street at along-offset k.
        out.append(seg(CX - half * px + k * ax, CY - half * py + k * ay,
                       CX + half * px + k * ax, CY + half * py + k * ay))
    return out


def district_a() -> list[OSMFeature]:
    """The west half of town: an axis-aligned grid (0 degrees), the larger
    phase - 2880 m of east-west streets plus 2080 m of north-south."""
    out = []
    y = 60
    while y <= 540:
        out.append(seg(40, y, 360, y))
        y += 60
    # North-south streets stop well left of x=250: the projector fits the
    # 600 m box into a wider tile canvas with a margin, so metre x is not
    # tile x - streets near the district edge measured across into the
    # east cells and their mixed votes muddied both districts.
    x = 50
    while x <= 230:
        out.append(seg(x, 40, x, 560))
        x += 60
    return out


def district_b() -> list[OSMFeature]:
    """The east half: a 30-degree grid, the smaller phase (2400 m)."""
    a = math.radians(30)
    ax, ay = math.cos(a), math.sin(a)
    px, py = -math.sin(a), math.cos(a)
    cx, cy = 500.0, 300.0
    out = []
    for u in (-80, -40, 0, 40, 80):          # streets running at 30 degrees
        out.append(seg(cx + u * px - 160 * ax, cy + u * py - 160 * ay,
                       cx + u * px + 160 * ax, cy + u * py + 160 * ay))
    for v in (-160, -80, 0, 80, 160):        # the cross streets at 120
        out.append(seg(cx - 80 * px + v * ax, cy - 80 * py + v * ay,
                       cx + 80 * px + v * ax, cy + 80 * py + v * ay))
    return out


class Uniform(unittest.TestCase):
    def test_finds_the_single_grid(self):
        angle, strength = renderer.dominant_road_angle(
            grid(30), SOUTH, WEST, NORTH, EAST)
        self.assertLess(abs(abs(angle) - 30), 2)
        self.assertGreater(strength, 0.8)

    def test_flat_grid_reads_zero(self):
        angle, strength = renderer.dominant_road_angle(
            grid(0), SOUTH, WEST, NORTH, EAST)
        self.assertLess(abs(angle), 1)
        self.assertGreater(strength, 0.8)


class TwoDistricts(unittest.TestCase):
    def test_dominant_district_wins_not_the_average(self):
        # Averaging the two phases lands near -6.5 degrees - straightens
        # neither grid. The larger district's own angle must win instead.
        angle, strength = renderer.dominant_road_angle(
            district_a() + district_b(), SOUTH, WEST, NORTH, EAST)
        self.assertLess(abs(angle), 2, f"snapped to the dominant grid, got {angle:.2f}")
        self.assertGreater(strength, 0.6)

    def test_smaller_phase_alone_still_found(self):
        # The losing district is measured correctly when it is all there is.
        angle, strength = renderer.dominant_road_angle(
            district_b(), SOUTH, WEST, NORTH, EAST)
        self.assertLess(abs(abs(angle) - 30), 2)
        self.assertGreater(strength, 0.8)


if __name__ == "__main__":
    unittest.main()
