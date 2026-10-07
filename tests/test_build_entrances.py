import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import numpy as np

from knoxbuild import build
from knoxbuild.footprint import Footprint
from knoxbuild.profile import BuildingProfile


class EntrancePointMapping(unittest.TestCase):
    def test_entrance_nodes_are_not_consumed_as_points_of_use(self):
        grid = {(0, 0): [(10.5, 10.0, {"entrance": "main"}),
                         (10.5, 10.0, {"shop": "bakery"})]}
        outline = [(10, 10), (20, 10), (20, 20), (10, 20)]
        taken = set()
        self.assertEqual(build._points_inside(grid, outline, taken), [{"shop": "bakery"}])
        self.assertEqual(build._entrances_inside(grid, outline),
                         [(10.5, 10.0, {"entrance": "main"})])

    def test_split_footprint_receives_nearby_entrance_locally(self):
        units = [Footprint(10, 20, np.ones((4, 4), dtype=bool), 0, 4, 4),
                 Footprint(14, 20, np.ones((4, 4), dtype=bool), 0, 4, 4)]
        entrances = build._entrances_by_unit(
            [(17.5, 21.5, {"entrance": "main"})], units)
        self.assertEqual(entrances[0], [])
        self.assertEqual(entrances[1], [(3.5, 1.5, {"entrance": "main"})])

    def test_worker_forwards_entrances_after_party_walls(self):
        entrances = [(2.0, 0.0, {"entrance": "main"})]
        profile = BuildingProfile.infer({}, "house", 0.15, 90, 1, 4)
        party = {(0, 0, "N"): 1}
        plan = SimpleNamespace(storeys=[], rooms=[], furniture=[], escalators=[])
        with TemporaryDirectory() as directory:
            path = f"{directory}/building.tbx"
            job = (4, 4, 1, False, 1, "hospital", None, None, None, "hospital",
                     path, None, False, [], False, entrances, profile, [], party)
            with mock.patch.object(build, "build_building", return_value=plan) as make, \
                    mock.patch.object(build, "render_tbx", return_value="tbx"):
                result = build._make_one(job)
            self.assertIsNone(result[3])
            make.assert_called_once()
            self.assertEqual(make.call_args.kwargs["entrances"], entrances)
            self.assertIs(make.call_args.kwargs["profile"], profile)
            self.assertEqual(make.call_args.kwargs["party"], party)


if __name__ == "__main__":
    unittest.main()