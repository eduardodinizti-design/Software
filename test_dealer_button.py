"""Dealer button: badge->seat mapping and position derivation.

Synthetic green badge and pure position logic (lab-safe). The real button->seat
accuracy is validated live on gabaritos; these pin the geometry and naming."""
import unittest
import numpy as np

from table_reading import dealer_button, seat_layout


class BadgeTests(unittest.TestCase):
    def _crop_with_badge(self, fx, fy, w=750, h=1334):
        crop = np.zeros((h, w, 3), np.uint8)
        cx, cy = int(fx * w), int(fy * h)
        crop[cy - 16:cy + 16, cx - 15:cx + 15] = (40, 200, 40)  # bright green blob (BGR)
        return crop

    def test_badge_maps_to_nearest_seat(self):
        for seat, (fx, fy) in seat_layout.SEAT_ANCHORS.items():
            if fy > 0.80 or fy < 0.12:   # badge detector ignores the very top/bottom bands
                continue
            found = dealer_button.find_dealer_seat(self._crop_with_badge(fx, fy))
            self.assertEqual(found['seat'], seat)
            self.assertEqual(found['confidence'], 'high')

    def test_no_badge_abstains(self):
        found = dealer_button.find_dealer_seat(np.zeros((1334, 750, 3), np.uint8))
        self.assertIsNone(found['seat'])
        self.assertEqual(found['confidence'], 'abstain')


class PositionTests(unittest.TestCase):
    def test_full_ring_naming_from_button(self):
        occupied = list(seat_layout.CLOCKWISE)
        pos = dealer_button.derive_positions('hero', occupied)
        self.assertEqual(pos['hero'], 'BTN')
        self.assertEqual(pos['bot_right'], 'SB')   # next clockwise
        self.assertEqual(pos['right_low'], 'BB')
        self.assertEqual(pos['bot_left'], 'CO')     # last before the button
        self.assertEqual(len(pos), 9)

    def test_button_must_be_occupied(self):
        self.assertEqual(dealer_button.derive_positions('hero', ['bot_right', 'right_low']), {})

    def test_short_ring_names_blinds(self):
        pos = dealer_button.derive_positions('hero', ['hero', 'bot_right', 'right_low'])
        self.assertEqual(pos, {'hero': 'BTN', 'bot_right': 'SB', 'right_low': 'BB'})


if __name__ == '__main__':
    unittest.main()
