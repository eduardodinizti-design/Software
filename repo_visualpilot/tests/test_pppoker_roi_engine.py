from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from visualpilot.pppoker.roi_engine import (REGIONS, TableROIEngine,
                                            frame_signature, region_hashes,
                                            scaled_box)


FIXTURES = Path(__file__).parent / "fixtures" / "actions"


class ROIEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.left = np.array(Image.open(FIXTURES / "left_99.png").convert("RGB"))
        cls.right = np.array(Image.open(FIXTURES / "right_99.png").convert("RGB"))

    def test_real_frames_have_distinct_critical_regions(self):
        left = region_hashes(self.left)
        right = region_hashes(self.right)
        for name in ("hand_id", "total_pot", "board_flop", "hero_cards",
                     "action_buttons", "observed_actions"):
            with self.subTest(region=name):
                self.assertNotEqual(left[name], right[name])

    def test_one_pixel_suit_change_invalidates_hero_only(self):
        changed = self.left.copy()
        # Dentro da caixa real do naipe da segunda carta do Hero.
        changed[1231, 525, 1] ^= 1
        before, after = region_hashes(self.left), region_hashes(changed)
        differences = {name for name in REGIONS if before[name] != after[name]}
        self.assertEqual(differences, {"hero_cards"})
        self.assertNotEqual(frame_signature(self.left), frame_signature(changed))

    def test_irrelevant_animation_outside_rois_hits_cache(self):
        engine = TableROIEngine()
        engine.inspect(self.left)
        changed = self.left.copy()
        changed[50, 50] ^= 255
        result = engine.inspect(changed)
        self.assertTrue(result["cache_hit"])
        self.assertEqual(result["changed"], [])

    def test_hand_id_change_invalidates_every_region(self):
        engine = TableROIEngine()
        engine.inspect(self.left)
        changed = self.left.copy()
        changed[1000, 300] ^= 1
        result = engine.inspect(changed)
        self.assertTrue(result["hand_changed"])
        self.assertEqual(result["changed"], list(REGIONS))

    def test_scales_to_runtime_normalized_width(self):
        box = scaled_box(REGIONS["hero_cards"][0], 755, 1343)
        self.assertLessEqual(box[1], 431)
        self.assertGreaterEqual(box[3], 544)
        self.assertLessEqual(box[0], 1073)
        self.assertGreaterEqual(box[2], 1183)

    def test_rejects_invalid_images(self):
        for image in (None, np.array([]), np.zeros((200, 200), dtype=np.uint8)):
            with self.subTest(shape=getattr(image, "shape", None)):
                with self.assertRaises(ValueError):
                    region_hashes(image)


if __name__ == "__main__":
    unittest.main()
