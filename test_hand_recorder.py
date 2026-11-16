"""Testes do gravador de mãos (hand_recorder) e do estudo do banco (hand_db)."""
import os
import tempfile
import unittest

import hand_recorder as hr
import hand_db


def _hand(rec, *, hid, pos, line_actions, board_flop=None, delta, opp_id='vilaoX',
          opp_cat='reg', outcome='won', hud=None):
    h = rec.begin(hand_id=hid, table_key='t1',
                  tournament=dict(mode='chip_ev', stage='mid'),
                  hero=dict(seat='hero', position=pos, cards=['Ah', 'Kd'], stack_bb=25),
                  opponents=[dict(seat='s5', id=opp_id, position='BB', stack_bb=22,
                                  hud=hud, category=opp_cat)])
    h.action(street='preflop', actor=pos, action='raise', amount_bb=2.0, player_id='hero')
    for st, act, amt in line_actions:
        h.action(street=st, actor=pos, action=act, amount_bb=amt, player_id='hero')
    if board_flop:
        h.board('flop', board_flop)
    h.advice(street='flop', recommended='bet', source='solver_shadow', execution_allowed=False)
    h.result(outcome=outcome, delta_bb=delta)
    return rec.commit(h)


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, 'maos.jsonl')
        self.rec = hr.HandRecorder(path=self.path)

    def test_grava_e_le(self):
        _hand(self.rec, hid='#1', pos='BTN', line_actions=[('flop', 'bet', 1.8)],
              board_flop=['As', '7d', '2c'], delta=5.5)
        hands = hr.load_hands(self.path)
        self.assertEqual(len(hands), 1)
        h = hands[0]
        self.assertEqual(h['hand_id'], '#1')
        self.assertEqual(h['opponent_ids'], ['vilaoX'])
        self.assertEqual(h['reached_street'], 'flop')
        self.assertTrue(any('fl:bet' in x for x in h['hero_line']))
        self.assertFalse(h['advice_trail'][0]['execution_allowed'])  # gate

    def test_resultado_e_linha(self):
        r = _hand(self.rec, hid='#2', pos='CO', line_actions=[], delta=-2.0, outcome='folded')
        self.assertEqual(r['result']['outcome'], 'folded')
        self.assertEqual(r['result']['delta_bb'], -2.0)
        self.assertTrue(r['line_key'].startswith('CO'))


class HandDbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, 'maos.jsonl')
        self.rec = hr.HandRecorder(path=self.path)
        # 25 mãos BTN c-bet ganhando + 25 CO foldando perdendo -> linhas distintas.
        for i in range(25):
            _hand(self.rec, hid='#b%d' % i, pos='BTN', line_actions=[('flop', 'bet', 1.8)],
                  board_flop=['As', '7d', '2c'], delta=4.0, opp_id='fish1', opp_cat='fish')
        for i in range(25):
            _hand(self.rec, hid='#c%d' % i, pos='CO', line_actions=[('flop', 'check', None)],
                  delta=-3.0, opp_id='nit2', opp_cat='nit', outcome='lost')
        self.hands = hr.load_hands(self.path)

    def test_summary(self):
        s = hand_db.summary(self.hands)
        self.assertEqual(s['total_hands'], 50)
        self.assertEqual(s['adversarios_distintos'], 2)
        self.assertAlmostEqual(s['net_bb'], 25 * 4.0 + 25 * -3.0, places=1)

    def test_by_opponent(self):
        opp = hand_db.by_opponent(self.hands)
        self.assertIn('fish1', opp)
        self.assertEqual(opp['fish1']['hands'], 25)
        self.assertGreater(opp['fish1']['net_bb'], 0)
        self.assertLess(opp['nit2']['net_bb'], 0)

    def test_linhas_leak_e_lucrativa(self):
        leaks = hand_db.leaks(self.hands)
        prof = hand_db.profitable(self.hands)
        self.assertTrue(leaks, 'deveria achar a linha CO-check negativa')
        self.assertTrue(prof, 'deveria achar a linha BTN-bet positiva')
        self.assertLess(leaks[0]['avg_bb'], 0)
        self.assertGreater(prof[0]['avg_bb'], 0)
        # amostra >= MIN_SAMPLE (25) -> não marcada low_sample
        self.assertFalse(leaks[0]['low_sample'])

    def test_exploit_targets(self):
        t = hand_db.exploit_targets(self.hands)
        self.assertEqual(t['mais_lucrativos'][0]['id'], 'fish1')
        self.assertEqual(t['mais_custosos'][0]['id'], 'nit2')


if __name__ == '__main__':
    unittest.main()
