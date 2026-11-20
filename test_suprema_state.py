"""TRAVA do adaptador de percepção da SUPREMA (Fase 1, offline): alimenta o SupremaTable
com um STREAM de eventos NVT (contrato de inject_emit.js) e exige que o table_state saia
correto e que o MESMO cérebro (advise_from_reading) decida — SEM cliente aberto, SEM clique.

Prova a trilha percepção->decisão da Suprema reusando 100% do cérebro do PPPoker."""
import os
import unittest

from suprema_state import SupremaTable, advise_from_suprema

PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def _preflop_3handed(hero_cards, stack=2500, sb=50, button=3):
    """Mesa 3-handed: assentos 1/2/3, botão=3 (herói). SB=1, BB=2. Devolve o SupremaTable
    já alimentado até a vez do herói (BTN first-in, SB+BB postados)."""
    t = SupremaTable()
    for s, name in ((1, 'A'), (2, 'B'), (3, 'Hero')):
        t.feed(dict(t='seat', seat=s, player=name, stack=stack))
    t.feed(dict(t='round_start', stage=1, cur_blind=sb, button_seat=button, hand_id='h1'))
    t.feed(dict(t='action', seat=1, atype=8, chips=sb))          # post SB
    t.feed(dict(t='action', seat=2, atype=9, chips=2 * sb))      # post BB
    t.feed(dict(t='hand_card', seat=3, cards=hero_cards))
    return t


class SupremaPerception(unittest.TestCase):

    def test_table_state_preflop_basico(self):
        t = _preflop_3handed(['Ad', 'Ac'])
        state, hero = t.to_table_state()
        self.assertIsNotNone(state, 'não deveria abster: %r' % (hero,))
        self.assertEqual(hero, ['Ad', 'Ac'])
        self.assertEqual(state['positions']['hero'], 'BTN')            # botão=herói
        self.assertEqual(set(state['positions'].values()), {'BTN', 'SB', 'BB'})
        self.assertAlmostEqual(state['seats']['hero']['stack_bb'], 25.0)   # 2500/100
        # SB=0.5bb, BB=1.0bb, hero=0 -> to_call = 1.0bb; pote = 1.5bb
        self.assertAlmostEqual(state['to_call']['to_call_bb'], 1.0)
        self.assertAlmostEqual(state['pot']['pot_bb'], 1.5)
        self.assertEqual(state['street'], 'PREFLOP')
        self.assertEqual(state['source'], 'suprema')

    def test_abstem_sem_blind(self):
        t = SupremaTable()
        t.feed(dict(t='seat', seat=1, player='A', stack=2500))
        t.feed(dict(t='seat', seat=3, player='Hero', stack=2500))
        t.feed(dict(t='hand_card', seat=3, cards=['Ad', 'Ac']))
        state, reason = t.to_table_state()
        self.assertIsNone(state)
        self.assertEqual(reason, 'SB_DESCONHECIDO')

    def test_abstem_sem_cartas_do_heroi(self):
        t = SupremaTable()
        for s in (1, 2, 3):
            t.feed(dict(t='seat', seat=s, player=str(s), stack=2500))
        t.feed(dict(t='round_start', stage=1, cur_blind=50, button_seat=3, hand_id='h1'))
        state, reason = t.to_table_state()
        self.assertIsNone(state)
        self.assertEqual(reason, 'HERO_CARDS_UNKNOWN')

    def test_mudanca_de_rua_zera_bets_e_poe_board(self):
        t = _preflop_3handed(['Kd', 'Qs'])
        # herói paga o BB; depois flop
        t.feed(dict(t='action', seat=3, atype=3, chips=100))        # hero call 1bb
        t.feed(dict(t='round_start', stage=2, cur_blind=50, button_seat=3,
                    board=['Kh', '7d', '2c']))
        state, hero = t.to_table_state()
        self.assertIsNotNone(state)
        self.assertEqual(state['street'], 'FLOP')
        self.assertEqual(state['board'], ['Kh', '7d', '2c'])
        # bets da rua anterior foram zerados (ninguém apostou no flop ainda)
        self.assertEqual(state['to_call']['to_call_bb'], 0.0)
        # pote carregou o pré-flop (SB 0.5 + BB 1.0 + call 1.0 = 2.5bb)
        self.assertAlmostEqual(state['pot']['pot_bb'], 2.5)

    @unittest.skipUnless(os.path.exists(PACK), 'pack validado ausente')
    def test_cerebro_decide_AA_preflop(self):
        from preflop_advisor import PreflopAdvisor
        adv = (PreflopAdvisor.from_files(PACK, DEEP) if os.path.exists(DEEP)
               else PreflopAdvisor.from_file(PACK))
        t = _preflop_3handed(['Ad', 'Ac'])
        r = advise_from_suprema(t, adv, mode='chip_ev', stage='mid')
        self.assertEqual(r.get('status'), 'ADVICE')
        self.assertIn(r.get('recommended'), ('raise', 'all_in', 'bets'))   # AA nunca folda

    @unittest.skipUnless(os.path.exists(PACK), 'pack validado ausente')
    def test_cerebro_abstem_quando_estado_incompleto(self):
        from preflop_advisor import PreflopAdvisor
        adv = (PreflopAdvisor.from_files(PACK, DEEP) if os.path.exists(DEEP)
               else PreflopAdvisor.from_file(PACK))
        t = SupremaTable()                       # vazio
        r = advise_from_suprema(t, adv, mode='chip_ev', stage='mid')
        self.assertEqual(r.get('status'), 'ABSTAIN')
        self.assertEqual(r.get('source'), 'suprema')


if __name__ == '__main__':
    unittest.main()
