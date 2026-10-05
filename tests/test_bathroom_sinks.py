import unittest

from knoxbuild import layout


class BathroomSinkSupport(unittest.TestCase):
    def make_plan(self, room_kind, role):
        room = layout.Room(0, 0, 2, 2, kind=room_kind)
        plan = layout.Plan(3, 3, rooms=[room], grid=[[1] * 3 for _ in range(3)])
        plan.furniture.append((role, 1, 1, "N"))
        return plan, room

    def test_pedestal_public_basin_does_not_get_counter_support(self):
        plan, room = self.make_plan("bathroom", "sink_public")

        layout._stand_on_something(plan, 1, room, {})

        self.assertEqual(plan.furniture, [("sink_public", 1, 1, "N")])

    def test_kitchen_sink_keeps_counter_support(self):
        plan, room = self.make_plan("kitchen", "kitchen_sink")

        layout._stand_on_something(plan, 1, room, {})

        self.assertEqual([role for role, *_ in plan.furniture],
                         ["counter", "kitchen_sink"])


if __name__ == "__main__":
    unittest.main()
