"""Founded raise-sizing heuristics."""
import unittest

import sizing


class RecommendSizeTests(unittest.TestCase):
    def test_open_and_iso(self):
        self.assertEqual(sizing.recommend_size('raise', hero_stack_bb=40)['size_bb'], 2.2)
        self.assertEqual(sizing.recommend_size('raise', hero_stack_bb=40, limpers=2)['size_bb'], 4.2)
        self.assertTrue(sizing.recommend_size('raise', hero_stack_bb=40)['heuristic'])

    def test_three_bet_ip_vs_oop(self):
        self.assertEqual(sizing.recommend_size('three_bet', hero_stack_bb=100, opener_bb=2.5, ip=True)['size_bb'], 7.5)
        self.assertEqual(sizing.recommend_size('three_bet', hero_stack_bb=100, opener_bb=2.5, ip=False)['size_bb'], 10.0)

    def test_exact_actions(self):
        self.assertEqual(sizing.recommend_size('all_in', hero_stack_bb=12)['size_bb'], 12)
        self.assertEqual(sizing.recommend_size('call', to_call_bb=3.0)['size_bb'], 3.0)
        self.assertEqual(sizing.recommend_size('limp', hero_stack_bb=40)['size_bb'], 1.0)
        self.assertIsNone(sizing.recommend_size('fold'))

    def test_size_capped_by_stack(self):
        self.assertEqual(sizing.recommend_size('raise', hero_stack_bb=3, limpers=2)['size_bb'], 3)   # 4.2 capped to 3

    def test_in_position(self):
        self.assertTrue(sizing.in_position('BTN', 'UTG'))
        self.assertFalse(sizing.in_position('SB', 'CO'))


class ReadingTests(unittest.TestCase):
    def test_count_limpers_excludes_blinds_and_hero(self):
        state = dict(positions={'hero': 'BTN', 'a': 'UTG', 'b': 'BB', 'c': 'SB'},
                     bets=[{'seat': 'a', 'bet_bb': 1.0}, {'seat': 'b', 'bet_bb': 1.0},
                           {'seat': 'c', 'bet_bb': 0.5}, {'seat': 'hero', 'bet_bb': 1.0}])
        self.assertEqual(sizing.count_limpers(state), 1)   # only UTG limped

    def test_opener_raise_detected(self):
        state = dict(bets=[{'seat': 'x', 'bet_bb': 2.5}, {'seat': 'y', 'bet_bb': 1.0}])
        self.assertEqual(sizing.opener_raise_bb(state), 2.5)

    def test_size_from_reading_open(self):
        state = dict(positions={'hero': 'CO'}, bets=[], seats={'hero': {'stack_bb': 25.0}},
                     to_call={'to_call_bb': None})
        s = sizing.size_from_reading('raise', state, 'CO')
        self.assertEqual(s['size_bb'], 2.2)


if __name__ == '__main__':
    unittest.main()
