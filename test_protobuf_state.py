"""Percepção pré-flop via PROTOBUF (protobuf_state): conversão estado->table_state,
derivação de posição auto-validada, identificação do hero, e decisão ponta-a-ponta
pelo MESMO roteamento (advise_from_reading). Tudo OFFLINE/sintético."""
import os
import unittest

import protobuf_state as P
from ppp_cards import encode_card
from preflop_advisor import PreflopAdvisor

_SB = 250000            # small blind em fichas -> BB = 500000
_BB = 2 * _SB


def _card_ints(h):
    """'AsKd' -> [int, int] no encoding do PPPoker (via encode_card, roundtrip)."""
    return [encode_card(h[0:2]), encode_card(h[2:4])]


def _pl(seat, stack_bb, *, bet_bb=0.0, cards=None, sit=0, uid=None, name='v'):
    return dict(seat=seat, uid=uid or (1000 + seat), name=name,
                stack=int(stack_bb * _BB), bet=int(bet_bb * _BB),
                cards=(cards or []), sit=sit, act=0, hascard=bool(cards))


def _entry(players, *, dealer, sbseat, bbseat, sb=_SB):
    return dict(ts=0, room='r', players=players,
                table=dict(dealer=dealer, sbseat=sbseat, bbseat=bbseat, sb=sb))


class CanonicalOrder(unittest.TestCase):
    def test_core_nao_diverge_das_outras_fontes(self):
        # trava: o _CORE do conversor tem que ser IDÊNTICO ao do sistema (senão as
        # posições do protobuf divergem das da range = gaveta errada).
        from table_reading.dealer_button import _CORE as DB_CORE
        self.assertEqual(P._CORE, DB_CORE)
        import hrc_ingest
        self.assertEqual(P._CORE, hrc_ingest.POSITIONS)


class BBAndHero(unittest.TestCase):
    def test_bb_e_dobro_do_sb(self):
        self.assertEqual(P.bb_chips({'sb': _SB}), _BB)

    def test_bb_none_sem_sb(self):
        self.assertIsNone(P.bb_chips({'sb': 0}))
        self.assertIsNone(P.bb_chips({}))

    def test_hero_e_o_unico_com_2_cartas(self):
        players = [_pl(0, 20), _pl(3, 15, cards=_card_ints('AsKd')), _pl(5, 10)]
        self.assertEqual(P.hero_seat(players), 3)

    def test_hero_none_se_ambiguo(self):
        players = [_pl(0, 20, cards=_card_ints('AsKd')), _pl(3, 15, cards=_card_ints('QhJc'))]
        self.assertIsNone(P.hero_seat(players))         # 2 com cartas -> não dá p/ saber
        self.assertIsNone(P.hero_seat([_pl(0, 20)]))    # nenhum com cartas


class Positions(unittest.TestCase):
    def test_9max(self):
        pos = P.assign_positions(range(9), dealer=0, sbseat=1, bbseat=2)
        self.assertEqual(pos, {1: 'SB', 2: 'BB', 3: 'UTG', 4: 'UTG+1', 5: 'UTG+2',
                               6: 'LJ', 7: 'HJ', 8: 'CO', 0: 'BTN'})

    def test_6max(self):
        pos = P.assign_positions(range(6), dealer=0, sbseat=1, bbseat=2)
        self.assertEqual(pos, {1: 'SB', 2: 'BB', 3: 'LJ', 4: 'HJ', 5: 'CO', 0: 'BTN'})

    def test_headsup_dealer_e_sb(self):
        pos = P.assign_positions([0, 1], dealer=0, sbseat=0, bbseat=1)
        self.assertEqual(pos, {0: 'SB', 1: 'BB'})

    def test_3handed_com_buracos(self):
        # assentos reais do recon (dealer=5, sb=7, bb=2) — ordem circular com wrap
        pos = P.assign_positions([2, 5, 7], dealer=5, sbseat=7, bbseat=2)
        self.assertEqual(pos, {7: 'SB', 2: 'BB', 5: 'BTN'})

    def test_abstem_se_sb_bb_nao_adjacentes(self):
        self.assertEqual(P.assign_positions([0, 1, 2, 3], dealer=0, sbseat=1, bbseat=3), {})

    def test_abstem_se_dealer_nao_e_btn_derivado(self):
        # dealer informado não bate com o último rótulo (BTN) -> não chuta
        self.assertEqual(P.assign_positions(range(9), dealer=4, sbseat=1, bbseat=2), {})


class BuildTableState(unittest.TestCase):
    def test_monta_positions_seats_bets_e_cartas(self):
        # 4 jogadores -> posições SB,BB,CO,BTN (UTG/LJ só existem com mais gente)
        players = [_pl(0, 20), _pl(1, 30, bet_bb=0.5), _pl(2, 25, bet_bb=1.0),
                   _pl(3, 10, cards=_card_ints('AsKd'))]   # hero = seat3 (CO, 4-handed)
        st, hero = P.build_table_state(_entry(players, dealer=0, sbseat=1, bbseat=2))
        self.assertEqual(hero, ['As', 'Kd'])
        self.assertEqual(st['positions']['hero'], 'CO')
        self.assertEqual(st['seats']['hero']['stack_bb'], 10.0)
        self.assertEqual(st['seats']['hero']['source'], 'protobuf')
        bb_bet = {b['seat']: b['bet_bb'] for b in st['bets']}
        self.assertAlmostEqual(bb_bet['seat1'], 0.5)      # SB postou 0.5
        self.assertAlmostEqual(bb_bet['seat2'], 1.0)      # BB postou 1.0
        self.assertAlmostEqual(bb_bet['hero'], 0.0)

    def test_abstencoes_explicitas(self):
        ok = [_pl(0, 20), _pl(1, 30), _pl(2, 25, cards=_card_ints('AsKd'))]
        self.assertEqual(P.build_table_state(_entry(ok, dealer=0, sbseat=1, bbseat=2, sb=0))[1],
                         'SB_DESCONHECIDO')
        self.assertEqual(P.build_table_state(_entry([_pl(0, 20, cards=_card_ints('AsKd'))],
                         dealer=0, sbseat=1, bbseat=2))[1], 'POUCOS_JOGADORES')
        self.assertEqual(P.build_table_state(_entry([_pl(0, 20), _pl(1, 30)],
                         dealer=0, sbseat=1, bbseat=2))[1], 'HERO_CARDS_UNKNOWN')


class FakeAdvisor:
    def advise_from_reading(self, table_state, hero_cards, **kw):
        self.seen = dict(state=table_state, hero=hero_cards, kw=kw)
        return dict(status='ADVICE', recommended='sentinela')


class AdviseFromProtobuf(unittest.TestCase):
    def test_alimenta_o_advisor_com_estado_exato(self):
        # 9-handed cheio: hero no seat6 = LJ (ordem canônica do ring completo)
        players = [_pl(0, 50), _pl(1, 40, bet_bb=0.5), _pl(2, 40, bet_bb=1.0),
                   _pl(3, 30), _pl(4, 30), _pl(5, 30),
                   _pl(6, 12, cards=_card_ints('AhAs')), _pl(7, 25), _pl(8, 25)]
        fake = FakeAdvisor()
        out = P.advise_from_protobuf(_entry(players, dealer=0, sbseat=1, bbseat=2),
                                     fake, mode='chip_ev', stage='mid', players=9)
        self.assertEqual(out['recommended'], 'sentinela')
        self.assertEqual(fake.seen['hero'], ['Ah', 'As'])
        self.assertEqual(fake.seen['state']['positions']['hero'], 'LJ')
        self.assertEqual(fake.seen['kw']['mode'], 'chip_ev')

    def test_abstencao_passa_sem_chamar_advisor(self):
        fake = FakeAdvisor()
        out = P.advise_from_protobuf(_entry([_pl(0, 20), _pl(1, 30)],
                                     dealer=0, sbseat=1, bbseat=2), fake)
        self.assertEqual(out['status'], 'ABSTAIN')
        self.assertEqual(out['reason'], 'HERO_CARDS_UNKNOWN')
        self.assertFalse(hasattr(fake, 'seen'))


_VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


class EndToEndComAdvisorReal(unittest.TestCase):
    """Ponta-a-ponta: estado protobuf -> cérebro REAL -> decisão (sem OCR)."""
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(_VAL) and os.path.exists(_DEEP)):
            raise unittest.SkipTest('pacotes de range nao encontrados')
        cls.adv = PreflopAdvisor.from_files(_VAL, _DEEP)

    def test_btn_curto_first_in_decide(self):
        # BTN 10bb, foldado até ele (só blinds com aposta): tem que DECIDIR (não abster)
        players = [_pl(0, 10, cards=_card_ints('AsKd')),   # hero BTN
                   _pl(1, 20, bet_bb=0.5), _pl(2, 20, bet_bb=1.0)]
        out = P.advise_from_protobuf(_entry(players, dealer=0, sbseat=1, bbseat=2),
                                     self.adv, mode='chip_ev', stage='mid', players=9)
        self.assertEqual(out.get('status'), 'ADVICE')
        self.assertIn(out.get('recommended'), ('raise', 'all_in', '3bet', 'three_bet'))
        self.assertEqual(out.get('hero_position'), 'BTN')


if __name__ == '__main__':
    unittest.main()
