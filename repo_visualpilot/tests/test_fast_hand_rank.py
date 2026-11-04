import random
import unittest
from visualpilot.lab.hand_rank import rank_hand
from visualpilot.lab.postflop import DECK,rank7


class FastHandRankTests(unittest.TestCase):
    def test_random_parity_against_independent_combinations(self):
        rng=random.Random(20261029)
        for length in (5,6,7):
            for _ in range(1000):
                cards=rng.sample(DECK,length)
                self.assertEqual(rank_hand(cards),rank7(cards),cards)

    def test_two_trips_three_pairs_wheel_and_flush(self):
        for text in ('As Ah Ad Ks Kh Kd 2c','As Ah Ks Kh Qs Qh 2c',
                     'As 2s 3s 4s 5s Kd Qd','As Ks Js 9s 7s 3s 2s',
                     'As Ah Ad Ac Ks Kh Kd'):
            cards=text.split()
            self.assertEqual(rank_hand(cards),rank7(cards))

    def test_order_invariance_and_invalid_lengths(self):
        cards='As Ah Ks Kh Qs Qh 2c'.split()
        self.assertEqual(rank_hand(cards),rank_hand(list(reversed(cards))))
        with self.assertRaises(ValueError): rank_hand(cards[:4])
