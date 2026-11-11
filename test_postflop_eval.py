"""Testes do núcleo de avaliação pós-flop (board + força da mão). Casos conhecidos."""
import unittest

from postflop_eval import classify_board, hand_strength


class BoardTests(unittest.TestCase):
    def test_rainbow_structure(self):
        b = classify_board(['As', '9h', '3d'])
        self.assertEqual(b['texture'], 'rainbow')
        self.assertFalse(b['paired'])
        self.assertEqual(b['structure'], ['A', 'M', 'L'])
        self.assertEqual(b['flush_count'], 1)
        self.assertFalse(b['flush_possible'])
        self.assertEqual(b['high_rank'], 14)

    def test_monotone_flush_possible(self):
        b = classify_board(['As', '9s', '3s'])
        self.assertEqual(b['texture'], 'monotone')
        self.assertTrue(b['flush_possible'])
        self.assertEqual(b['flush_count'], 3)

    def test_two_tone(self):
        b = classify_board(['Qs', '7s', '2d'])
        self.assertEqual(b['texture'], 'two_tone')
        self.assertFalse(b['flush_possible'])

    def test_paired_low(self):
        b = classify_board(['7h', '7c', '2d'])
        self.assertTrue(b['paired'])
        self.assertFalse(b['trips'])
        self.assertEqual(b['structure'], ['M', 'L'])

    def test_connected_straightish(self):
        b = classify_board(['9h', '8c', '7d'])
        self.assertEqual(b['straightish'], 3)      # 9-8-7 em janela de 5
        self.assertFalse(b['straight_on_board'])

    def test_straight_on_board(self):
        b = classify_board(['9h', '8c', '7d', '6s', '5h'])
        self.assertTrue(b['straight_on_board'])
        self.assertEqual(b['texture'], 'flush_2')

    def test_wheel_uses_ace_low(self):
        b = classify_board(['Ah', '2c', '3d', '4s', '5h'])
        self.assertTrue(b['straight_on_board'])

    def test_invalid_size(self):
        with self.assertRaises(ValueError):
            classify_board(['As', 'Kd'])


class HandStrengthTests(unittest.TestCase):
    def test_top_pair(self):
        r = hand_strength(['As', 'Qc'], ['Ah', '9h', '3d'])
        self.assertEqual(r['category_name'], 'pair')
        self.assertEqual(r['made'], 'top_pair')

    def test_overpair(self):
        r = hand_strength(['Ks', 'Kc'], ['9h', '3d', '2c'])
        self.assertEqual(r['made'], 'overpair')

    def test_underpair(self):
        r = hand_strength(['5s', '5c'], ['Ah', 'Qd', '2c'])
        self.assertEqual(r['made'], 'underpair')

    def test_set_from_pocket(self):
        r = hand_strength(['3c', '3h'], ['As', '9h', '3d'])
        self.assertEqual(r['category_name'], 'trips')
        self.assertEqual(r['made'], 'set')

    def test_trips_from_one_card(self):
        r = hand_strength(['3c', 'Kh'], ['3s', '3h', '9d'])
        self.assertEqual(r['made'], 'trips')

    def test_board_pair_only(self):
        r = hand_strength(['Ks', 'Qc'], ['7h', '7c', '2d'])
        self.assertEqual(r['category_name'], 'pair')
        self.assertEqual(r['made'], 'board_pair_only')

    def test_two_pair(self):
        r = hand_strength(['As', '9c'], ['Ah', '9h', '3d'])
        self.assertEqual(r['made'], 'two_pair')

    def test_flush_draw_nine_outs(self):
        r = hand_strength(['As', 'Ks'], ['Qs', '7s', '2d'])
        self.assertTrue(r['draws']['flush_draw'])
        self.assertEqual(r['draws']['flush_outs'], 9)
        self.assertEqual(r['outs'], 9)

    def test_oesd_eight_outs(self):
        r = hand_strength(['9s', '8d'], ['7h', '6c', '2s'])
        self.assertTrue(r['draws']['oesd'])
        self.assertEqual(r['draws']['straight_outs'], 8)

    def test_gutshot_four_outs(self):
        r = hand_strength(['9s', '5d'], ['7h', '6c', '2s'])
        self.assertTrue(r['draws']['gutshot'])
        self.assertEqual(r['draws']['straight_outs'], 4)

    def test_combo_draw_capped(self):
        # flush draw (spades: 9s8s7s6s=4) + OESD (T/5); total descontando overlap, cap 15
        r = hand_strength(['9s', '8s'], ['7s', '6s', '2d'])
        self.assertTrue(r['draws']['combo'])
        self.assertLessEqual(r['outs'], 15)
        self.assertGreaterEqual(r['outs'], 12)

    def test_made_straight_no_draw_outs(self):
        r = hand_strength(['9s', '8d'], ['7h', '6c', '5s'])
        self.assertEqual(r['category_name'], 'straight')
        self.assertEqual(r['draws']['straight_outs'], 0)

    def test_made_flush(self):
        r = hand_strength(['As', '7s'], ['Ks', '9s', '2s'])
        self.assertEqual(r['category_name'], 'flush')

    def test_overcards(self):
        r = hand_strength(['As', 'Kd'], ['9h', '7c', '2s'])
        self.assertEqual(r['made'], 'overcards')

    def test_air(self):
        r = hand_strength(['7s', '4d'], ['Ah', 'Kc', '9s'])
        self.assertEqual(r['made'], 'air')

    def test_duplicate_card_returns_none(self):
        self.assertIsNone(hand_strength(['As', 'Kd'], ['As', '9h', '3d']))

    def test_turn_and_river_sizes(self):
        self.assertIsNotNone(hand_strength(['As', 'Qc'], ['Ah', '9h', '3d', '5c']))
        self.assertIsNotNone(hand_strength(['As', 'Qc'], ['Ah', '9h', '3d', '5c', 'Jd']))


if __name__ == '__main__':
    unittest.main()
