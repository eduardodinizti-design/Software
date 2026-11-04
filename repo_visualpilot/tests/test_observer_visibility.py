import unittest
import numpy as np
from visualpilot.pppoker.observer_visibility import prepare_observer_frame, candidate_visibility


class ObserverVisibilityTests(unittest.TestCase):
    def test_negative_origin_and_only_one_table_blocked(self):
        source = np.full((400, 800, 3), 120, dtype=np.uint8)
        blockers = [{"box": (-1900, 20, 100, 200)}]
        masked = prepare_observer_frame(source, (-1920, 0, 800, 400), blockers)
        self.assertFalse(masked[20:220, 20:120].any())
        self.assertTrue((masked[:, 400:] == 120).all())
        self.assertTrue((source == 120).all())
        self.assertEqual(candidate_visibility((-1900, 20, 200, 300), blockers), "OCCLUDED")
        self.assertEqual(candidate_visibility((-1500, 20, 200, 300), blockers), "CLEAR")

    def test_clipping_and_external_window(self):
        frame = np.ones((100, 100, 3), dtype=np.uint8)
        result = prepare_observer_frame(frame, (0, 0, 100, 100),
            [{"box": (-50, -50, 60, 60)}, {"box": (300, 300, 40, 40)}])
        self.assertFalse(result[:10, :10].any())
        self.assertTrue(result[10:, 10:].all())

    def test_contour_at_mask_boundary_is_blocked(self):
        self.assertEqual(candidate_visibility((0,0,100,100), [{"box": (100,0,20,100)}]), "OCCLUDED")
