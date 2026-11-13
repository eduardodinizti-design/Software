"""Penalidade de equidade multiway + bloqueio de c-bet blefe."""
import unittest

from multiway_equity import (apply_multiway_penalty, cbet_bluff_blocked,
                             count_opponents, extra_villains, penalty_pct)


class PenaltyTests(unittest.TestCase):
    def test_heads_up_no_penalty(self):
        self.assertEqual(apply_multiway_penalty(0.5, 1), 0.5)
        self.assertEqual(penalty_pct(1), 0)

    def test_minus_12pct_per_extra_relative(self):
        self.assertAlmostEqual(apply_multiway_penalty(0.5, 2), 0.5 * 0.88)   # 1 extra
        self.assertAlmostEqual(apply_multiway_penalty(0.5, 3), 0.5 * 0.76)   # 2 extra
        self.assertEqual((penalty_pct(2), penalty_pct(3)), (12, 24))

    def test_none_passthrough_and_floor(self):
        self.assertIsNone(apply_multiway_penalty(None, 5))
        self.assertGreaterEqual(apply_multiway_penalty(0.9, 20), 0.0)

    def test_extra_villains(self):
        self.assertEqual((extra_villains(1), extra_villains(3), extra_villains(None)), (0, 2, 0))


class BluffBlockTests(unittest.TestCase):
    def test_blocked_only_over_two_opponents(self):
        self.assertFalse(cbet_bluff_blocked(1))
        self.assertFalse(cbet_bluff_blocked(2))        # 3-way = 2 opp: ainda permite
        self.assertTrue(cbet_bluff_blocked(3))         # 4-way = 3 opp: bloqueia
        self.assertFalse(cbet_bluff_blocked(None))


class CountTests(unittest.TestCase):
    def test_counts_active_non_hero_seats(self):
        ts = dict(seats={'hero': {'stack_bb': 40}, 'a': {'stack_bb': 30},
                         'b': {'in_hand': True}, 'c': {}})
        self.assertEqual(count_opponents(ts), 2)

    def test_none_when_no_seats(self):
        self.assertIsNone(count_opponents({}))


if __name__ == '__main__':
    unittest.main()
