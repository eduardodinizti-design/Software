"""Percepção AO VIVO da SUPREMA (Cocos/V8) via protocolo de REDE -> table_state genérico.

A Suprema fala com o servidor por WebSocket sobre TLS em JSON de TEXTO PURO (recon 20/11,
ver research/suprema_cocos/SUPREMA_PROTOCOL.md). Este módulo consome esses JSONs já
parseados (um por `feed_json`) e mantém o estado da mão VIVA, convertível no MESMO
`table_state` que `PreflopAdvisor.advise_from_reading` consome — decidido pelo MESMO
cérebro/roteamento/cobertura do PPPoker. Análogo a protobuf_state. READ-ONLY.

Schema (do recon):
  gameinfo.game_info: {dealer_seat, shared_cards:[int], pot, state}
  moveturn/prompt.game_seat: uid -> {seat, coins(=STACK atrás), cards, chips(=apostado), sitout, role}
      HERÓI = assento com `cards` de CÓDIGOS REAIS; oponente = null/[0,0] (oculto).
  prompt.gamer_prompt: {fold,check,call,raise,all_in,bet} — true(disp)/null(não)/string-range(raise).
  carta: decode REAL = rank=code%16 (2..14), suit=code//16 (1..4) — provado 31/31 showdowns
  (ver nvt-suprema-cartas-maior-59). NÃO é rank*4+suit (scheme antigo lia rank E naipe errados).
  STACK = coins ; aposta = chips. bb em fichas vem da stake da mesa (bb_chips).
"""
from __future__ import annotations

from protobuf_state import assign_positions, _CORE

ROLE_SB, ROLE_BB = 82, 93        # roles do stream na POSTAGEM (ancoram o cross-check de posição)


def _positions_from_blinds(ids, sb_seat, bb_seat):
    """Posições ANCORADAS nos BLINDS VERDADEIROS (role 82/93 do stream = verdade terreno),
    imune a assento vazio/dealer mal-lido (bug 24/11: vazio deslocava a posição -> a SB que
    completa 1bb era mal-rotulada e virava LIMPER FANTASMA -> open 2x inflava p/ 3x no first-in).
    SB=sb_seat (1º, sentido horário por índice de assento), BB logo após; BTN por último.
    Devolve {} se inconsistente (o caller cai no assign_positions por dealer / abstém)."""
    ids = sorted(set(ids))
    n = len(ids)
    if n < 2 or n > 9 or sb_seat not in ids or bb_seat not in ids:
        return {}
    i = ids.index(sb_seat)
    order = ids[i:] + ids[:i]                      # SB 1º, horário, BTN por último
    if n >= 3 and order[1] != bb_seat:             # BB tem que ser o próximo ATIVO horário
        return {}
    labels = (('SB', 'BB') + _CORE[-n:-2]) if n > 2 else ('SB', 'BB')
    return dict(zip(order, labels))

_RANKS = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9',
          10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
# Naipe = code//16 ∈ {1,2,3,4}. LETRAS CONFIRMADAS AO VIVO (22/11, leitura sincronizada e
# ANCORADA no hero_uid): 1=♦ (4♦ em K♣4♦), 2=♣ (K♣), 3=♥ (3♥ em J♠3♥), 4=♠ (J♠); reforçado
# por um showdown de FLUSH todo naipe 2. rank=code%16 também confirmado ao vivo (K,4,J,3).
# Nada mais provisório.
_SUITS = {1: 'd', 2: 'c', 3: 'h', 4: 's'}


def decode_card(code):
    """Código int da Suprema -> 'As'/'Td'/... ; None se oculto/inválido ([0,0], null).
    Encoding REAL: rank=code%16 (2..14), suit=code//16 (1..4). Provado 31/31 showdowns
    (ver nvt-suprema-cartas-maior-59). Os códigos antes tidos como '>59 revelados' são só o
    naipe 4 — cartas normais. Fora da faixa (rank/suit inválidos) = None (nunca chuta)."""
    if not isinstance(code, int) or code <= 0:
        return None                     # 0 / [0,0] / null = carta oculta
    rank, suit = code % 16, code // 16
    if rank in _RANKS and suit in _SUITS:
        return _RANKS[rank] + _SUITS[suit]
    return None


def decode_cards(codes):
    """Lista de códigos -> lista de strings; descarta ocultas. [0,0]/null viram []."""
    if not isinstance(codes, list):
        return []
    out = [decode_card(c) for c in codes]
    return [c for c in out if c]


UNKNOWN_CARD = '??'


def decode_board(codes):
    """Board DECODIFICADO POR POSIÇÃO: carta real quando decodifica; '??' (DESCONHECIDA, NÃO
    chutada) p/ código oculto/inválido. Preserva a CONTAGEM de cartas
    da rua — sem isso o board fica curto, o emissor PULA turn/river e DROPA o betting -> a mão
    não fecha o saldo (chip_imbalance) e é rejeitada do banco. Ver nvt-suprema-net-hook-funciona."""
    if not isinstance(codes, list):
        return []
    return [decode_card(c) or UNKNOWN_CARD for c in codes]


def parse_raise_range(s):
    """'range,4000,27900,2X,4000,3X,8000,4X,12000' -> {min, max, presets:{'2X':4000,...}}.
    Devolve None se não for string de range."""
    if not isinstance(s, str) or not s.startswith('range'):
        return None
    parts = s.split(',')
    out = {'min': None, 'max': None, 'presets': {}}
    try:
        out['min'] = float(parts[1]); out['max'] = float(parts[2])
    except (IndexError, ValueError):
        pass
    i = 3
    while i + 1 < len(parts):
        try:
            out['presets'][parts[i]] = float(parts[i + 1])
        except ValueError:
            pass
        i += 2
    return out


def parse_prompt(gp):
    """gamer_prompt -> {actions:set(acoes legais), call_amount, raise_range}. true=disponível,
    null=não, string=range (raise). Vazio se nenhuma ação (não é a vez do herói)."""
    out = {'actions': set(), 'call_amount': None, 'raise_range': None}
    if not isinstance(gp, dict):
        return out
    for act, v in gp.items():
        if v is None:
            continue
        if act in ('raise', 'bet') and isinstance(v, str):
            # PÓS-FLOP usa a chave 'bet' (sem aposta anterior) com presets de POTE
            # (1/2 POT, 2/3 POT, 1 POT); pré/facing-bet usa 'raise' (2X/3X/4X). Ambos são
            # string de range -> alimentam raise_range (o executor clica o mesmo botão Apostar/Aumentar).
            out['actions'].add(act); out['raise_range'] = parse_raise_range(v)
        elif act == 'call' and isinstance(v, (int, float)) and not isinstance(v, bool):
            # CUIDADO: em Python isinstance(True, int) é True. A Suprema manda call=True
            # (booleano = "pode pagar"), NÃO o valor. Tratar True como número dava
            # call_amount=1.0 -> to_call=0.0bb (bug 21/11). Booleano cai no ramo genérico
            # abaixo (vira ação legal) e o to_call é DERIVADO das apostas.
            out['actions'].add('call'); out['call_amount'] = float(v)
        elif v is True or isinstance(v, (int, float, str, dict)):
            out['actions'].add(act)
    return out


class SupremaTable:
    """Estado vivo de UMA mesa da Suprema, alimentado por mensagens JSON via `feed_json`."""

    def __init__(self, bb_chips=None, hero_uid=None):
        self.bb_chips = bb_chips          # fichas por BIG BLIND (stake da mesa)
        self.hero_uid = hero_uid          # uid do herói (da raiz da msg; ID definitivo)
        self.reset()

    def reset(self):
        self.players = {}                 # seat -> {coins, chips, cards[str], sitout, uid}
        self.bb_live = None               # BB em fichas LIDO do gamestart (auto-ajusta por nível)
        self._counter = None              # game_counter da mão atual (p/ não resetar em gamestart redundante)
        self._hand_seats = set()          # assentos DISTRIBUÍDOS nesta mão (posição estável, não desliza ao foldar)
        self.dealer_seat = None
        self.board = []
        self.pot_chips = None
        self.state = None
        self.hero_seat = None
        self.prompt = {'actions': set(), 'call_amount': None, 'raise_range': None}
        self.mtt = {}                     # contexto do torneio lido do game_info (p/ ICM + bounty)
        self.mtt_bb = None                # BB EXATO do game_info.blinds (autoridade sobre role-derive)
        self._street_bet = {}             # por RUA pós-flop (3/4/5): max chips_round visto = detecta check-check (villain_line)

    def _reset_hand(self):
        """Nova mão: zera cartas/board/pot/prompt (mantém bb, hero_uid e os stacks)."""
        for p in self.players.values():
            p['cards'] = []
        self.board, self.pot_chips, self.state, self.hero_seat = [], None, None, None
        self.prompt = {'actions': set(), 'call_amount': None, 'raise_range': None}
        self._hand_seats = set()          # nova mão: reconta os assentos distribuídos
        # INICIATIVA: quem fez o último RAISE pré-flop = agressor pré-flop. Dá a iniciativa ao
        # pós-flop (destrava c-bet-range/barril/ataque-scare, que são gated em aggressor='hero').
        self.preflop_aggressor_seat = None
        self._pf_max_bet = 0.0
        self._street_bet = {}             # zera o rastro de ação pós-flop por rua
        # BLINDS REAIS do stream (role 82=SB, 93=BB no gamestart): ancoram o cross-check de posição
        # p/ o assign_positions não deslocar (bug 24/11: assento vazio -> BB mal-rotulado -> o post
        # de 1bb virava LIMPER FANTASMA -> open 2x inflava p/ iso 3x no first-in).
        self.sb_seat = None
        self.bb_seat = None

    # ---- ingestão ----
    def feed_json(self, msg):
        """Consome UMA mensagem JSON já parseada ({route,uid?,event,data,...}). Ignora ruído."""
        if not isinstance(msg, dict):
            return
        # uid na RAIZ da mensagem = o herói (a quem o servidor endereça o prompt/cartas).
        if msg.get('uid') is not None:
            self.hero_uid = msg['uid']
        ev = msg.get('event')
        data = msg.get('data') or {}
        if ev == 'gamestart':
            # Só reseta a mão quando o game_counter MUDA (mão nova). A Suprema manda
            # gamestart REDUNDANTE em rajada (counter=None e repetidos); resetar nesses
            # APAGAVA as cartas do herói já recebidas no prompt de 'deal' -> a vez chegava
            # sem cartas -> HERO_CARDS_UNKNOWN -> abstenção (bug 21/11). Mesma regra do builder.
            c = (data.get('game_info') or {}).get('game_counter')
            if c is not None and c != self._counter:
                self._counter = c
                self._reset_hand()
            self._update_blinds(data.get('game_seat'))
        if ev == 'gameinfo':
            self._gameinfo(data.get('game_info') or {})
        if isinstance(data.get('kodata'), list):
            self._kodata(data['kodata'])
        elif ev in ('moveturn', 'prompt'):
            if isinstance(data.get('game_seat'), dict):
                self._seats(data['game_seat'])
        if ev == 'prompt' and isinstance(data.get('gamer_prompt'), dict):
            self.prompt = parse_prompt(data['gamer_prompt'])
        if ev in ('gameover', 'handover', 'gameResult', 'settle'):
            self.board, self.pot_chips, self.state = [], None, None
            self.prompt = {'actions': set(), 'call_amount': None, 'raise_range': None}

    def _kodata(self, kd):
        """Eventos de KO: `reward` = metade da CABEÇA da vítima (cash ganho). A menor reward vista
        = KO de cabeça FRESCA -> base da cabeça do torneio = 2×min(reward). (O campo seat.bounty é
        o cash ACUMULADO, 0 p/ fresco; a CABEÇA de um jogador = base + acumulado.)"""
        for e in kd:
            if not isinstance(e, dict):
                continue
            r = e.get('reward')
            if isinstance(r, (int, float)) and r > 0:
                prev = self.mtt.get('_min_reward')
                if prev is None or r < prev:
                    self.mtt['_min_reward'] = float(r)
                    self.mtt['bounty_base'] = round(2.0 * float(r), 4)

    def _gameinfo(self, gi):
        if gi.get('dealer_seat') is not None:
            self.dealer_seat = gi['dealer_seat']
        if isinstance(gi.get('shared_cards'), list):
            nb = decode_cards(gi['shared_cards'])
            if len(nb) >= len(self.board):   # board só CRESCE na mão: ignora leitura PARCIAL do flop (2 de 3)
                self.board = nb
        if isinstance(gi.get('pot'), (int, float)):
            self.pot_chips = float(gi['pot'])
        if gi.get('state') is not None:
            self.state = gi['state']
        # Contexto MTT: BB EXATO + dados de ICM/bounty (vivos, pagos, avgStack, nível, tipo).
        # blinds = big blind (fichas); autoridade sobre a derivação por role.
        if isinstance(gi.get('blinds'), (int, float)) and gi['blinds'] > 0:
            self.mtt_bb = float(gi['blinds'])
        for src, dst in (('smallblinds', 'sb'), ('blinds', 'bb'), ('blindsLevel', 'level'),
                         ('avgStack', 'avg_stack'), ('playerCount', 'players_left'),
                         ('totalPlayerCount', 'players_total'), ('mttprizecount', 'places_paid'),
                         ('rebuy', 'rebuys'), ('addon', 'addons'), ('remainTables', 'tables_left'),
                         ('type', 'type'), ('nextAnteFix', 'next_ante')):
            if gi.get(src) is not None:
                self.mtt[dst] = gi[src]
        # STACK INICIAL detectado NO COMEÇO: o avgStack é MÍNIMO no início (antes dos bustes
        # elevarem a média); no nível 1 sem bustes, avgStack == stack inicial EXATO. Guarda o
        # MENOR avgStack visto + o nível em que ocorreu (ss_level=1 => exato). Reseta em novo torneio.
        av = gi.get('avgStack')
        if isinstance(av, (int, float)) and av > 0:
            cur = self.mtt.get('starting_stack')
            if cur is None or av < cur:
                self.mtt['starting_stack'] = float(av)
                self.mtt['ss_level'] = gi.get('blindsLevel')
        if isinstance(gi.get('game_seat'), dict):
            self._seats(gi['game_seat'])

    def _seats(self, game_seat):
        # Quantos assentos têm 2 cartas REAIS face-up AGORA. Em jogo normal só o HERÓI mostra
        # cartas (=1); num all-in/showdown os vilões viram face-up (>1). Guard do fallback sem
        # uid: só ancora o herói quando há UMA mão face-up — senão um reveal SEQUESTRARIA o
        # hero_seat p/ um vilão (bug: li KK de vilão em all-in vs AK antes do 1º prompt).
        revealed = sum(1 for _s, q in game_seat.items()
                       if isinstance(q, dict) and len(decode_cards(q.get('cards') or [])) == 2)
        for _uid, p in game_seat.items():
            if not isinstance(p, dict):
                continue
            seat = p.get('seat')
            if seat is None:
                continue
            self._hand_seats.add(seat)     # distribuído nesta mão (p/ posição não deslizar quando gente folda)
            cards = decode_cards(p.get('cards') or [])
            rec = self.players.setdefault(seat, {})
            uid = p.get('uid')
            if uid is not None:
                rec['uid'] = uid
            if isinstance(p.get('coins'), (int, float)):
                rec['coins'] = float(p['coins'])
            if isinstance(p.get('chips'), (int, float)):
                rec['chips'] = float(p['chips'])
            if isinstance(p.get('chips_round'), (int, float)):
                rec['chips_round'] = float(p['chips_round'])   # aposta da RUA (reseta por street)
                # INICIATIVA PRÉ-FLOP: o ÚLTIMO a raisar (chips_round acima do BB e do topo visto
                # nesta mão) é o agressor pré-flop -> iniciativa no pós-flop. Só no pré (board vazio;
                # no pós o chips_round é da rua corrente e não deve sobrescrever a iniciativa).
                if not self.board:
                    _bbv = self.bb()
                    _cr = rec['chips_round']
                    if _bbv and _cr > _bbv + 1e-9 and _cr > getattr(self, '_pf_max_bet', 0.0) + 1e-9:
                        self._pf_max_bet = _cr
                        self.preflop_aggressor_seat = seat
                else:
                    # PÓS-FLOP (Eduardo 24/11): rastreia a aposta da RUA p/ derivar villain_line
                    # (probe/delayed/bet-check-bet). chips_round reseta por rua, então max==0 no fim
                    # da rua = CHECK-CHECK (confiável). `first` = 1º assento visto pondo fichas na rua
                    # (bettor/agressor da rua) — usado só p/ o bet-check-bet.
                    _st = len(self.board)                 # 3=flop, 4=turn, 5=river
                    _cr = rec['chips_round']
                    _sb = self._street_bet.setdefault(_st, {'max': 0.0, 'first': None})
                    if _cr > 1e-9:
                        if _cr > _sb['max'] + 1e-9:
                            _sb['max'] = _cr
                        if _sb['first'] is None:
                            _sb['first'] = seat
            # BOUNTY PKO: valor CRU da cabeça (unidade escalada do stream; a TELA mostra em
            # fichas) + nº de KOs do jogador. A conversão cru->fichas é calibrada na tela
            # (suprema_bounty.BOUNTY_CHIP_SCALE). Guarda o cru aqui; a matemática fica fora.
            if isinstance(p.get('bounty'), (int, float)):
                rec['bounty_raw'] = float(p['bounty'])
            if isinstance(p.get('ko'), (int, float)):
                rec['ko'] = int(p['ko'])
            if 'sitout' in p:
                rec['sitout'] = bool(p.get('sitout'))
            rec['role'] = p.get('role')
            if len(cards) == 2:                 # cartas reais presentes -> guarda (persistem na mão)
                rec['cards'] = cards
            elif 'cards' not in rec:
                rec['cards'] = []
            # HERÓI: assento do hero_uid (DEFINITIVO). O fallback por "2 cartas reais" vale SÓ
            # enquanto o uid é DESCONHECIDO — senão uma REVELAÇÃO de oponente (showdown/all-in)
            # SEQUESTRA o hero_seat e o Henrique lê a mão do vilão (bug 21/11: tinha 8d3c, leu 6d8s).
            if self.hero_uid is not None:
                if uid == self.hero_uid:
                    self.hero_seat = seat
            elif len(cards) == 2 and revealed == 1:
                self.hero_seat = seat

    def _update_blinds(self, game_seat):
        """Lê o BB (em fichas) do gamestart: role 93 = BIG BLIND, role 0 = ante; bb = chips do
        BB menos o ante (igual ao suprema_hand_builder). Atualiza self.bb_live só com valor
        positivo (mantém o último bom) — assim o BB acompanha o aumento de nível sozinho."""
        if not isinstance(game_seat, dict):
            return
        by_role = {}
        for _u, p in game_seat.items():
            if isinstance(p, dict) and p.get('seat') is not None:
                by_role.setdefault(p.get('role'), []).append(float(p.get('chips') or 0))
                # captura o assento do SB (82) e BB (93) na POSTAGEM (set-once por mão) p/ ancorar
                # o cross-check de posição. Os roles mudam quando o jogador age, então pega o 1º.
                if p.get('role') == ROLE_SB and self.sb_seat is None:
                    self.sb_seat = p['seat']
                elif p.get('role') == ROLE_BB and self.bb_seat is None:
                    self.bb_seat = p['seat']
        ante = min(by_role[0]) if by_role.get(0) else 0.0
        bb_chips = by_role.get(93)                      # role 93 = BB
        if bb_chips:
            bb = max(bb_chips) - ante
            if bb > 0:
                self.bb_live = bb

    # ---- conversão p/ o cérebro ----
    def bb(self):
        # BB EXATO do game_info.blinds tem prioridade máxima (autoridade); depois o derivado
        # por role do gamestart; por fim a semente bb_chips.
        if isinstance(self.mtt_bb, (int, float)) and self.mtt_bb > 0:
            return float(self.mtt_bb)
        if isinstance(self.bb_live, (int, float)) and self.bb_live > 0:
            return float(self.bb_live)
        if isinstance(self.bb_chips, (int, float)) and self.bb_chips > 0:
            return float(self.bb_chips)
        return None

    def active_seats(self):
        return [s for s, p in self.players.items() if not p.get('sitout')]

    def legal_actions(self):
        """Ações legais do herói na vez atual (p/ a EXECUÇÃO/Fase 2). Vazio = não é a vez."""
        return set(self.prompt.get('actions') or set())

    def to_table_state(self):
        """(table_state, hero_cards) p/ advise_from_reading, ou (None, motivo)."""
        bb = self.bb()
        if bb is None:
            return None, 'BB_DESCONHECIDO'
        active = self.active_seats()
        # SIT-OUT (LEI Eduardo, nvt-regra-sitout-nunca-walk): o jogador SIT-OUT sai dos ATIVOS
        # (auto-folda a blind), mas a MÃO ainda existe — p/ o override "nunca dar WALK a sit-out"
        # o estado precisa ser montado mesmo num blind-war onde o(s) defensor(es) estão TODOS
        # sit-out (active cai a 1). Conta os sit-out NO gate de nº de jogadores.
        sitout_others = [s for s, p in self.players.items()
                         if p.get('sitout') and s != self.hero_seat]
        in_hand = set(active) | set(sitout_others)
        if self.hero_seat is not None:
            in_hand.add(self.hero_seat)
        if len(in_hand) < 2:
            return None, 'POUCOS_JOGADORES'
        if self.hero_seat is None or self.hero_seat not in self.players:
            return None, 'HERO_CARDS_UNKNOWN'
        hero_cards = list(self.players[self.hero_seat].get('cards') or [])
        if len(hero_cards) != 2:
            return None, 'HERO_CARDS_UNKNOWN'
        if self.hero_seat not in active:
            active.append(self.hero_seat)
        # Posição ANCORADA nos assentos DISTRIBUÍDOS na mão (união monotônica), não nos
        # ATIVOS do momento: senão o rótulo DESLIZA quando gente folda (BB virava SB na rua).
        # inclui os ATIVOS no conjunto de posições (senão um assento ativo que não entrou em
        # _hand_seats fica sem posição -> KeyError, engolido pelo run_live -> decisão some).
        dealt = sorted(self._hand_seats | set(active) | set(sitout_others) | {self.hero_seat})
        # POSIÇÃO ancorada nos BLINDS VERDADEIROS (role 82/93) primeiro — imune a assento vazio/
        # dealer mal-lido (mata o limper fantasma -> open 3x do first-in). Só cai no assign_positions
        # (dealer) se os blinds forem desconhecidos/inconsistentes; esse ainda cross-checa o BB.
        _sbs, _bbs = getattr(self, 'sb_seat', None), getattr(self, 'bb_seat', None)
        pos_by_seat = (_positions_from_blinds(dealt, _sbs, _bbs)
                       or assign_positions(dealt, self.dealer_seat, _sbs, _bbs))
        if not pos_by_seat or self.hero_seat not in pos_by_seat:
            return None, 'POSICOES_INCONSISTENTES'

        def key(seat):
            return 'hero' if seat == self.hero_seat else 'seat%s' % seat

        positions, seats, bets = {}, {}, []
        for seat in active:
            if seat not in pos_by_seat:          # guarda à prova de KeyError (nunca estoura a decisão)
                continue
            p = self.players[seat]
            k = key(seat)
            positions[k] = pos_by_seat[seat]
            coins = p.get('coins')
            seats[k] = dict(stack_bb=(coins / bb if isinstance(coins, (int, float)) else None),
                            occupied=True, source='suprema', sitout=bool(p.get('sitout')),
                            bounty_raw=p.get('bounty_raw'), ko=p.get('ko'))
            # bet da RUA = chips_round (reseta por street -> to_call certo no PÓS-FLOP);
            # fallback p/ chips quando chips_round ausente (pré-flop o ante cancela, dá igual).
            _cr = p.get('chips_round')
            _bet = float(_cr if isinstance(_cr, (int, float)) else (p.get('chips') or 0.0))
            bets.append(dict(seat=k, bet_bb=round(_bet / bb, 4)))

        n = len(self.board)
        street = ('RIVER' if n >= 5 else 'TURN' if n == 4 else 'FLOP' if n == 3 else 'PREFLOP')
        # to_call: prioriza o valor EXATO do prompt (a vez do herói); senão deriva das apostas.
        if isinstance(self.prompt.get('call_amount'), (int, float)):
            to_call_bb = round(self.prompt['call_amount'] / bb, 2)
        else:
            max_bet = max((b['bet_bb'] for b in bets), default=0.0)
            hero_bet = next((b['bet_bb'] for b in bets if b['seat'] == 'hero'), 0.0)
            to_call_bb = round(max(0.0, max_bet - hero_bet), 2)
        pot_bb = (round(self.pot_chips / bb, 2) if isinstance(self.pot_chips, (int, float)) else None)
        # SIT-OUT exposto SEM quebrar posição: posições dos VILÕES sit-out ainda na mão (os
        # ATIVOS/`positions` seguem só com os não-sit-out, p/ não alterar o que o cérebro vê no
        # multiway). `sitout_positions` alimenta o override "nunca dar WALK a sit-out"; `hero_sitout`
        # é o flag do PRÓPRIO hero (p/ log/tratamento posterior).
        sitout_positions = sorted({pos_by_seat[s] for s in sitout_others if s in pos_by_seat})
        hero_sitout = bool(self.players.get(self.hero_seat, {}).get('sitout'))
        # INICIATIVA + TIPO DE POTE p/ o pós-flop: resolve o agressor pré-flop (assento->rótulo
        # 'hero'/posição) e marca multiway. Sem isto o advise_postflop recebia aggressor=None ->
        # _hia=None -> TODO o motor de c-bet-range/barril/ataque-scare ficava morto -> passivão.
        _pfa = getattr(self, 'preflop_aggressor_seat', None)
        aggressor = ('hero' if _pfa == self.hero_seat else pos_by_seat.get(_pfa)) if _pfa is not None else None
        pot_type = 'multiway' if len(in_hand) > 2 else None
        # VILLAIN_LINE (Eduardo 24/11): deriva a LINHA pós-flop p/ LIGAR probe/delayed/bet-check-bet
        # (antes ficavam MORTAS ao vivo: villain_line=None). Base = CHECK-CHECK por rua (max
        # chips_round==0, confiável pois reseta por rua) + quem foi o PFR. Conservador: só seta no
        # padrão CLARO; senão None (comportamento atual). HU só (multiway não entra nessas linhas).
        villain_line = None
        _sb = getattr(self, '_street_bet', {})
        # TRAVA ANTI-SPEW: só afirma "check-check" se a rua foi OBSERVADA (há entrada em _sb[rua]).
        # Se o estado nunca viu o flop (pulou pro turn), NÃO inventa checked_through -> villain_line
        # None (seguro). Idem o 'flop teve aposta' do bet-check-bet exige o flop observado com max>0.
        _flop_cc = (3 in _sb and _sb[3].get('max', 0.0) <= 1e-9)   # flop OBSERVADO e check-check
        _flop_bet = (3 in _sb and _sb[3].get('max', 0.0) > 1e-9)   # flop OBSERVADO com aposta
        _turn_cc = (4 in _sb and _sb[4].get('max', 0.0) <= 1e-9)   # turn OBSERVADO e check-check
        _hero_pfr = (_pfa is not None and _pfa == self.hero_seat)
        if len(in_hand) <= 2:                                      # só heads-up
            if street == 'TURN' and _flop_cc:
                # flop check-check: hero=PFR -> DELAYED c-bet; vilão=PFR (check back) -> PROBE
                villain_line = 'delayed' if _hero_pfr else 'checked_back'
            elif street == 'RIVER' and _hero_pfr and _flop_bet and _turn_cc:
                villain_line = 'checked_turn'                      # hero c-betou flop, checou turn -> valor fino
        state = dict(positions=positions, seats=seats, bets=bets, phase='mid',
                     source='suprema', room='SupremaPoker', hand_id=self._counter, bb_chips=bb,
                     scope=('POSTFLOP_SUPREMA' if n >= 3 else 'PREFLOP_SUPREMA'),
                     board=list(self.board), street=street, aggressor=aggressor, pot_type=pot_type,
                     villain_line=villain_line,
                     legal_actions=sorted(self.legal_actions()),
                     to_call={'to_call_bb': to_call_bb}, pot={'pot_bb': pot_bb},
                     sitout_positions=sitout_positions, hero_sitout=hero_sitout,
                     mtt=dict(self.mtt))
        return state, hero_cards


def advise_from_suprema(table, advisor, *, hunt_bounty=False, head_fraction=0.5,
                        starting_stack=None, **kwargs):
    """Decide a partir do estado vivo da Suprema, pelo MESMO roteamento do OCR/protobuf.
    `table` é um SupremaTable alimentado. Devolve o dict do advisor, ou {status:'ABSTAIN'}.

    BOUNTY PKO AUTO (hunt_bounty): em pko/pko_icm, calcula a CABEÇA (base+acumulado, lida do stream)
    por vilão via suprema_bounty e injeta no call-off do advisor — `state['bounties']={seat: head_bb}`
    + `bounty_bb`=cabeça fresca. Substitui o --bounty-bb MANUAL: o alvo bountiado curto que a gente
    cobre passa a precisar de MENOS equity (caça). Default off até validar ao vivo (LEI: não armar
    sem green)."""
    state, hero_or_reason = table.to_table_state()
    if state is None:
        return dict(status='ABSTAIN', reason=hero_or_reason, source='suprema')
    # PÓS-FLOP (board>=3): religa o MOTOR PÓS-FLOP (23/11). ANTES a Suprema decidia TODO pós-flop com
    # lógica PRÉ-FLOP (advise_from_reading) -> supervalorizava underpair (ex. QQ em K-alto virava
    # call-off premium -> perdeu ~50k, H2N #61). Espelha protobuf_state.advise_from_protobuf: board/
    # pote/to_call EXATOS do stream -> advise_postflop + postflop_sizing.enforce. SHADOW (validated=
    # False, heurístico) até homologar. Pré-flop segue idêntico (bounty/sitout são só pré-flop).
    board = state.get('board') or []
    if len(board) >= 3:
        from postflop_advisor import advise_postflop
        import postflop_sizing
        # CAMPO MOLE por STAGE (Eduardo 24/11): início (early/mid/pre_itm) = play money ruim que
        # SOBRE-blefa -> bluff-catch mais largo (paga o lixo deles). Bolha/reta final = ICM +
        # callstation value-heavy -> conservador. Modula o over-fold sem virar spew.
        _stage = kwargs.get('stage', 'mid')
        _soft = _stage in ('early', 'mid', 'pre_itm')
        advice = advise_postflop(state, hero_or_reason, board, street=state.get('street'),
                                 mode=kwargs.get('mode', 'chip_ev'), stage=_stage,
                                 aggressor=state.get('aggressor'), pot_type=state.get('pot_type'),
                                 villain_line=state.get('villain_line'),
                                 soft_field=_soft)
        if isinstance(advice, dict):
            _stk = (state.get('seats', {}).get('hero') or {}).get('stack_bb')
            postflop_sizing.enforce(advice, pot_bb=(state.get('pot') or {}).get('pot_bb'),
                                    stack_bb=_stk, spr=advice.get('spr'))
            advice['source'] = 'suprema_postflop'
            advice.setdefault('validated', False)       # heurístico -> shadow até homologar
            advice.setdefault('hero_cards', hero_or_reason)
        return advice
    if hunt_bounty and kwargs.get('mode') in ('pko', 'pko_icm'):
        try:
            import suprema_bounty
            hs = suprema_bounty.hunt(state, head_fraction=head_fraction, starting_stack=starting_stack)
            if hs.get('calibrated'):
                bts = {t['seat']: t['head_bb'] for t in hs.get('targets', []) if t.get('head_bb')}
                if bts:
                    state['bounties'] = bts                       # cabeça por vilão (BB-equiv)
                    kwargs.setdefault('bounty_bb', min(bts.values()))   # base = cabeça fresca
        except Exception:
            pass
    advice = advisor.advise_from_reading(state, hero_or_reason, **kwargs)
    # ALARGAR O OPEN pra caçar (bounded): em spot de open com alvo curto bountiado coberto, promove
    # fold->raise só se o GTO já abre a mão em freq mista. O call largo já veio do call-off.
    if hunt_bounty and kwargs.get('mode') in ('pko', 'pko_icm') and state.get('bounties'):
        try:
            import bounty_open
            advice = bounty_open.widen_open(advice, state)
        except Exception:
            pass
    # NUNCA dar WALK a um jogador SIT-OUT (LEI Eduardo, nvt-regra-sitout-nunca-walk): se a
    # recomendação é FOLD e o único caminho é ceder a blind a defensor(es) SIT-OUT (que
    # auto-foldam), promove fold->raise (ROUBA). Bounded; não mexe se há oponente ATIVO vivo.
    try:
        import sitout_steal
        advice = sitout_steal.never_walk_sitout(advice, state)
    except Exception:
        pass
    return advice
