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
        # decode REAL: rank=code%16, suit=code//16 (ver nvt-suprema-cartas-maior-59).
        # 78=A(14,s4), 43=J(11,h3), 73=9(9,s4), 68=4(4,s4), 59=J(11,h3)
        self.assertEqual(decode_card(78)[0], 'A')
        self.assertEqual(decode_card(43)[0], 'J')
        self.assertEqual(decode_card(73)[0], '9')
        self.assertEqual(decode_card(68)[0], '4')
        self.assertEqual(decode_card(59)[0], 'J')
        # naipe bijetivo: 20 e 52 são ambos rank 4 mas de naipes DIFERENTES (1 vs 3)
        self.assertEqual(decode_card(20)[0], decode_card(52)[0])
        self.assertNotEqual(decode_card(20)[1], decode_card(52)[1])
        # FLUSH: 68,72,73,74,77 são todos naipe 4 -> mesmo suit (prova decisiva do scheme)
        self.assertEqual(len({decode_card(c)[1] for c in (68, 72, 73, 74, 77)}), 1)

    def test_invalid_codes_sao_none(self):
        # fora da faixa de rank (2..14) ou suit (1..4) = None, nunca chuta
        self.assertIsNone(decode_card(16))   # rank 0
        self.assertIsNone(decode_card(17))   # rank 1
        self.assertIsNone(decode_card(15))   # suit 0
        self.assertIsNone(decode_card(79))   # rank 15

    def test_hidden_cards(self):
        self.assertIsNone(decode_card(0))
        self.assertEqual(decode_cards([0, 0]), [])
        self.assertEqual(decode_cards(None), [])
        # 40=8(8,c2), 23=7(7,d1)
        self.assertEqual(decode_cards([40, 23]), ['8c', '7d'])

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
    """Pré-flop 3-handed (schema REAL): herói seat2=dealer(BTN) com AA=[78,62] (As,Ah no
    decode real); SB=seat3, BB=seat6. Devolve SupremaTable alimentado por gameinfo + moveturn."""
    t = SupremaTable(bb_chips=bb_chips)
    t.feed_json({"route": "onMsg", "event": "gameinfo",
                 "data": {"game_info": {"gamers_count": 3, "dealer_seat": 2,
                                        "shared_cards": [], "pot": 750, "state": 3}}})
    t.feed_json({"route": "onMsg", "event": "moveturn", "data": {"game_seat": {
        "1754193": {"seat": 2, "uid": 1754193, "coins": 10000, "cards": [78, 62], "chips": 0, "sitout": False, "role": 0},
        "388769":  {"seat": 3, "uid": 388769, "coins": 9000, "cards": None, "chips": 250, "sitout": False, "role": 0},
        "295455":  {"seat": 6, "uid": 295455, "coins": 12000, "cards": [0, 0], "chips": 500, "sitout": False, "role": 40},
    }}})
    return t


class SupremaPerception(unittest.TestCase):

    def test_table_state_preflop(self):
        t = _preflop_AA_btn()
        state, hero = t.to_table_state()
        self.assertIsNotNone(state, 'abstido: %r' % (hero,))
        self.assertEqual(hero, ['As', 'Ah'])                     # [78,62] = As + Ah (naipes diff)
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
        self.assertEqual(state['board'], ['4c', 'Jh', '7c'])     # 36=4c,59=Jh,39=7c
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

    def test_heroi_por_uid_no_prompt_de_deal(self):
        # mensagem REAL de deal: uid na RAIZ + game_seat só do herói com cartas reais
        t = SupremaTable(bb_chips=50)
        t.feed_json({"route": "onMsg", "uid": 1754193, "event": "prompt", "data": {
            "gamer_prompt": {"fold": None, "check": None, "call": None, "raise": None,
                             "all_in": None, "ready": None, "bet": None},
            "game_seat": {"1754193": {"seat": 7, "uid": 1754193, "coins": 60825,
                                      "cards": [20, 46], "chips": 75, "sitout": False}}}})
        self.assertEqual(t.hero_uid, 1754193)
        self.assertEqual(t.hero_seat, 7)
        self.assertEqual(t.players[7]['cards'], ['4d', 'Ac'])     # [20,46] = 4d, Ac

    def test_heroi_persiste_por_uid_com_cards_null(self):
        t = SupremaTable(bb_chips=50, hero_uid=1754193)
        # deal: herói recebe cartas
        t.feed_json({"event": "prompt", "uid": 1754193, "data": {"game_seat": {
            "1754193": {"seat": 7, "uid": 1754193, "coins": 60825, "cards": [20, 46], "chips": 75, "sitout": False}}}})
        # moveturn posterior: cards=null p/ todos (servidor não reenvia) -> herói PERSISTE
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "1754193": {"seat": 7, "uid": 1754193, "coins": 60750, "cards": None, "chips": 150, "sitout": False},
            "300268": {"seat": 4, "uid": 300268, "coins": 45375, "cards": None, "chips": 150, "sitout": False}}}})
        self.assertEqual(t.hero_seat, 7)                          # continua o herói (por uid)
        self.assertEqual(t.players[7]['cards'], ['4d', 'Ac'])     # cartas PERSISTEM na mão

    def test_gamestart_novo_counter_zera_cartas(self):
        # MÃO NOVA (game_counter muda) zera as cartas da anterior.
        t = SupremaTable(bb_chips=50, hero_uid=1754193)
        t.feed_json({"event": "gamestart", "data": {"game_info": {"game_counter": 10}}})
        t.feed_json({"event": "prompt", "uid": 1754193, "data": {"game_seat": {
            "1754193": {"seat": 7, "uid": 1754193, "coins": 60825, "cards": [20, 46], "chips": 75, "sitout": False}}}})
        self.assertEqual(t.players[7]['cards'], ['4d', 'Ac'])
        t.feed_json({"event": "gamestart", "data": {"game_info": {"game_counter": 11}}})  # mão NOVA
        self.assertEqual(t.players[7]['cards'], [])               # nova mão -> zera
        self.assertIsNone(t.hero_seat)

    def test_gamestart_redundante_NAO_apaga_cartas(self):
        # BUG 21/11: a Suprema manda gamestart REDUNDANTE (counter=None / repetido) em rajada
        # no MEIO da mão; resetar nesses apagava as cartas já recebidas -> abstenção na vez.
        # Agora só reseta quando o game_counter MUDA.
        t = SupremaTable(bb_chips=50, hero_uid=1754193)
        t.feed_json({"event": "gamestart", "data": {"game_info": {"game_counter": 20}}})
        t.feed_json({"event": "prompt", "uid": 1754193, "data": {"game_seat": {
            "1754193": {"seat": 7, "uid": 1754193, "coins": 60825, "cards": [20, 46], "chips": 75, "sitout": False}}}})
        self.assertEqual(t.players[7]['cards'], ['4d', 'Ac'])
        t.feed_json({"event": "gamestart", "data": {}})                       # redundante sem counter
        t.feed_json({"event": "gamestart", "data": {"game_info": {"game_counter": 20}}})  # repetido
        self.assertEqual(t.players[7]['cards'], ['4d', 'Ac'])     # PRESERVA (não é mão nova)
        self.assertEqual(t.hero_seat, 7)

    def test_revelacao_de_oponente_nao_sequestra_heroi(self):
        # BUG 21/11 (CRÍTICO): no showdown as cartas do OPONENTE são reveladas e o fallback
        # len(cards)==2 jogava o hero_seat pro vilão -> o Henrique lia a mão errada (tinha 8d3c,
        # leu 6d8s). Com hero_uid conhecido, só o assento do uid é o herói.
        t = SupremaTable(bb_chips=500, hero_uid=1754193)
        t.feed_json({"event": "prompt", "uid": 1754193, "data": {"game_seat": {
            "1754193": {"seat": 6, "uid": 1754193, "coins": 10000, "cards": [59, 56],
                        "chips": 0, "sitout": False}}}})
        self.assertEqual(t.hero_seat, 6)
        self.assertEqual(t.players[6]['cards'], ['Jh', '8h'])   # 59=Jh, 56=8h (decode REAL)
        t.feed_json({"event": "moveturn", "data": {"game_seat": {           # showdown: vilão revela
            "999": {"seat": 7, "uid": 999, "coins": 0, "cards": [40, 23], "chips": 0, "sitout": False}}}})
        self.assertEqual(t.hero_seat, 6)                     # NÃO pulou pro vilão
        self.assertEqual(t.players[6]['cards'], ['Jh', '8h'])   # cartas do herói intactas
        self.assertEqual(t.players[7]['cards'], ['8c', '7d'])   # vilão guardado no assento DELE

    def test_allin_reveal_sem_uid_nao_ancora_vilao(self):
        # BUG RESIDUAL (22/11, visto AO VIVO): captura começa NO MEIO de um all-in, antes do 1º
        # prompt endereçado ao herói -> hero_uid ainda None. Vários assentos viram face-up
        # (reveal). O fallback "assento com 2 cartas" NÃO pode ancorar num vilão: com >1 mão
        # revelada (revealed>1), não seta hero_seat. Antes: li KK de vilão (all-in vs AK) como herói.
        t = SupremaTable(bb_chips=600)                       # hero_uid DESCONHECIDO
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "111": {"seat": 2, "uid": 111, "coins": 0, "cards": [77, 61], "chips": 0, "sitout": False},
            "222": {"seat": 5, "uid": 222, "coins": 0, "cards": [78, 62], "chips": 0, "sitout": False}}}})
        self.assertIsNone(t.hero_seat)                       # reveal múltiplo -> NÃO ancora ninguém
        state, reason = t.to_table_state()
        self.assertIsNone(state)
        self.assertEqual(reason, 'HERO_CARDS_UNKNOWN')

    def test_uma_mao_faceup_sem_uid_ainda_ancora_heroi(self):
        # Caso normal pré-showdown sem uid conhecido: só o HERÓI mostra 2 cartas (revealed==1),
        # então o fallback AINDA ancora o herói (o guard não quebrou o comportamento bom).
        t = SupremaTable(bb_chips=600)                       # hero_uid DESCONHECIDO
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "111": {"seat": 2, "uid": 111, "coins": 10000, "cards": [40, 23], "chips": 0, "sitout": False},
            "222": {"seat": 5, "uid": 222, "coins": 9000, "cards": None, "chips": 0, "sitout": False}}}})
        self.assertEqual(t.hero_seat, 2)                     # única mão face-up = herói
        self.assertEqual(t.players[2]['cards'], ['8c', '7d'])

    def test_to_call_posflop_usa_chips_round(self):
        # PÓS-FLOP (achado 22/11 ao vivo): `chips` acumula entre ruas -> to_call derivado dava
        # errado no pós-flop. FIX: derivar do `chips_round` (aposta da RUA, reseta por street).
        # Aqui hero chips_round=0 e vilão apostou 1bb nesta rua (chips_round=600); o `chips`
        # acumulado (1000 vs 1200) daria 0.33bb ERRADO, o chips_round dá 1.0bb CERTO.
        t = SupremaTable(bb_chips=600, hero_uid=100)
        t.feed_json({"event": "gameinfo", "data": {"game_info": {
            "dealer_seat": 2, "shared_cards": [73, 77, 20], "pot": 5000, "state": 4}}})
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "100": {"seat": 2, "uid": 100, "coins": 50000, "cards": [78, 62],
                    "chips": 1000, "chips_round": 0, "sitout": False},
            "200": {"seat": 5, "uid": 200, "coins": 40000, "cards": None,
                    "chips": 1200, "chips_round": 600, "sitout": False}}}})
        state, hero = t.to_table_state()
        self.assertIsNotNone(state, hero)
        self.assertEqual(state['street'], 'FLOP')                 # board de 3 cartas
        self.assertAlmostEqual(state['to_call']['to_call_bb'], 1.0)   # chips_round, NÃO chips

    def test_cold_attach_sem_cartas_do_heroi_abstem(self):
        # Anexar no MEIO da mão (sem ver o deal do herói) + oponente revelado: NÃO pode ler a
        # mão do vilão; deve ABSTER (HERO_CARDS_UNKNOWN) — leitura segura.
        t = SupremaTable(bb_chips=500, hero_uid=1754193)
        t.feed_json({"event": "prompt", "uid": 1754193, "data": {
            "gamer_prompt": {"fold": True, "call": 100},
            "game_seat": {"1754193": {"seat": 6, "uid": 1754193, "coins": 10000,
                                      "cards": None, "chips": 0, "sitout": False}}}})
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "999": {"seat": 7, "uid": 999, "coins": 0, "cards": [40, 23], "chips": 0, "sitout": False}}}})
        state, reason = t.to_table_state()
        self.assertIsNone(state)                             # abstém, NÃO lê a mão do vilão
        self.assertEqual(reason, 'HERO_CARDS_UNKNOWN')

    def test_posicao_congela_quando_gente_folda(self):
        # BUG 21/11: a posição DESLIZAVA (BB virava SB na rua) porque era recomputada sobre os
        # ATIVOS do momento; ao foldar o SB, o herói (BB) herdava o rótulo SB. Agora ancora nos
        # assentos DISTRIBUÍDOS na mão (união monotônica) -> rótulo estável.
        t = SupremaTable(bb_chips=500, hero_uid=5000)
        gs = {str(1000 + s): {"seat": s, "uid": 1000 + s, "coins": 10000,
                              "cards": None, "chips": 0, "sitout": False}
              for s in range(8) if s != 5}
        gs["5000"] = {"seat": 5, "uid": 5000, "coins": 10000, "cards": [59, 56],
                      "chips": 500, "sitout": False}
        t.feed_json({"event": "gameinfo", "data": {"game_info": {
            "dealer_seat": 3, "shared_cards": [], "pot": 0, "state": 3}}})
        t.feed_json({"event": "moveturn", "data": {"game_seat": gs}})
        state, hero = t.to_table_state()
        self.assertIsNotNone(state, 'abstido: %r' % (hero,))
        self.assertEqual(state['positions']['hero'], 'BB')     # dealer=3 -> seat5 = BB
        # o SB (seat4) FOLDA e sai dos ATIVOS
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "1004": {"seat": 4, "uid": 1004, "coins": 10000, "cards": None,
                     "chips": 0, "sitout": True}}}})
        state2, _ = t.to_table_state()
        self.assertEqual(state2['positions']['hero'], 'BB')    # CONGELA: continua BB (não vira SB)

    def test_board_nao_encolhe_na_mao(self):
        # BUG 21/11: o flop lido PARCIAL (2 de 3 cartas) sobrescrevia o board completo (flicker).
        t = SupremaTable(bb_chips=500, hero_uid=5000)
        t.feed_json({"event": "gamestart", "data": {"game_info": {"game_counter": 50}}})
        t.feed_json({"event": "gameinfo", "data": {"game_info": {"shared_cards": [36, 59, 39]}}})
        self.assertEqual(t.board, ['4c', 'Jh', '7c'])
        t.feed_json({"event": "gameinfo", "data": {"game_info": {"shared_cards": [36, 59]}}})  # parcial
        self.assertEqual(t.board, ['4c', 'Jh', '7c'])          # NÃO encolhe
        t.feed_json({"event": "gameinfo", "data": {"game_info": {"shared_cards": [36, 59, 39, 44]}}})
        self.assertEqual(t.board, ['4c', 'Jh', '7c', 'Qc'])    # cresce normal (turn)
        t.feed_json({"event": "gamestart", "data": {"game_info": {"game_counter": 51}}})
        self.assertEqual(t.board, [])                          # mão NOVA zera

    @unittest.skipUnless(os.path.exists(PACK), 'pack validado ausente')
    def test_cerebro_decide_AA(self):
        from preflop_advisor import PreflopAdvisor
        adv = (PreflopAdvisor.from_files(PACK, DEEP) if os.path.exists(DEEP)
               else PreflopAdvisor.from_file(PACK))
        r = advise_from_suprema(_preflop_AA_btn(), adv, mode='chip_ev', stage='mid')
        self.assertEqual(r.get('status'), 'ADVICE')
        self.assertIn(r.get('recommended'), ('raise', 'all_in', 'bets'))   # AA nunca folda


class SpotGateAntiFlicker(unittest.TestCase):
    """_SpotGate (novo contrato, Eduardo 22/11): STABLE_FRAMES=1 -> DECIDE na 1ª leitura válida
    (velocidade, anti sit-out). NÃO re-decide o MESMO spot: `_decided` PERSISTE entre resets/flickers
    (legal_actions pisca vazio não re-dispara) e `hand_id` entra na sig (mão nova re-decide). Mata o
    'raise raise raise' do AK no gate; a trava de 1-tentativa no emit é a garantia final."""

    def test_decide_na_1a_leitura(self):
        from assistir_suprema import _SpotGate
        g = _SpotGate()
        A = ((7,), (), 'BB', ('check', 'fold', 'raise'), 0.0)
        self.assertEqual(g.offer(A), 'decide')    # STABLE_FRAMES=1: decide já na 1ª
        self.assertEqual(g.offer(A), 'wait')      # mesmo spot -> NÃO re-decide (_decided)
        self.assertEqual(g.offer(A), 'wait')

    def test_mesmo_spot_nao_redecide_apos_flicker(self):
        # legal_actions pisca vazio -> reset() NÃO limpa _decided -> mesmo spot não re-dispara
        # (mata o 'raise raise raise' do AK).
        from assistir_suprema import _SpotGate
        g = _SpotGate()
        A = ((7,), (), 'BB', ('check', 'fold', 'raise'), 0.0)
        self.assertEqual(g.offer(A), 'decide')
        g.reset()                                 # a vez "sumiu" 1 frame e voltou (flicker)
        self.assertEqual(g.offer(A), 'wait')      # mesma mão/spot -> não re-decide

    def test_mao_nova_redecide(self):
        from assistir_suprema import _SpotGate
        g = _SpotGate()
        A = ((7,), (), 'BB', ('check', 'fold', 'raise'), 0.0)
        B = ((8,), (), 'BB', ('check', 'fold', 'raise'), 0.0)   # hand_id diferente = mão nova
        self.assertEqual(g.offer(A), 'decide')
        g.reset()
        self.assertEqual(g.offer(B), 'decide')    # mão nova -> decide de novo

    def test_bet_raise_nao_conta_como_flicker(self):
        from assistir_suprema import _spot_sig
        s_raise = _spot_sig({'board': [], 'positions': {'hero': 'BB'},
                             'legal_actions': ['all_in', 'check', 'fold', 'raise'],
                             'to_call': {'to_call_bb': 0.0}})
        s_bet = _spot_sig({'board': [], 'positions': {'hero': 'BB'},
                           'legal_actions': ['all_in', 'bet', 'check', 'fold'],
                           'to_call': {'to_call_bb': 0.0}})
        self.assertEqual(s_raise, s_bet)                 # bet<->raise = MESMA assinatura


class ReRaiseExecutavel(unittest.TestCase):
    """BUG 21/11: recommended='three_bet' (e 4bet/squeeze/iso) caía em ABSTAIN:REC_DESCONHECIDO
    no plan_action. Agora vira RAISE executável (ou ALL_IN p/ shove); limp vira CALL."""

    def test_rec_family_vocabulario(self):
        from suprema_act import _rec_family, RAISE, ALL_IN, CALL, FOLD, CHECK
        for r in ('three_bet', 'four_bet', '3bet', '4bet', 'squeeze', 'isolate', 'iso',
                  'open_raise', 'raise', 'bet', 'bets'):
            self.assertEqual(_rec_family(r), RAISE, r)
        for r in ('shove', 'open_shove', 'all_in', 'all-in', 'jam'):
            self.assertEqual(_rec_family(r), ALL_IN, r)
        self.assertEqual(_rec_family('limp'), CALL)
        self.assertEqual(_rec_family('fold'), FOLD)
        self.assertEqual(_rec_family('check'), CHECK)
        self.assertIsNone(_rec_family('xyz'))

    def test_three_bet_vira_raise_concreto(self):
        import suprema_act
        t = SupremaTable(bb_chips=500)
        t.feed_json({"event": "prompt", "data": {"gamer_prompt": {
            "fold": True, "check": None, "call": 1250,
            "raise": "range,2500,20000,2X,2500,3X,4000",
            "all_in": True, "ready": None, "bet": None}}})
        plan = suprema_act.plan_action({"status": "ADVICE", "recommended": "three_bet"}, t)
        self.assertEqual(plan['action'], 'raise')         # não mais ABSTAIN
        self.assertIsNotNone(plan.get('chips'))
        self.assertGreaterEqual(plan['chips'], 2500)      # pelo menos o min-3bet LEGAL (não inventa)


class BoardDesconhecidoBalanceia(unittest.TestCase):
    """BUG 21/11 (nº 3): cartas de board de naipe 4 (ex-'>59') não decodificavam -> board curto
    -> o emissor PULAVA turn/river -> betting dropado -> chip_imbalance. Com o decode REAL
    (code%16 / code//16) naipe 4 decodifica normal; decode_board preserva a CONTAGEM e só marca
    '??' p/ código oculto/inválido (sem chutar) + emit_hand emite a rua se tiver board OU ação."""

    def test_decode_board_decodifica_naipe4_e_marca_oculta(self):
        from suprema_state import decode_board
        # naipe 4 agora decodifica: 73=9s, 72=8s, 55=7h (antes virava '??')
        self.assertEqual(decode_board([73, 72, 55]), ['9s', '8s', '7h'])
        # código oculto/inválido preserva a posição como '??' (sem chutar)
        self.assertEqual(decode_board([73, 0, 55]), ['9s', '??', '7h'])
        self.assertEqual(decode_board([40, 23]), ['8c', '7d'])            # conhecidas decodificam
        self.assertEqual(decode_board([]), [])

    def test_emit_nao_dropa_betting_de_rua_sem_board(self):
        from hand_history_emit import emit_hand
        h = dict(room='SupremaPoker', hand_id='1', tournament_id='t', buyin='$0 USD',
                 sb=1, bb=2, ante=0, datetime='2026/11/21 00:00:00', club_id='', table_tag='t',
                 max_seats=9, button_seat=0,
                 seats=[{'seat': 0, 'player': 'A', 'chips': 100},
                        {'seat': 1, 'player': 'B', 'chips': 100}],
                 hero=None, hero_cards=[], posts=[],
                 streets={'turn': [{'player': 'A', 'action': 'bets', 'amount': 50}]},
                 board={'flop': [], 'turn': [], 'river': []},    # board VAZIO mas HÁ ação no turn
                 uncalled=None, collected=[], total_pot=50, rake=0, end_datetime='x')
        text = emit_hand(h)
        self.assertIn('*** TURN ***', text)        # rua emitida mesmo sem board (tinha ação)
        self.assertIn('A: bets 50', text)           # betting NÃO foi dropado


class _FoldStub:
    """Advisor FALSO: devolve sempre FOLD (p/ provar o override em isolamento, sem pack)."""
    def advise_from_reading(self, state, hero_cards, **kwargs):
        return dict(status='ADVICE', recommended='fold',
                    mix=[{'action': 'fold', 'frequency': 1.0}], caveats=[])


class _RaiseStub:
    """Advisor FALSO: devolve sempre RAISE (p/ provar que o override NÃO mexe no que não é fold)."""
    def advise_from_reading(self, state, hero_cards, **kwargs):
        return dict(status='ADVICE', recommended='raise',
                    mix=[{'action': 'raise', 'frequency': 1.0}], caveats=[])


def _blind_war_bb_sitout():
    """HU blind-war (schema REAL): hero=seat2=dealer(=SB em HU) com cartas reais; o BB=seat5
    está SIT-OUT (auto-folda a blind). O vilão sai dos ATIVOS -> estado precisa expor o sit-out."""
    t = SupremaTable(bb_chips=500, hero_uid=1754193)
    t.feed_json({"event": "gameinfo", "data": {"game_info": {
        "dealer_seat": 2, "shared_cards": [], "pot": 750, "state": 3}}})
    t.feed_json({"event": "moveturn", "uid": 1754193, "data": {"game_seat": {
        "1754193": {"seat": 2, "uid": 1754193, "coins": 10000, "cards": [36, 23],
                    "chips": 250, "chips_round": 250, "sitout": False, "role": 0},   # 36=4c,23=7d (trash)
        "999": {"seat": 5, "uid": 999, "coins": 9000, "cards": None,
                "chips": 500, "chips_round": 500, "sitout": True, "role": 93}}}})     # BB SIT-OUT
    return t


class SitOutExposicao(unittest.TestCase):
    """TAREFA 1/4: o sit-out do VILÃO e do HERO ficam expostos no estado SEM quebrar posição."""

    def test_estado_expoe_sitout_do_vilao(self):
        state, hero = self._state()
        self.assertEqual(state['positions'], {'hero': 'SB'})        # ativo = só o hero (BB saiu)
        self.assertEqual(state['sitout_positions'], ['BB'])          # BB sit-out EXPOSTO por posição
        self.assertFalse(state['hero_sitout'])                       # hero NÃO está sit-out
        self.assertFalse(state['seats']['hero']['sitout'])

    def test_hero_sitout_flag(self):
        t = _blind_war_bb_sitout()
        t.players[2]['sitout'] = True                                # hero entra em sit-out
        # com hero sit-out ele some dos ATIVOS; o gate ainda conta hero+BB sit-out
        state, reason = t.to_table_state()
        self.assertIsNotNone(state, reason)
        self.assertTrue(state['hero_sitout'])                        # flag do PRÓPRIO hero exposto

    def _state(self):
        state, hero = _blind_war_bb_sitout().to_table_state()
        self.assertIsNotNone(state, 'abstido: %r' % (hero,))
        return state, hero


class NuncaWalkSitOut(unittest.TestCase):
    """TAREFA 2: override 'nunca dar WALK a sit-out' — fold->raise no blind-war com defensor
    sit-out; INALTERADO quando o hero enfrenta um ATIVO."""

    def test_fold_vira_raise_quando_BB_sitout(self):
        r = advise_from_suprema(_blind_war_bb_sitout(), _FoldStub())
        self.assertEqual(r['recommended'], 'raise')                  # ROUBA, não folda
        self.assertIn('NEVER_WALK_SITOUT_STEAL', r.get('caveats', []))
        self.assertEqual(r['exploit']['reason'], 'NEVER_WALK_SITOUT_STEAL')

    def test_raise_recomendado_fica_intacto(self):
        r = advise_from_suprema(_blind_war_bb_sitout(), _RaiseStub())
        self.assertEqual(r['recommended'], 'raise')                  # já era raise -> igual
        self.assertNotIn('NEVER_WALK_SITOUT_STEAL', r.get('caveats', []))

    def test_facing_aposta_de_ativo_NAO_mexe(self):
        # 3-handed: hero (BB) enfrenta um vilão ATIVO que abriu 3bb; o SB está sit-out. Há
        # sit-out na mão, MAS sobra oponente ATIVO vivo e to_call>1bb -> NÃO é walk; mesmo
        # fold stub, o override NÃO toca (não se rouba de quem está apostando de verdade).
        t = SupremaTable(bb_chips=500, hero_uid=1754193)
        t.feed_json({"event": "gameinfo", "data": {"game_info": {
            "dealer_seat": 2, "shared_cards": [], "pot": 2250, "state": 3}}})
        t.feed_json({"event": "moveturn", "uid": 1754193, "data": {"game_seat": {
            "1754193": {"seat": 7, "uid": 1754193, "coins": 10000, "cards": [36, 23],
                        "chips": 500, "chips_round": 500, "sitout": False, "role": 93},   # hero BB (1bb)
            "500": {"seat": 2, "uid": 500, "coins": 9000, "cards": None,
                    "chips": 1500, "chips_round": 1500, "sitout": False, "role": 0},       # ATIVO abriu 3bb (BTN)
            "999": {"seat": 3, "uid": 999, "coins": 8000, "cards": None,
                    "chips": 250, "chips_round": 250, "sitout": True, "role": 0}}}})        # SB sit-out
        state, _ = t.to_table_state()
        self.assertGreater(state['to_call']['to_call_bb'], 1.0)      # enfrenta aposta REAL
        self.assertTrue(state['sitout_positions'])                  # há sit-out na mão, mas...
        self.assertGreater(len(state['positions']), 1)              # ...sobra oponente ATIVO vivo
        r = advise_from_suprema(t, _FoldStub())
        self.assertEqual(r['recommended'], 'fold')                  # INALTERADO (não rouba de ativo)

    def test_override_unitario_direto(self):
        from sitout_steal import never_walk_sitout, is_sitout_walk_steal
        steal = dict(board=[], positions={'hero': 'SB'}, sitout_positions=['BB'],
                     to_call={'to_call_bb': 0.0})
        self.assertTrue(is_sitout_walk_steal(steal))
        out = never_walk_sitout(dict(status='ADVICE', recommended='fold'), steal)
        self.assertEqual(out['recommended'], 'raise')
        # sem defensor sit-out -> não dispara
        self.assertFalse(is_sitout_walk_steal(dict(steal, sitout_positions=[])))
        # oponente ATIVO vivo -> não dispara
        self.assertFalse(is_sitout_walk_steal(dict(steal, positions={'hero': 'SB', 'seat2': 'BB'})))
        # pós-flop -> não dispara
        self.assertFalse(is_sitout_walk_steal(dict(steal, board=['4c', 'Jh', '7c'])))
        # recomendação não-fold fica intacta
        keep = never_walk_sitout(dict(status='ADVICE', recommended='call'), steal)
        self.assertEqual(keep['recommended'], 'call')


if __name__ == '__main__':
    unittest.main()
