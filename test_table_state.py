"""Table-state reader: amount parsing, seat geometry, abstention.

Pure logic plus OCR-mocked reads (lab-safe). The 9/9 accuracy on a real gabarito
is validated live, not here; these tests pin the parsing rules and structure."""
import unittest
from unittest.mock import patch
import numpy as np

from table_reading import seat_layout, table_state


class ParseAmountTests(unittest.TestCase):
    def test_comma_is_high_confidence(self):
        self.assertEqual(table_state.parse_amount('buzZzylay 291,8 BB'), (291.8, 'high'))

    def test_dropped_comma_restored_as_one_decimal_medium(self):
        self.assertEqual(table_state.parse_amount('pp108ae | 1431BB'), (143.1, 'medium'))
        self.assertEqual(table_state.parse_amount('Mr.Tomate 1229BR'), (122.9, 'medium'))

    def test_pot_with_dropped_comma(self):
        self.assertEqual(table_state.parse_amount('Pot: 257 BB'), (25.7, 'medium'))

    def test_unreadable_abstains(self):
        self.assertEqual(table_state.parse_amount(''), (None, 'abstain'))
        self.assertEqual(table_state.parse_amount('----'), (None, 'abstain'))


class SeatLayoutTests(unittest.TestCase):
    def test_nine_unique_seats_hero_first(self):
        self.assertEqual(len(seat_layout.SEAT_ANCHORS), 9)
        self.assertEqual(set(seat_layout.CLOCKWISE), set(seat_layout.SEAT_ANCHORS))
        self.assertEqual(seat_layout.CLOCKWISE[0], 'hero')

    def test_nameplate_box_within_bounds_and_centered(self):
        x0, y0, x1, y1 = seat_layout.nameplate_box(750, 1334, 'hero')
        self.assertTrue(0 <= x0 < x1 <= 750 and 0 <= y0 < y1 <= 1334)
        self.assertAlmostEqual((x0 + x1) / 2, 375, delta=2)   # hero fx=0.50
        self.assertAlmostEqual((y0 + y1) / 2, int(0.90 * 1334), delta=2)


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.crop = np.zeros((1334, 750, 3), np.uint8)

    def test_read_seat_stacks_covers_all_seats(self):
        with patch('table_reading.table_state.image_to_string', return_value='Hero 63,1 BB'):
            seats = table_state.read_seat_stacks(self.crop)
        self.assertEqual(set(seats), set(seat_layout.SEAT_ANCHORS))
        self.assertTrue(all(s['stack_bb'] == 63.1 for s in seats.values()))

    def test_unreadable_stack_abstains(self):
        with patch('table_reading.table_state.image_to_string', return_value=''):
            seats = table_state.read_seat_stacks(self.crop)
        self.assertTrue(all(s['stack_bb'] is None for s in seats.values()))

    def test_table_state_structure_is_labelled(self):
        with patch('table_reading.table_state.image_to_string', return_value=''):
            state = table_state.read_table_state(self.crop)
        self.assertTrue(state['experimental'])
        self.assertEqual(len(state['seats']), 9)
        self.assertIn('pot_bb', state['pot'])
        self.assertIn('seat', state['dealer'])
        self.assertEqual(state['positions'], {})  # no dealer badge -> no positions
        self.assertEqual(set(state['pending']), {'bets', 'to_call_bb'})

    def test_bad_crop_rejected(self):
        with self.assertRaises(ValueError):
            table_state.read_table_state(np.zeros((10, 10), np.uint8))


class OccupancyTests(unittest.TestCase):
    def test_blue_felt_seat_is_empty_avatar_photo_is_occupied(self):
        felt = np.zeros((1334, 750, 3), np.uint8); felt[:] = (200, 90, 40)   # blue felt (BGR)
        occ = table_state.read_occupancy(felt)
        self.assertTrue(all(not s['occupied'] for s in occ.values()))
        # a non-blue textured avatar over every seat -> occupied
        photo = felt.copy()
        for seat in seat_layout.SEAT_ANCHORS:
            x0, y0, x1, y1 = seat_layout.avatar_box(750, 1334, seat)
            photo[y0:y1, x0:x1] = np.random.randint(0, 255, (y1 - y0, x1 - x0, 3), np.uint8)
        occ2 = table_state.read_occupancy(photo)
        self.assertTrue(all(s['occupied'] for s in occ2.values()))

    def test_stacks_and_occupancy_are_independent(self):
        crop = np.zeros((1334, 750, 3), np.uint8); crop[:] = (200, 90, 40)
        for seat in seat_layout.SEAT_ANCHORS:
            x0, y0, x1, y1 = seat_layout.avatar_box(750, 1334, seat)
            crop[y0:y1, x0:x1] = np.random.randint(0, 255, (y1 - y0, x1 - x0, 3), np.uint8)
        with patch('table_reading.table_state.image_to_string', return_value=''):
            state = table_state.read_table_state(crop)
        self.assertTrue(all(s['occupied'] and s['stack_bb'] is None for s in state['seats'].values()))


if __name__ == '__main__':
    unittest.main()
