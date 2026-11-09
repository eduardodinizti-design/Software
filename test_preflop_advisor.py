"""PreflopAdvisor: stack bucketing, context lookup, out-of-range, abstention.

Uses a tiny synthetic pack so it runs without the reference file; the real pack
is consulted live, not committed."""
import unittest

from preflop_study import RANKS
from preflop_advisor import PreflopAdvisor, infer_live_spot

HANDS = [r + r for r in RANKS] + [a + b + s for i, a in enumerate(RANKS) for b in RANKS[i + 1:] for s in ('s', 'o')]


def pack_with_node(out_of_range=()):
    idx_aa = HANDS.index('AA')
    freq = {'raise': [1.0 if k == idx_aa else 0.0 for k in range(169)],
            'fold': [0.0 if k == idx_aa else 1.0 for k in range(169)]}
    ev = {'raise': [2.0 if k == idx_aa else 0.0 for k in range(169)], 'fold': [0.0] * 169}
    node = dict(id='n1', context=dict(mode='chip_ev', format='regular', stage='mid', players=9, stack=25),
                spot='open_raise', hero='BTN', vs=[], validated=True, evUnit='bb',
                legalActions=['fold', 'raise'], actions=['raise', 'fold'], freq=freq, ev=ev,
                outOfRange=list(out_of_range), source='test')
    return dict(format='nvt-range-export', version=1, engineCommit='test', hands=HANDS, nodes=[node])


class AdvisorTests(unittest.TestCase):
    def setUp(self):
        self.a = PreflopAdvisor(pack_with_node())

    def test_bucket_stack(self):
        self.assertEqual(self.a.bucket_stack(20.8)[0], 20)
        self.assertEqual(self.a.bucket_stack(26)[0], 25)
        self.assertEqual(self.a.bucket_stack(65)[0], 40)        # deep bucket now exists
        self.assertEqual(self.a.bucket_stack(90)[0], 100)
        self.assertEqual(self.a.bucket_stack(150), (100, 'OK'))   # HRC caps at 100bb; deeper uses it
        self.assertEqual(self.a.bucket_stack(200), (100, 'OK'))
        self.assertEqual(self.a.bucket_stack(0), (None, 'STACK_UNKNOWN'))

    def test_advice_for_covered_hand(self):
        r = self.a.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=25)
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['recommended'], 'raise')
        self.assertEqual(r['mix'], [{'action': 'raise', 'frequency': 1.0}])
        self.assertFalse(r['execution_allowed'])
        self.assertIn('EXPLORATORY_NOT_FOR_EXECUTION', r['caveats'])

    def test_bucketing_is_flagged(self):
        r = self.a.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=24)
        self.assertEqual(r['stack_bucket'], 25)
        self.assertTrue(r['bucketed'])
        self.assertIn('STACK_BUCKETED_24_TO_25BB', r['caveats'])

    def test_above_solved_depth_uses_100bb_reference(self):
        # HRC tops out at 100bb; a deeper stack (common early in tournaments) uses
        # the 100bb range as a flagged reference instead of abstaining.
        idx_aa = HANDS.index('AA')
        node100 = dict(id='n100', context=dict(mode='chip_ev', format='regular', stage='mid', players=9, stack=100),
                       spot='open_raise', hero='BTN', vs=[], validated=True, evUnit='bb',
                       legalActions=['fold', 'raise'], actions=['raise', 'fold'],
                       freq={'raise': [1.0 if k == idx_aa else 0.0 for k in range(169)],
                             'fold': [0.0 if k == idx_aa else 1.0 for k in range(169)]},
                       ev={'raise': [2.0] * 169, 'fold': [0.0] * 169}, outOfRange=[], source='test')
        pack = pack_with_node()
        pack['nodes'].append(node100)
        a = PreflopAdvisor(pack)
        r = a.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=200)
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['stack_bucket'], 100)
        self.assertIn('STACK_ABOVE_SOLVED_DEPTH_100BB_REFERENCE', r['caveats'])

    def test_unknown_context_abstains(self):
        r = self.a.advise(hero_cards=['As', 'Ac'], hero_position='UTG', stack_bb=25)  # no UTG node
        self.assertEqual((r['status'], r['reason']), ('ABSTAIN', 'NO_VALIDATED_NODE_FOR_CONTEXT'))

    def test_out_of_range_hand(self):
        idx = HANDS.index('AA')
        a = PreflopAdvisor(pack_with_node(out_of_range=(idx,)))
        r = a.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=25)
        self.assertEqual(r['status'], 'OUT_OF_RANGE')

    def test_invalid_cards_abstain(self):
        r = self.a.advise(hero_cards=['As', 'As'], hero_position='BTN', stack_bb=25)
        self.assertEqual(r['status'], 'ABSTAIN')

    def test_advise_from_reading_pulls_position_and_stack(self):
        table_state = dict(positions={'hero': 'BTN'}, seats={'hero': {'stack_bb': 25.0}})
        r = self.a.advise_from_reading(table_state, ['As', 'Ac'])
        self.assertEqual((r['status'], r['recommended']), ('ADVICE', 'raise'))

    def test_advise_from_reading_without_position_abstains(self):
        r = self.a.advise_from_reading(dict(positions={}, seats={}), ['As', 'Ac'])
        self.assertEqual(r['reason'], 'HERO_POSITION_UNKNOWN')


def pack_with_shove():
    idx = HANDS.index('AA')
    freq = {'all_in': [1.0 if k == idx else 0.0 for k in range(169)],
            'fold': [0.0 if k == idx else 1.0 for k in range(169)]}
    node = dict(id='s1', context=dict(mode='chip_ev', format='regular', stage='mid', players=9, stack=10),
                spot='open_shove', hero='BTN', vs=[], validated=True, evUnit='bb',
                legalActions=['fold', 'all_in'], actions=['all_in', 'fold'], freq=freq,
                ev={'all_in': [1.0] * 169, 'fold': [0.0] * 169}, outOfRange=[], source='test')
    return dict(format='nvt-range-export', version=1, engineCommit='test', hands=HANDS, nodes=[node])


class FirstInTests(unittest.TestCase):
    def test_prefers_open_raise_when_present(self):
        r = PreflopAdvisor(pack_with_node()).advise_first_in(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=25)
        self.assertEqual(r['recommended'], 'raise')

    def test_falls_back_to_open_shove(self):
        r = PreflopAdvisor(pack_with_shove()).advise_first_in(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=10)
        self.assertEqual((r['status'], r['recommended']), ('ADVICE', 'all_in'))

    def test_abstains_when_no_first_in_node(self):
        r = PreflopAdvisor(pack_with_node()).advise_first_in(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=10)
        self.assertEqual(r['status'], 'ABSTAIN')  # pack only has open_raise at 25


def pack_with_reference():
    idx = HANDS.index('AA')
    freq = {'raise': [1.0 if k == idx else 0.0 for k in range(169)],
            'fold': [0.0 if k == idx else 1.0 for k in range(169)]}
    node = dict(id='d1', context=dict(mode='chip_ev', format='regular', stage='mid', players=9, stack=100),
                spot='open_raise', hero='BTN', vs=[], validated=False, evUnit='bb',
                legalActions=['fold', 'raise'], actions=['raise', 'fold'], freq=freq, ev=None,
                outOfRange=[], source='reference')
    return dict(format='nvt-range-export', version=1, engineCommit='deep', hands=HANDS, nodes=[node])


class ReferenceTests(unittest.TestCase):
    def test_unvalidated_deep_node_is_flagged(self):
        r = PreflopAdvisor(pack_with_reference()).advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=100)
        self.assertEqual(r['status'], 'ADVICE')
        self.assertFalse(r['validated'])
        self.assertIn('UNVALIDATED_REFERENCE_RANGE', r['caveats'])

    def test_from_files_merges_validated_and_reference(self):
        import json
        import os
        import tempfile
        d = tempfile.mkdtemp()
        p1, p2 = os.path.join(d, 'a.json'), os.path.join(d, 'b.json')
        json.dump(pack_with_node(), open(p1, 'w'))        # validated BTN 25
        json.dump(pack_with_reference(), open(p2, 'w'))   # reference BTN 100
        a = PreflopAdvisor.from_files(p1, p2)
        self.assertTrue(a.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=25)['validated'])
        self.assertFalse(a.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=100)['validated'])


def pack_with_vsopen():
    idx = HANDS.index('AA')
    freq = {'call': [1.0 if k == idx else 0.0 for k in range(169)],
            'fold': [0.0 if k == idx else 1.0 for k in range(169)]}
    node = dict(id='v1', context=dict(mode='chip_ev', format='regular', stage='mid', players=9, stack=25),
                spot='vs_open', hero='BB', vs=['BTN'], validated=True, evUnit='bb',
                legalActions=['fold', 'call'], actions=['call', 'fold'], freq=freq,
                ev={'call': [1.0] * 169, 'fold': [0.0] * 169}, outOfRange=[], source='test')
    return dict(format='nvt-range-export', version=1, engineCommit='test', hands=HANDS, nodes=[node])


class SpotInferenceTests(unittest.TestCase):
    def _state(self, bets):
        return dict(positions={'hero': 'BB', 'x': 'BTN', 'y': 'CO'}, bets=bets,
                    seats={'hero': {'stack_bb': 25.0}})

    def test_no_raiser_is_first_in(self):
        self.assertEqual(infer_live_spot(self._state([{'seat': 'x', 'bet_bb': 1.0}]))['spot'], 'first_in')

    def test_one_raiser_is_vs_open(self):
        s = infer_live_spot(self._state([{'seat': 'x', 'bet_bb': 2.5}]))
        self.assertEqual((s['spot'], s['opener']), ('vs_open', 'BTN'))

    def test_two_distinct_levels_abstain(self):
        # An open (2.5) and a reraise (7.0): two levels -> a 3bet pot the hero
        # faces cold, which the pack does not cover.
        s = infer_live_spot(self._state([{'seat': 'x', 'bet_bb': 2.5}, {'seat': 'y', 'bet_bb': 7.0}]))
        self.assertEqual((s['spot'], s['reason']), ('abstain', 'MULTIWAY_OR_3BET_NOT_COVERED'))

    def test_open_with_caller_is_vs_open_against_the_opener(self):
        # Open (BTN 2.5) plus a caller at the same level (CO 2.5): one raise level,
        # so it is vs_open; the opener is the earliest-position seat at that level.
        s = infer_live_spot(self._state([{'seat': 'x', 'bet_bb': 2.5}, {'seat': 'y', 'bet_bb': 2.6}]))
        self.assertEqual((s['spot'], s['opener'], s['callers']), ('vs_open', 'CO', 1))

    def test_multiway_caller_is_flagged_in_advice(self):
        a = PreflopAdvisor(pack_with_vsopen())
        state = dict(positions={'hero': 'BB', 'x': 'BTN', 'z': 'SB'},
                     bets=[{'seat': 'x', 'bet_bb': 2.5}, {'seat': 'z', 'bet_bb': 2.5}],
                     seats={'hero': {'stack_bb': 25.0}})
        r = a.advise_from_reading(state, ['As', 'Ac'])
        self.assertEqual((r['status'], r['spot']), ('ADVICE', 'vs_open'))
        self.assertIn('MULTIWAY_1_CALLERS_APPROX_VS_OPEN', r['caveats'])

    def test_hero_opened_facing_3bet_is_vs_3bet(self):
        state = dict(positions={'hero': 'CO', 'x': 'BTN'},
                     bets=[{'seat': 'hero', 'bet_bb': 2.2}, {'seat': 'x', 'bet_bb': 7.0}])
        s = infer_live_spot(state)
        self.assertEqual((s['spot'], s['opener']), ('vs_3bet', 'BTN'))

    def test_hero_opened_no_reraise_abstains(self):
        s = infer_live_spot(dict(positions={'hero': 'CO'}, bets=[{'seat': 'hero', 'bet_bb': 2.2}]))
        self.assertEqual((s['spot'], s['reason']), ('abstain', 'HERO_OPENED_NO_RERAISE'))

    def test_from_reading_routes_to_vs_open(self):
        a = PreflopAdvisor(pack_with_vsopen())
        state = dict(positions={'hero': 'BB', 'x': 'BTN'}, bets=[{'seat': 'x', 'bet_bb': 2.5}],
                     seats={'hero': {'stack_bb': 25.0}})
        r = a.advise_from_reading(state, ['As', 'Ac'])
        self.assertEqual((r['status'], r['spot'], r['recommended']), ('ADVICE', 'vs_open', 'call'))
        self.assertIn('AGGRESSOR_INFERRED_BTN', r['caveats'])


if __name__ == '__main__':
    unittest.main()
