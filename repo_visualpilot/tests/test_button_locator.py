from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from visualpilot.lab.button_locator import load_template, locate_button


class ButtonLocatorTests(unittest.TestCase):
    def setUp(self):
        self.button = np.full((34, 128, 3), 230, np.uint8)
        cv2.rectangle(self.button, (0, 0), (127, 33), (80, 80, 80), 1)
        cv2.putText(self.button, 'Registrar', (7, 25), cv2.FONT_HERSHEY_SIMPLEX,
                    .65, (10, 10, 10), 1, cv2.LINE_AA)
        self.screen = np.full((300, 500, 3), 255, np.uint8)

    def test_center_includes_crop_origin_and_negative_monitor_origin(self):
        self.screen[70:104, 160:288] = self.button
        for origin in ((0, 0), (300, 200), (-1920, 30)):
            with self.subTest(origin=origin):
                found = locate_button(self.screen, self.button, origin=origin)
                self.assertEqual(found['status'], 'found')
                self.assertEqual(found['point'], [224+origin[0], 87+origin[1]])

    def test_two_distinct_matches_are_ambiguous_even_if_one_is_perfect(self):
        self.screen[40:74, 20:148] = self.button
        self.screen[200:234, 300:428] = self.button
        found = locate_button(self.screen, self.button)
        self.assertEqual(found['status'], 'ambiguous')
        self.assertNotIn('point', found)
        self.assertEqual(len(found['candidates']), 2)

    def test_overlapping_scale_peaks_are_one_button(self):
        self.screen[70:104, 160:288] = self.button
        result = locate_button(self.screen, self.button, scales=(.98, 1., 1.02))
        self.assertEqual(result['status'], 'found')
        self.assertEqual(result['point'], [224, 87])

    def test_scaled_image_has_correct_center(self):
        scaled = cv2.resize(self.button, (160, 42), interpolation=cv2.INTER_LINEAR)
        self.screen[90:132, 240:400] = scaled
        found = locate_button(self.screen, self.button)
        self.assertEqual(found['status'], 'found')
        self.assertEqual(found['point'], [320, 111])
        self.assertEqual(found['scale'], 1.25)

    def test_missing_clipped_and_constant_background_do_not_return_coordinates(self):
        self.assertEqual(locate_button(self.screen, self.button)['status'], 'missing')
        self.screen[80:114, :60] = self.button[:, :60]
        self.assertEqual(locate_button(self.screen, self.button)['status'], 'missing')
        self.assertEqual(locate_button(self.screen[:10, :10], self.button)['status'], 'missing')

    def test_invalid_template_and_parameters_are_explicit(self):
        for template in (None, np.zeros((20, 20, 3), np.uint8), np.zeros((2, 2), np.uint8)):
            with self.assertRaises(ValueError): locate_button(self.screen, template)
        for kwargs in (dict(threshold=float('nan')), dict(threshold=.1), dict(origin=(.5, 0)),
                       dict(scales=()), dict(scales=(float('inf'),))):
            with self.assertRaises(ValueError): locate_button(self.screen, self.button, **kwargs)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'broken.png'; path.write_text('not an image')
            with self.assertRaises(ValueError): load_template(path)


if __name__ == '__main__':
    unittest.main()
