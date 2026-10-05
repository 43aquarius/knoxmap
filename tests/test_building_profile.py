import unittest

from knoxbuild.profile import BuildingProfile


class BuildingProfileTests(unittest.TestCase):
    def test_inference_is_reproducible_and_uses_explicit_tags(self):
        tags = {"start_date": "1922", "building:condition": "poor",
                "class": "luxury", "building": "mansion"}
        profile = BuildingProfile.infer(tags, "house", 0.12, 700, 2, 41)
        self.assertEqual(profile, BuildingProfile.infer(tags, "house", 0.12, 700, 2, 41))
        self.assertEqual(profile.year_built, 1922)
        self.assertEqual(profile.era, "prewar")
        self.assertEqual(profile.setting, "suburban")
        self.assertEqual(profile.wear, 0.76)
        self.assertGreater(profile.wealth, 0.7)

    def test_neighborhood_setting_uses_density_and_building_type(self):
        rural = BuildingProfile.infer({}, "house", 0.02, 100, 1, 4)
        suburban = BuildingProfile.infer({}, "house", 0.14, 100, 1, 4)
        urban = BuildingProfile.infer({}, "apartment", 0.4, 100, 4, 4)
        barn = BuildingProfile.infer({"building": "barn"}, None, 0.2, 100, 1, 4)
        self.assertEqual((rural.setting, suburban.setting, urban.setting, barn.setting),
                         ("rural", "suburban", "urban", "rural"))

    def test_profile_weights_shell_furniture_and_floor_families(self):
        old_worn = BuildingProfile.infer(
            {"start_date": "1900", "condition": "poor"}, "house", 0.1, 100, 1, 2)
        new_clean = BuildingProfile.infer(
            {"start_date": "1985", "condition": "excellent", "class": "luxury"},
            "house", 0.35, 700, 2, 3)
        self.assertGreater(old_worn.style_weight("brick"), old_worn.style_weight("render"))
        self.assertGreater(new_clean.furniture_weight("dresser_black"),
                           new_clean.furniture_weight("dresser_pale"))
        self.assertGreater(old_worn.floor_weight("civic_worn"),
                           old_worn.floor_weight("wood_pale"))
        self.assertLess(new_clean.clutter, old_worn.clutter)


if __name__ == "__main__":
    unittest.main()
