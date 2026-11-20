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


def _pl(seat, stack_bb, *, bet_bb=0.0, cards=None, sit=0, uid=None, name='v', hascard=1):
    # villao NA MAO: hascard=1 mesmo sem cartas visiveis (cards=[]); hero tem as 2 cartas.
    return dict(seat=seat, uid=uid or (1000 + seat), name=name,
                stack=int(stack_bb * _BB), bet=int(bet_bb * _BB),
                cards=(cards or []), sit=sit, act=0, hascard=hascard)


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

    def test_hu_sb_stale_ancora_no_dealer(self):
        # HU real (torneio 19/11): _nowSmallBlindSeat=s7 ficou STALE (jogador bustou),
        # ativos=[0,4], dealer=s4, bb=s0. Ancorar no DEALER resolve: s4=SB(botao), s0=BB.
        # Antes abstinha (sb fora dos ativos) -> HERO_POSITION_UNKNOWN no HU.
        pos = P.assign_positions([0, 4], dealer=4, sbseat=7, bbseat=0)
        self.assertEqual(pos, {4: 'SB', 0: 'BB'})

    def test_3handed_sb_stale_ancora_no_dealer(self):
        # 3-handed com sb stale: ativos=[1,3,6], dealer=6, bb=3 (sb velho s9 fora).
        # Do dealer(6) em ordem horária: 1=SB, 3=BB, 6=BTN.
        pos = P.assign_positions([1, 3, 6], dealer=6, sbseat=9, bbseat=3)
        self.assertEqual(pos, {1: 'SB', 3: 'BB', 6: 'BTN'})

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

    def test_hascard0_fica_fora_da_mao(self):
        # jogador hascard=0 (esperando/sentado fora) NAO entra nas posicoes (visto ao
        # vivo: um assento assim entre SB e BB quebraria a ordem)
        players = [_pl(0, 20, bet_bb=0.5), _pl(2, 25, bet_bb=1.0, cards=_card_ints('AsKd')),
                   _pl(1, 8, hascard=0)]
        st, hero = P.build_table_state(_entry(players, dealer=0, sbseat=0, bbseat=2))
        self.assertEqual(hero, ['As', 'Kd'])
        self.assertEqual(st['positions']['hero'], 'BB')     # heads-up: s0=SB, s2=BB(hero)
        self.assertNotIn('seat1', st['positions'])          # fora da mão

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


class OperatorHelper(unittest.TestCase):
    """_protobuf_advice do operador: lê estado_mesa.json, exige UMA mesa
    fresca (0 ou >1 -> None -> OCR de reserva), ignora estado velho."""
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(_VAL) and os.path.exists(_DEEP)):
            raise unittest.SkipTest('pacotes de range nao encontrados')
        try:
            import operar_mesa
        except Exception as e:                       # noqa: BLE001
            raise unittest.SkipTest('operar_mesa nao importavel: %s' % e)
        import tempfile
        cls.om = operar_mesa
        cls.adv = PreflopAdvisor.from_files(_VAL, _DEEP)
        cls.tmp = tempfile.mkdtemp()

    def _write(self, data):
        import json
        p = os.path.join(self.tmp, 'estado_mesa.json')
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return p

    def _fresh_entry(self):
        import time
        players = [_pl(0, 10, cards=_card_ints('AsKd')),   # hero BTN 10bb
                   _pl(1, 20, bet_bb=0.5), _pl(2, 20, bet_bb=1.0)]
        e = _entry(players, dealer=0, sbseat=1, bbseat=2)
        e['ts'] = time.time()
        return e

    def test_uma_mesa_fresca_decide(self):
        p = self._write({'r1': self._fresh_entry()})
        out = self.om._protobuf_advice(self.adv, 'chip_ev', estado_path=p)
        self.assertIsNotNone(out)
        self.assertEqual(out.get('status'), 'ADVICE')
        self.assertEqual(out.get('hero_cards'), ['As', 'Kd'])   # cartas exatas anexadas

    def test_duas_frescas_abstem_para_ocr(self):
        p = self._write({'r1': self._fresh_entry(), 'r2': self._fresh_entry()})
        self.assertIsNone(self.om._protobuf_advice(self.adv, 'chip_ev', estado_path=p))

    def test_mesa_velha_ignorada(self):
        e = self._fresh_entry(); e['ts'] = 0           # 1970 -> estado velho
        p = self._write({'r1': e})
        self.assertIsNone(self.om._protobuf_advice(self.adv, 'chip_ev', estado_path=p))


class PostflopFromMemory(unittest.TestCase):
    """Leitura PÓS-FLOP por MEMÓRIA (Eduardo 19/11): board + to_call + pote do protobuf
    (emitir_seats) -> advise_postflop, sem OCR. Mata o board ilegível e o to_call null."""

    @classmethod
    def setUpClass(cls):
        import os as _os
        v = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
        d = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'
        if not (_os.path.exists(v) and _os.path.exists(d)):
            raise unittest.SkipTest('ranges nao encontrados')
        from preflop_advisor import PreflopAdvisor
        cls.adv = PreflopAdvisor.from_files(v, d)

    def _entry(self, tocall, pot, v0bet=0):
        # dealer=2 (hero BTN), sb=0, bb=1; board 5c4s8d; hero seat2 = AsKs ([270,269]).
        return dict(table=dict(dealer=2, sbseat=0, bbseat=1, sb=1000, minraise=2000,
                               maxraise=140000, board=[1029, 260, 776], stage=2,
                               tocall=tocall, pot=pot),
                    players=[dict(seat=0, uid=11, name='v1', stack=70000, sit=0, bet=v0bet, act=1, hascard=1, cards=[]),
                             dict(seat=1, uid=22, name='v2', stack=70000, sit=0, bet=0, act=1, hascard=1, cards=[]),
                             dict(seat=2, uid=33, name='hero', stack=70000, sit=0, bet=0, act=3, hascard=1, cards=[270, 269])])

    def test_board_e_to_call_da_memoria(self):
        import protobuf_state as ps
        st, hero = ps.build_table_state(self._entry(0, 6500))
        self.assertEqual(st['scope'], 'POSTFLOP_PROTOBUF')
        self.assertEqual(st['street'], 'FLOP')
        self.assertEqual(st['board'], ['5c', '4s', '8d'])     # board EXATO da memória
        self.assertEqual(st['to_call']['to_call_bb'], 0.0)    # to_call EXATO (não null)
        self.assertEqual(hero, ['As', 'Ks'])

    def test_postflop_decide_sem_ocr(self):
        import protobuf_state as ps
        r = ps.advise_from_protobuf(self._entry(0, 6500), self.adv, mode='chip_ev', stage='mid')
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['phase'], 'postflop')
        self.assertEqual(r['perception'], 'protobuf')
        self.assertIn(r['recommended'], ('bet', 'check', 'call', 'fold', 'raise'))

    def test_facing_bet_tem_to_call_e_pot_odds(self):
        import protobuf_state as ps
        r = ps.advise_from_protobuf(self._entry(3000, 9500, 3000), self.adv, mode='chip_ev', stage='mid')
        self.assertEqual(r['phase'], 'postflop')
        self.assertIsNotNone(r.get('pot_odds'))               # pot odds computável (to_call lido)

    def test_to_call_DERIVADO_quando_emissor_nao_da(self):
        # Bug do torneio: emissor não deu tocall pós-flop (0), mas o vilão apostou 3000.
        # O to_call deve DERIVAR das apostas (maior − hero) -> pot odds existe, não abstém.
        import protobuf_state as ps
        r = ps.advise_from_protobuf(self._entry(0, 9500, 3000), self.adv, mode='chip_ev', stage='mid')
        self.assertEqual(r['phase'], 'postflop')
        self.assertGreater(r.get('to_call_bb') or 0, 0)       # derivou o preço de pagar
        self.assertIsNotNone(r.get('pot_odds'))


if __name__ == '__main__':
    unittest.main()
