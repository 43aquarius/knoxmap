import unittest

from knoxbuild import layout


class FurnishedRoomWalkability(unittest.TestCase):
    def test_furniture_is_removed_from_window_approach(self):
        room = layout.Room(0, 0, 4, 4, kind="livingroom")
        plan = layout.Plan(
            5, 5, rooms=[room], grid=[[1] * 5 for _ in range(5)],
            doors=[(2, 0, "N")], windows=[(0, 2, "W")],
            furniture=[("bookshelf", 0, 2, "N")])
        building = layout.Building(5, 5, storeys=[plan])

        removed = layout._clear_the_way(building)

        self.assertEqual(removed, 1)
        self.assertNotIn(("bookshelf", 0, 2, "N"), plan.furniture)

    def test_furniture_partition_is_opened_for_room_walkability(self):
        room = layout.Room(0, 0, 4, 4, kind="livingroom")
        furniture = [("bookshelf", 2, y, "N") for y in range(5)]
        plan = layout.Plan(
            5, 5, rooms=[room], grid=[[1] * 5 for _ in range(5)],
            doors=[(0, 2, "W")], furniture=furniture)
        building = layout.Building(5, 5, storeys=[plan])

        removed = layout._clear_the_way(building)

        self.assertGreater(removed, 0)
        self.assertLess(len(plan.furniture), len(furniture))


if __name__ == "__main__":
    unittest.main()
