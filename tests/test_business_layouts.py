import random
import unittest

from knoxbuild import build, layout
from knoxbuild.settings import Settings
from knoxbuild.uses import use_of


class BusinessLayouts(unittest.TestCase):
    def test_car_repair_tags_select_a_garage_with_mechanic_use(self):
        self.assertEqual(use_of({"shop": "car_repair"}), ("mechanic", "storage"))
        self.assertEqual(build.classify_building({"shop": "car_repair"}), "garage")
        self.assertEqual(build._business_kind("shop", [("mechanic", "storage")]),
                         "garage")
        self.assertEqual(build._business_kind("house", [("mechanic", "storage")]),
                         "house")

        shell = build.pick_style(build.STYLE_AS["garage"], 20, 30,
                                 random.Random(8), Settings(), density=0.2)
        self.assertTrue(shell["name"].startswith("industrial"))

    def test_mechanic_layout_keeps_a_clear_service_bay(self):
        building = layout.build_building(
            16, 12, kind="garage", uses=[("mechanic", "storage")],
            street="S", garage_door=True, seed=17)
        plan = building.storeys[0]

        self.assertEqual(len(plan.rooms), 1)
        self.assertEqual(plan.rooms[0].kind, "mechanic")
        self.assertFalse(plan.shop_front)
        self.assertFalse(plan.windows)
        self.assertIn("metal_rack", {role for role, *_ in plan.furniture})
        self.assertIn("counter_2", {role for role, *_ in plan.furniture})

        south_walls = [wall for room_id in range(1, len(plan.rooms) + 1)
                       for side, wall in layout._outside_runs(plan, room_id)
                       if side == "S"]
        self.assertTrue(any(sum(edge in plan.doors for edge in wall) >= 3
                            for wall in south_walls))

        for role, x, y, facing in plan.furniture:
            self.assertFalse(any(4 <= cx <= 11 and 3 <= cy <= 8
                                 for cx, cy in layout._cells_for(role, x, y, facing)))


if __name__ == "__main__":
    unittest.main()