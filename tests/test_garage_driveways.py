import os
import unittest
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from generator import pz_colors as C
from knoxbuild.yards import paint_paths


class GarageDriveways(unittest.TestCase):
    def test_garage_door_gets_an_asphalt_path_to_the_road(self):
        with TemporaryDirectory() as directory:
            os.mkdir(os.path.join(directory, "buildings"))
            ground = Image.new("RGB", (40, 30), C.DARK_GRASS)
            for x in range(40):
                ground.putpixel((x, 15), C.MEDIUM_ASPHALT)
            ground.save(os.path.join(directory, "map.bmp"))
            room_grid = "\n".join(",".join(["1"] * 8) for _ in range(8))
            with open(os.path.join(directory, "buildings", "garage.tbx"),
                      "w", encoding="utf-8") as tbx:
                tbx.write(f'<floor><rooms>{room_grid}</rooms>'
                          '<object type="door" x="0" y="3" dir="W"/>'
                          '</floor>')
            occupied = np.zeros((30, 40), dtype=bool)
            occupied[10:18, 10:18] = True
            rows = [{"file": "garage.tbx", "building": "garage",
                     "tile_x": 10, "tile_y": 10}]

            paint_paths(directory, "map", rows, occupied)

            with Image.open(os.path.join(directory, "map.bmp")) as result:
                self.assertEqual(result.getpixel((9, 13)), C.DARK_ASPHALT)
                self.assertEqual(result.getpixel((9, 14)), C.DARK_ASPHALT)
                self.assertEqual(result.getpixel((9, 15)), C.MEDIUM_ASPHALT)

    def test_car_repair_business_kind_also_gets_a_driveway(self):
        with TemporaryDirectory() as directory:
            os.mkdir(os.path.join(directory, "buildings"))
            ground = Image.new("RGB", (40, 30), C.DARK_GRASS)
            for x in range(40):
                ground.putpixel((x, 15), C.MEDIUM_ASPHALT)
            ground.save(os.path.join(directory, "map.bmp"))
            room_grid = "\n".join(",".join(["1"] * 8) for _ in range(8))
            with open(os.path.join(directory, "buildings", "repair.tbx"),
                      "w", encoding="utf-8") as tbx:
                tbx.write(f'<floor><rooms>{room_grid}</rooms>'
                          '<object type="door" x="0" y="3" dir="W"/>'
                          '</floor>')
            occupied = np.zeros((30, 40), dtype=bool)
            occupied[10:18, 10:18] = True
            rows = [{"file": "repair.tbx", "building": "retail",
                     "kind": "garage", "tile_x": 10, "tile_y": 10}]

            paint_paths(directory, "map", rows, occupied)

            with Image.open(os.path.join(directory, "map.bmp")) as result:
                self.assertEqual(result.getpixel((9, 13)), C.DARK_ASPHALT)


if __name__ == "__main__":
    unittest.main()