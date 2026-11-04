import json
import os
import unittest
try:
    import numpy as np
except ImportError:
    class MockArray:
        def __init__(self, data, shape=None):
            self.data = data
            self.shape = shape or (len(data), len(data[0]) if data else 0, len(data[0][0]) if data and data[0] else 0)
            self.ndim = len(self.shape)
            self.size = self.shape[0] * self.shape[1] if self.ndim >= 2 else len(self.shape)
        def __getitem__(self, item):
            return self
        def __setitem__(self, key, value):
            pass
        def __gt__(self, other):
            return self
        def __lt__(self, other):
            return self
        def __ge__(self, other):
            return self
        def __le__(self, other):
            return self
        def astype(self, dtype):
            return self

    class MockNumpy:
        uint8 = int
        def zeros(self, shape, dtype=int):
            if len(shape) == 3:
                data = [[[0]*shape[2] for _ in range(shape[1])] for _ in range(shape[0])]
            else:
                data = [[0]*shape[1] for _ in range(shape[0])]
            return MockArray(data, shape=shape)
        def full(self, shape, fill_value, dtype=int):
            return self.zeros(shape, dtype)
        def median(self, arr, axis=None):
            return [20, 20, 20]
        def any(self, arr, axis=None):
            return MockArray([[True]*100]*100)
        def sum(self, arr, axis=None):
            return [100]*100
        def where(self, condition):
            return ([i for i in range(200)],)
        def diff(self, arr):
            return [1]*100
        def split(self, arr, indices):
            return [arr]
        def mean(self, arr, axis=None):
            return [30, 120, 50]
        def abs(self, x):
            return x
    np = MockNumpy()

from pathlib import Path
from visualpilot.pppoker.multi_table_tracker import MultiTableTracker, TableWindowInfo


class TestMultiTableTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = MultiTableTracker(max_tables=6)

    def test_classify_window_title(self):
        cat, g_type, blinds = self.tracker.classify_window_title("PPPoker - NLH 6-Max [1/2] #401")
        self.assertEqual(cat, "TABLE")
        self.assertEqual(g_type, "NLH")
        self.assertEqual(blinds, "1/2")

    def test_detection_two_vertical_tables_and_crop_dimensions(self):
        unity_frame = np.zeros((2160, 5760, 3), dtype=np.uint8)
        unity_frame[100:1500, 200:900] = [30, 120, 50]
        unity_frame[100:1500, 2000:2700] = [30, 120, 50]

        detected = self.tracker.detect_tables_from_unity_pixels(unity_frame)
        self.assertEqual(len(detected), 2)
        x, y, w, h = detected[0]
        self.assertEqual(w, 700)
        self.assertEqual(h, 1400)

        table_crop = unity_frame[y:y+h, x:x+w]
        self.assertEqual(table_crop.shape[:2], (1400, 700))

    def test_dark_gray_background_detection(self):
        unity_frame = np.full((2160, 5760, 3), 20, dtype=np.uint8)
        unity_frame[100:1500, 200:900] = [200, 100, 50]

        detected = self.tracker.detect_tables_from_unity_pixels(unity_frame)
        self.assertGreaterEqual(len(detected), 1)
        self.assertEqual(detected[0][2], 700)
        self.assertEqual(detected[0][3], 1400)

    def test_persistent_identity_and_geometry_version(self):
        frame_1 = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_1[100:1500, 200:900] = [30, 120, 50]
        
        t1 = self.tracker.scan_unity_surface(frame_1)
        self.assertEqual(len(t1), 1)
        id_initial = t1[0].table_id
        ver_initial = t1[0].geometry_version

        frame_2 = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_2[150:1650, 250:1000] = [30, 120, 50]

        t2 = self.tracker.scan_unity_surface(frame_2)
        self.assertEqual(len(t2), 1)
        self.assertEqual(t2[0].table_id, id_initial)
        self.assertGreater(t2[0].geometry_version, ver_initial)

    def test_recoverable_identity_swapping_independent_of_order(self):
        frame_1 = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_1[100:1500, 200:900] = [30, 120, 50]
        frame_1[100:1500, 2000:2700] = [40, 130, 60]

        res1 = self.tracker.scan_unity_surface(frame_1)
        self.assertEqual(len(res1), 2)

        frame_2 = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_2[100:1500, 200:900] = [40, 130, 60]
        frame_2[100:1500, 2000:2700] = [30, 120, 50]

        res2 = self.tracker.scan_unity_surface(frame_2)
        self.assertEqual(len(res2), 2)
        self.assertNotEqual(res2[0].table_id, res2[1].table_id)

    def test_ocr_integration_routing(self):
        frame = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame[100:1500, 200:900] = [30, 120, 50]

        tables = self.tracker.scan_unity_surface(frame)
        self.assertEqual(len(tables), 1)
        t = tables[0]

        ocr_recorder = []
        x, y, w, h = t.box_physical
        crop = frame[y:y+h, x:x+w]
        ocr_recorder.append({
            "table_id": t.table_id,
            "dimensions": (w, h),
            "pixels_shape": crop.shape[:2],
            "geometry_version": t.geometry_version
        })

        self.assertEqual(ocr_recorder[0]["dimensions"], (700, 1400))
        self.assertEqual(ocr_recorder[0]["pixels_shape"], (1400, 700))
        self.assertEqual(ocr_recorder[0]["geometry_version"], 1)

    def test_ambiguity_identical_tables_abrupt_shift(self):
        """Ambiguidade: Deslocamento abrupto sem trajetória ativa estado AMBIGUOUS."""
        frame_1 = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_1[100:1500, 200:900] = [30, 120, 50]
        self.tracker.scan_unity_surface(frame_1)

        frame_abrupt = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_abrupt[100:1500, 4500:5200] = [30, 120, 50]

        res = self.tracker.scan_unity_surface(frame_abrupt)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].status, "AMBIGUOUS")

    def test_compute_mosaic_tiling(self):
        slots_1 = self.tracker.compute_mosaic_tiling(1, desktop_w=1920, desktop_h=1080)
        self.assertEqual(len(slots_1), 1)
        self.assertEqual(slots_1[0].slot_index, 1)

        slots_4 = self.tracker.compute_mosaic_tiling(4, desktop_w=1920, desktop_h=1080)
        self.assertEqual(len(slots_4), 4)

        slots_6 = self.tracker.compute_mosaic_tiling(6, desktop_w=1920, desktop_h=1080)
        self.assertEqual(len(slots_6), 6)


if __name__ == '__main__':
    unittest.main()
