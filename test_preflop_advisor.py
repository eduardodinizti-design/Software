"""PreflopAdvisor: stack bucketing, context lookup, out-of-range, abstention.

Uses a tiny synthetic pack so it runs without the reference file; the real pack
is consulted live, not committed."""
import unittest

from preflop_study import RANKS
from preflop_advisor import (PreflopAdvisor, infer_live_spot, infer_spread,
                             _icm_risk_premium)

HANDS = [r + r for r in RANKS] + [a + b + s for i, a in enumerate(RANKS) for b in RANKS[i + 1:] for s in ('s', 'o')]


def shove_pack(spot, yes_hands, hero, vs, stack, yes_action):
    """Pack com um nó de shove genérico (3bet_shove/open_shove => all_in;
    vs_open_shove => call), com `yes_action` para as mãos em `yes_hands`."""
    idx = set(yes_hands)
    yes = [1.0 if HANDS[k] in idx else 0.0 for k in range(169)]
    fold = [0.0 if HANDS[k] in idx else 1.0 for k in range(169)]
    node = dict(id=spot + '1', context=dict(mode='chip_ev', format='regular', stage='mid', players=9, stack=stack),
                spot=spot, hero=hero, vs=list(vs), validated=True, evUnit='bb',
                legalActions=['fold', yes_action], actions=[yes_action, 'fold'],
                freq={yes_action: yes, 'fold': fold}, ev={yes_action: [0.0] * 169, 'fold': [0.0] * 169},
                outOfRange=[], source='test')
    return dict(format='nvt-range-export', version=1, engineCommit='test', hands=HANDS, nodes=[node])


def pack_with_3bet_shove(shove_hands, hero='BTN', vs=('CO',), stack=15, extra_nodes=()):
    """Pack com `3bet_shove` (range do re-shove do vilão) e nada de vs_3bet."""
    p = shove_pack('3bet_shove', shove_hands, hero, vs, stack, 'all_in')
    p['nodes'] += list(extra_nodes)
    return p


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


class CallOffTests(unittest.TestCase):
    """Síntese do call-off do abridor vs re-shove quando falta o nó vs_3bet curto."""

    def test_calloff_folds_vs_narrow_shove_bad_odds(self):
        a = PreflopAdvisor(pack_with_3bet_shove(['AA'], hero='BTN', vs=('CO',), stack=15))
        # A7o enfrenta re-shove do BTN que só shova AA; pot odds ruins -> fold
        r = a.advise_call_off(hero_cards=['Ah', '7d'], hero_position='CO',
                              villain_position='BTN', stack_bb=15, to_call_bb=12, pot_bb=18)
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['recommended'], 'fold')
        self.assertLess(r['equity'], r['required_equity'])
        self.assertIn('CALLOFF_SYNTH_VS_3BET_SHOVE', r['caveats'])
        self.assertFalse(r['execution_allowed'])

    def test_calloff_calls_vs_wide_shove_good_odds(self):
        wide = list(HANDS)                                   # vilão shova qualquer duas
        a = PreflopAdvisor(pack_with_3bet_shove(wide, hero='BTN', vs=('CO',), stack=15))
        r = a.advise_call_off(hero_cards=['Ah', '7d'], hero_position='CO',
                              villain_position='BTN', stack_bb=15, to_call_bb=2, pot_bb=20)
        self.assertEqual(r['recommended'], 'call')
        self.assertGreaterEqual(r['equity'], r['required_equity'])

    def test_calloff_abstains_without_shove_range(self):
        a = PreflopAdvisor(pack_with_3bet_shove(['AA'], hero='BTN', vs=('CO',), stack=15))
        r = a.advise_call_off(hero_cards=['Ah', '7d'], hero_position='UTG',
                              villain_position='LJ', stack_bb=15, to_call_bb=12, pot_bb=18)
        self.assertEqual(r['status'], 'ABSTAIN')
        self.assertEqual(r['reason'], 'NO_SHOVE_RANGE_FOR_CONTEXT')

    def test_calloff_abstains_without_pot_odds(self):
        a = PreflopAdvisor(pack_with_3bet_shove(['AA'], hero='BTN', vs=('CO',), stack=15))
        r = a.advise_call_off(hero_cards=['Ah', '7d'], hero_position='CO',
                              villain_position='BTN', stack_bb=15, to_call_bb=None, pot_bb=18)
        self.assertEqual(r['reason'], 'CANNOT_COMPUTE_POT_ODDS')

    def test_from_reading_synthesizes_calloff_instead_of_freezing(self):
        # A7 abriu (CO, 2bb), BTN re-shova 15bb: sem nó vs_3bet -> antes abstinha
        # (NO_VALIDATED_NODE); agora sintetiza um call-off e DECIDE.
        a = PreflopAdvisor(pack_with_3bet_shove(list(HANDS), hero='BTN', vs=('CO',), stack=15))
        state = dict(positions={'hero': 'CO', 's2': 'BTN'},
                     seats={'hero': dict(stack_bb=15, occupied=True),
                            's2': dict(stack_bb=0, occupied=True)},
                     bets=[dict(seat='hero', bet_bb=2.0), dict(seat='s2', bet_bb=15.0)],
                     to_call=dict(to_call_bb=13.0), pot=dict(pot_bb=18.0))
        r = a.advise_from_reading(state, ['Ah', '7d'])
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['spot'], 'call_off_vs_3bet_shove')
        self.assertIn(r['recommended'], ('call', 'fold'))
        self.assertIn('AGGRESSOR_INFERRED_BTN', r['caveats'])


class IcmRiskPremiumTests(unittest.TestCase):
    def test_chip_ev_has_no_rp(self):
        self.assertEqual(_icm_risk_premium('chip_ev', 'mid', 10, 10), 0.0)

    def test_bubble_all_in_is_full_rp(self):
        self.assertAlmostEqual(_icm_risk_premium('icm', 'bubble', 10, 10), 0.135, places=3)

    def test_covering_scales_rp_down(self):
        # arrisca 20% do stack (cobre o shove curto) -> RP ~1/5 do da bolha
        self.assertAlmostEqual(_icm_risk_premium('icm', 'bubble', 2, 10), 0.135 * 0.2, places=3)

    def test_pko_discounts_rp(self):
        self.assertAlmostEqual(_icm_risk_premium('pko_icm', 'bubble', 10, 10), 0.135 * 0.6, places=3)

    def test_ft_and_pre_itm(self):
        self.assertAlmostEqual(_icm_risk_premium('icm', 'ft', 10, 10), 0.12, places=3)
        self.assertAlmostEqual(_icm_risk_premium('icm', 'pre_itm', 10, 10), 0.09, places=3)


class CallOffIcmTests(unittest.TestCase):
    """O risk premium de ICM aperta o call-off: mão que paga em chip EV folda na bolha."""

    def _adv(self, mode, stage):
        a = PreflopAdvisor(pack_with_3bet_shove(['AA', 'KK', 'QQ'], hero='BTN', vs=('CO',), stack=15))
        return a.advise_call_off(hero_cards=['7h', '2d'], hero_position='CO',
                                 villain_position='BTN', stack_bb=15, to_call_bb=15, pot_bb=135,
                                 mode=mode, stage=stage)                      # pot odds = 0.10

    def test_chip_ev_calls_icm_bubble_folds(self):
        ce = self._adv('chip_ev', 'mid')
        icm = self._adv('icm', 'bubble')
        self.assertEqual(ce['recommended'], 'call')          # eq (~0.12) >= pot odds 0.10
        self.assertEqual(ce['required_equity_icm'], ce['required_equity'])   # RP 0
        self.assertEqual(icm['recommended'], 'fold')         # eq < 0.10 + 0.135
        self.assertGreater(icm['required_equity_icm'], icm['required_equity'])
        self.assertAlmostEqual(icm['risk_premium'], 0.135, places=3)
        self.assertTrue(any(c.startswith('ICM_RP_APPROX_BY_STAGE') for c in icm['caveats']))


class VsOpenShoveTests(unittest.TestCase):
    """Enfrentar um OPEN-SHOVE (jam de 1ª aposta): roteia p/ o nó validado
    `vs_open_shove` (5-15bb); mais fundo que isso, fallback por equity."""

    def _state(self, villain_remaining, villain_bet, hero_stack=10):
        return dict(positions={'hero': 'BB', 's2': 'SB'},
                    seats={'hero': dict(stack_bb=hero_stack, occupied=True),
                           's2': dict(stack_bb=villain_remaining, occupied=True)},
                    bets=[dict(seat='s2', bet_bb=villain_bet)],
                    to_call=dict(to_call_bb=villain_bet - 1), pot=dict(pot_bb=villain_bet + 1.5))

    def test_infer_classifies_open_shove(self):
        spot = infer_live_spot(self._state(villain_remaining=0, villain_bet=10.0))
        self.assertEqual(spot['spot'], 'vs_open_shove')
        self.assertEqual(spot['opener'], 'SB')

    def test_infer_keeps_normal_open_as_vs_open(self):
        spot = infer_live_spot(self._state(villain_remaining=20, villain_bet=2.0))
        self.assertEqual(spot['spot'], 'vs_open')

    def test_infer_shove_by_size_when_stack_unreadable(self):
        st = self._state(villain_remaining=None, villain_bet=9.0)
        self.assertEqual(infer_live_spot(st)['spot'], 'vs_open_shove')

    def test_uses_validated_node_when_covered(self):
        a = PreflopAdvisor(shove_pack('vs_open_shove', ['AA', 'KK'], 'BB', ('SB',), 10, 'call'))
        r = a.advise_from_reading(self._state(0, 10.0, hero_stack=10), ['As', 'Ac'])
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['spot'], 'vs_open_shove')      # nó validado, não call-off
        self.assertEqual(r['recommended'], 'call')
        self.assertTrue(r['validated'])

    def test_validated_node_folds_trash(self):
        a = PreflopAdvisor(shove_pack('vs_open_shove', ['AA', 'KK'], 'BB', ('SB',), 10, 'call'))
        r = a.advise_from_reading(self._state(0, 10.0, hero_stack=10), ['7h', '2d'])
        self.assertEqual(r['recommended'], 'fold')

    def test_equity_fallback_when_no_validated_node(self):
        # sem nó vs_open_shove, mas há open_shove (range do shover) -> call-off sintetizado
        a = PreflopAdvisor(shove_pack('open_shove', list(HANDS), 'SB', (), 15, 'all_in'))
        r = a.advise_from_reading(self._state(0, 15.0, hero_stack=15), ['As', 'Ac'])
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['spot'], 'call_off_vs_open_shove')
        self.assertIn('CALLOFF_SYNTH_VS_OPEN_SHOVE', r['caveats'])


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

    def test_infer_spread_classifies_the_table(self):
        even = {p: 40 for p in ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')}
        self.assertEqual(infer_spread(even), 'iguais')
        early_short = {'UTG': 12, 'UTG+1': 13, 'UTG+2': 18, 'LJ': 20, 'HJ': 25, 'CO': 32, 'BTN': 38, 'SB': 40, 'BB': 30}
        self.assertEqual(infer_spread(early_short), 'curtos_ini')
        late_short = {'UTG': 38, 'UTG+1': 40, 'UTG+2': 32, 'LJ': 30, 'HJ': 25, 'CO': 18, 'BTN': 13, 'SB': 12, 'BB': 20}
        self.assertEqual(infer_spread(late_short), 'curtos_fim')
        self.assertIsNone(infer_spread({'UTG': 40, 'BTN': 20}))   # too few seats -> keep default

    def test_from_reading_uses_inferred_spread_in_icm(self):
        # The ICM caveat reports the spread classified from the table, not a blanket assumption.
        node = dict(id='i1', context=dict(mode='icm', format='regular', stage='bubble', players=9, stack=25),
                    spot='open_raise', hero='BTN', vs=[], validated=False, evUnit='bb', spread='curtos_fim',
                    legalActions=['fold', 'raise'], actions=['raise', 'fold'],
                    freq={'raise': [1.0 if HANDS[k] == 'AA' else 0.0 for k in range(169)],
                          'fold': [0.0 if HANDS[k] == 'AA' else 1.0 for k in range(169)]},
                    ev={'raise': [2.0] * 169, 'fold': [0.0] * 169}, outOfRange=[], source='test')
        pack = pack_with_node()
        pack['nodes'].append(node)
        a = PreflopAdvisor(pack)
        # Late-short (curtos_fim) profile; hero is BTN at 25bb so the open node matches.
        by_pos = {'UTG': 58, 'UTG+1': 58, 'UTG+2': 50, 'LJ': 50, 'HJ': 42, 'CO': 33, 'BTN': 25, 'SB': 25, 'BB': 33}
        seats = {p: {'stack_bb': st} for p, st in by_pos.items()}
        seats['hero'] = {'stack_bb': 25}
        positions = {p: p for p in by_pos}
        positions['hero'] = 'BTN'
        state = dict(positions=positions, seats=seats, bets=[])
        r = a.advise_from_reading(state, ['As', 'Ac'], mode='icm', stage='bubble')
        self.assertEqual(r['status'], 'ADVICE')
        self.assertIn('ICM_SPREAD_CURTOS_FIM', r['caveats'])

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

    def test_short_table_and_limpers_are_flagged_not_abstained(self):
        a = PreflopAdvisor(pack_with_node())   # BTN open_raise 25bb node
        seats = {s: {'stack_bb': 25.0, 'occupied': True} for s in ('hero', 'a', 'b', 'c', 'd', 'e')}
        state = dict(positions={'hero': 'BTN', 'a': 'CO', 'b': 'HJ', 'c': 'LJ', 'd': 'SB', 'e': 'BB'},
                     seats=seats, bets=[{'seat': 'a', 'bet_bb': 1.0}])   # CO limped
        r = a.advise_from_reading(state, ['As', 'Ac'])                # stack comes from seats['hero']
        self.assertEqual(r['status'], 'ADVICE')                       # advises, not abstains
        self.assertIn('TABLE_6HANDED_USING_9MAX_REF', r['caveats'])
        self.assertIn('LIMPERS_PRESENT_OPEN_AS_ISO_APPROX', r['caveats'])

    def test_from_reading_routes_to_vs_open(self):
        a = PreflopAdvisor(pack_with_vsopen())
        state = dict(positions={'hero': 'BB', 'x': 'BTN'}, bets=[{'seat': 'x', 'bet_bb': 2.5}],
                     seats={'hero': {'stack_bb': 25.0}})
        r = a.advise_from_reading(state, ['As', 'Ac'])
        self.assertEqual((r['status'], r['spot'], r['recommended']), ('ADVICE', 'vs_open', 'call'))
        self.assertIn('AGGRESSOR_INFERRED_BTN', r['caveats'])


if __name__ == '__main__':
    unittest.main()
