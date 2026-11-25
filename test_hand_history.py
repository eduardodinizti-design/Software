"""Testes do parser/replay de histórico de mãos (.txt PPPoker)."""
import os
import unittest

from hand_history import parse_hand_histories

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'pppoker_sample.txt')


def _sample():
    with open(_FIX, encoding='utf-8') as f:
        return f.read()


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.hands = parse_hand_histories(_sample(), 'Hero')

    def test_counts_five_hands(self):
        self.assertEqual(len(self.hands), 5)

    def test_header_blinds_and_hero_cards(self):
        h0 = self.hands[0]
        self.assertEqual(h0.id, '#9841201')
        self.assertEqual(h0.bb, 200.0)
        self.assertEqual(h0.sb, 100.0)
        self.assertEqual(h0.ante, 25.0)
        self.assertEqual(h0.hero_cards, ['Kh', '9d'])
        self.assertEqual(h0.board, ['Qc', '7s', '2d'])

    def test_hero_cards_from_showdown_fallback(self):
        # A última mão não tem linha 'Dealt to'; as cartas vêm de 'Hero: shows'.
        last = self.hands[4]
        self.assertEqual(last.id, '#9841247')
        self.assertEqual(last.hero_cards, ['Ks', '7s'])
        self.assertEqual(len(last.board), 5)

    def test_decision_normalized_to_bb(self):
        d0 = self.hands[0].hero_decisions[0]
        self.assertEqual(d0['street'], 'FLOP')
        self.assertEqual(d0['hero_action'], 'bet')
        self.assertEqual(d0['to_call_bb'], 0.0)
        self.assertAlmostEqual(d0['pot_bb'], 12.4, delta=0.3)   # 2480 fichas / 200
        self.assertEqual(d0['pot_type'], 'multiway')
        self.assertEqual(d0['opponents'], 3)
        self.assertEqual(d0['aggressor'], 'hero')

    def test_passive_turned_aggressive_detected_on_checkraise_river(self):
        # #9841247: vilão deu check no turn e aposta no river -> passivo->agressivo.
        river_calls = [d for d in self.hands[4].hero_decisions
                       if d['street'] == 'RIVER' and d['hero_action'] == 'call']
        self.assertTrue(river_calls)
        self.assertEqual(river_calls[0]['villain_line'], 'passive_turned_aggressive')

    def test_robust_to_garbage(self):
        self.assertEqual(parse_hand_histories('', 'Hero'), [])
        self.assertEqual(parse_hand_histories('linha solta sem cabeçalho', 'Hero'), [])


if __name__ == '__main__':
    unittest.main()
