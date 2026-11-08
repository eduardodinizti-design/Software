"""End-to-end glue: advise_table gates street/hero and calls the advisor.

The individual readers are tested elsewhere; here they are mocked so the glue is
checked without OCR."""
import unittest
from unittest.mock import patch
import numpy as np

import table_advisor


class FakeAdvisor:
    def advise_from_reading(self, state, hero, **kw):
        return dict(status='ADVICE', recommended='raise', mix=[{'action': 'raise', 'frequency': 1.0}],
                    stack_bucket=25, node_id='n1', caveats=[], execution_allowed=False)


def _patch(hero, board_cards):
    return [
        patch('table_advisor.read_table_state', return_value=dict(
            positions={'hero': 'BTN'}, seats={'hero': {'stack_bb': 25.0, 'occupied': True}},
            pot={'pot_bb': 2.5}, to_call={'to_call_bb': 1.0}, dealer={'seat': 'bot_left'})),
        patch('table_advisor.read_hand_id', return_value=dict(hand_number=10)),
        patch('table_advisor.read_board', return_value=dict(cards=board_cards)),
        patch('table_advisor.read_hero_cards', return_value=hero),
        patch('table_advisor.read_tournament', return_value=dict(paid=20, players_left=55, confidence='high')),
    ]


class AdviseTableTests(unittest.TestCase):
    crop = np.zeros((1334, 750, 3), np.uint8)

    def _run(self, hero, board_cards):
        patches = _patch(hero, board_cards)
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        return table_advisor.advise_table(self.crop, FakeAdvisor())

    def test_preflop_with_hero_gets_advice(self):
        r = self._run(['As', 'Ks'], [])
        self.assertEqual(r['advice']['status'], 'ADVICE')
        self.assertIn('SPOT_INFERRED_FROM_BETS', r['advice']['caveats'])
        self.assertFalse(r['advice']['execution_allowed'])

    def test_postflop_abstains(self):
        r = self._run(['As', 'Ks'], ['Kh', 'Qd', '2c'])
        self.assertEqual(r['advice']['reason'], 'POSTFLOP_NOT_COVERED')

    def test_no_hero_cards_abstains(self):
        r = self._run(None, [])
        self.assertEqual(r['advice']['reason'], 'HERO_CARDS_UNKNOWN')

    def test_lobby_crop_is_skipped(self):
        patches = [
            patch('table_advisor.read_table_state', return_value=dict(
                positions={}, seats={'hero': {'stack_bb': None, 'occupied': True}},
                pot={'pot_bb': None}, to_call={'to_call_bb': None}, dealer={'seat': None})),
            patch('table_advisor.read_hand_id', return_value=dict(hand_number=None)),
            patch('table_advisor.read_board', return_value=dict(cards=[])),
            patch('table_advisor.read_hero_cards', return_value=None),
            patch('table_advisor.read_tournament', return_value=dict(paid=None, players_left=None, confidence='abstain')),
        ]
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        r = table_advisor.advise_table(self.crop, FakeAdvisor())
        self.assertFalse(r['is_table'])
        self.assertEqual(r['advice']['status'], 'SKIP')


if __name__ == '__main__':
    unittest.main()
