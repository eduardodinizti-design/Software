"""TRAVA do adaptador de rede da SUPREMA (Fase 1b, offline): alimenta o SupremaTable com
MENSAGENS JSON REAIS (schema capturado ao vivo 20/11, ver SUPREMA_PROTOCOL.md) e exige
table_state correto + decisão do MESMO cérebro. Sem cliente aberto, sem clique."""
import os
import unittest

from suprema_state import (SupremaTable, advise_from_suprema, decode_card, decode_cards,
                           parse_raise_range, parse_prompt)

PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


class Decode(unittest.TestCase):
    def test_card_rank_suit(self):
        # rank*4+suit: 59=A(14,3), 56=A(14,0), 40=T(10,0), 23=5(5,3), 44=J(11,0), 36=9(9,0)
        self.assertEqual(decode_card(59)[0], 'A')
        self.assertEqual(decode_card(56)[0], 'A')
        self.assertEqual(decode_card(40)[0], 'T')
        self.assertEqual(decode_card(44)[0], 'J')
        self.assertEqual(decode_card(36)[0], '9')
        # naipe é bijetivo: 59 e 56 são ambos A mas de naipes DIFERENTES
        self.assertNotEqual(decode_card(59)[1], decode_card(56)[1])

    def test_hidden_cards(self):
        self.assertIsNone(decode_card(0))
        self.assertEqual(decode_cards([0, 0]), [])
        self.assertEqual(decode_cards(None), [])
        self.assertEqual(decode_cards([40, 23]), ['Td', '5s'])

    def test_parse_raise_range(self):
        r = parse_raise_range('range,4000,27900,2X,4000,3X,8000,4X,12000')
        self.assertEqual(r['min'], 4000.0)
        self.assertEqual(r['max'], 27900.0)
        self.assertEqual(r['presets']['2X'], 4000.0)
        self.assertEqual(r['presets']['4X'], 12000.0)
        self.assertIsNone(parse_raise_range(None))

    def test_parse_prompt_active(self):
        # prompt REAL capturado na vez do herói
        gp = {"fold": True, "check": True, "call": None,
              "raise": "range,4000,27900,2X,4000,3X,8000,4X,12000",
              "all_in": True, "ready": None, "bet": None}
        p = parse_prompt(gp)
        self.assertEqual(p['actions'], {'fold', 'check', 'raise', 'all_in'})
        self.assertIsNotNone(p['raise_range'])
        self.assertIsNone(p['call_amount'])

    def test_parse_prompt_idle(self):
        gp = {"fold": None, "check": None, "call": None, "raise": None,
              "all_in": None, "ready": None, "bet": None}
        self.assertEqual(parse_prompt(gp)['actions'], set())


def _preflop_AA_btn(bb_chips=500):
    """Pré-flop 3-handed (schema REAL): herói seat2=dealer(BTN) com AA=[59,56]; SB=seat3,
    BB=seat6. Devolve SupremaTable alimentado por gameinfo + moveturn reais."""
    t = SupremaTable(bb_chips=bb_chips)
    t.feed_json({"route": "onMsg", "event": "gameinfo",
                 "data": {"game_info": {"gamers_count": 3, "dealer_seat": 2,
                                        "shared_cards": [], "pot": 750, "state": 3}}})
    t.feed_json({"route": "onMsg", "event": "moveturn", "data": {"game_seat": {
        "1754193": {"seat": 2, "uid": 1754193, "coins": 10000, "cards": [59, 56], "chips": 0, "sitout": False, "role": 0},
        "388769":  {"seat": 3, "uid": 388769, "coins": 9000, "cards": None, "chips": 250, "sitout": False, "role": 0},
        "295455":  {"seat": 6, "uid": 295455, "coins": 12000, "cards": [0, 0], "chips": 500, "sitout": False, "role": 40},
    }}})
    return t


class SupremaPerception(unittest.TestCase):

    def test_table_state_preflop(self):
        t = _preflop_AA_btn()
        state, hero = t.to_table_state()
        self.assertIsNotNone(state, 'abstido: %r' % (hero,))
        self.assertEqual(hero, ['As', 'Ad'])                     # [59,56] = A + A (naipes diff)
        self.assertEqual(state['positions']['hero'], 'BTN')      # dealer=2=herói
        self.assertEqual(set(state['positions'].values()), {'BTN', 'SB', 'BB'})
        self.assertAlmostEqual(state['seats']['hero']['stack_bb'], 20.0)   # 10000/500
        self.assertEqual(state['street'], 'PREFLOP')
        self.assertAlmostEqual(state['to_call']['to_call_bb'], 1.0)        # BB=500=1bb, hero 0
        self.assertEqual(state['source'], 'suprema')

    def test_board_decode_flop(self):
        t = _preflop_AA_btn()
        t.feed_json({"route": "onMsg", "event": "gameinfo",
                     "data": {"game_info": {"dealer_seat": 2, "shared_cards": [36, 59, 39],
                                            "pot": 3000, "state": 4}}})
        state, _ = t.to_table_state()
        self.assertEqual(state['street'], 'FLOP')
        self.assertEqual(state['board'], ['9d', 'As', '9s'])     # 36=9d,59=As,39=9s
        self.assertAlmostEqual(state['pot']['pot_bb'], 6.0)      # 3000/500

    def test_legal_actions_from_prompt(self):
        t = _preflop_AA_btn()
        t.feed_json({"event": "prompt", "data": {"gamer_prompt": {
            "fold": True, "check": None, "call": 500, "raise": "range,1000,10000,2X,1000",
            "all_in": True, "ready": None, "bet": None}}})
        self.assertEqual(t.legal_actions(), {'fold', 'call', 'raise', 'all_in'})
        state, _ = t.to_table_state()
        self.assertEqual(set(state['legal_actions']), {'fold', 'call', 'raise', 'all_in'})
        self.assertAlmostEqual(state['to_call']['to_call_bb'], 1.0)   # call=500 do prompt / 500

    def test_abstem_sem_bb(self):
        t = SupremaTable(bb_chips=None)
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "1": {"seat": 2, "coins": 10000, "cards": [59, 56], "chips": 0, "sitout": False}}}})
        state, reason = t.to_table_state()
        self.assertIsNone(state)
        self.assertEqual(reason, 'BB_DESCONHECIDO')

    def test_abstem_sem_heroi(self):
        t = SupremaTable(bb_chips=500)
        t.feed_json({"event": "gameinfo", "data": {"game_info": {"dealer_seat": 2, "shared_cards": []}}})
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "2": {"seat": 2, "coins": 10000, "cards": None, "chips": 0, "sitout": False},
            "3": {"seat": 3, "coins": 9000, "cards": None, "chips": 500, "sitout": False}}}})
        state, reason = t.to_table_state()
        self.assertIsNone(state)
        self.assertEqual(reason, 'HERO_CARDS_UNKNOWN')

    @unittest.skipUnless(os.path.exists(PACK), 'pack validado ausente')
    def test_cerebro_decide_AA(self):
        from preflop_advisor import PreflopAdvisor
        adv = (PreflopAdvisor.from_files(PACK, DEEP) if os.path.exists(DEEP)
               else PreflopAdvisor.from_file(PACK))
        r = advise_from_suprema(_preflop_AA_btn(), adv, mode='chip_ev', stage='mid')
        self.assertEqual(r.get('status'), 'ADVICE')
        self.assertIn(r.get('recommended'), ('raise', 'all_in', 'bets'))   # AA nunca folda


if __name__ == '__main__':
    unittest.main()
