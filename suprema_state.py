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
  carta = rank*4 + suit  (rank 2..14, suit 0..3)  -> decode: rank=code//4, suit=code%4.
  STACK = coins ; aposta = chips. bb em fichas vem da stake da mesa (bb_chips).
"""
from __future__ import annotations

from protobuf_state import assign_positions

_RANKS = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9',
          10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
# Bijeção de naipe (rótulo exato ♦♣♥♠ é indiferente p/ o cérebro — só importa IGUAL=flush,
# preservado por code%4; confirmar o rótulo no feltro quando interessar p/ relatório/HUD).
_SUITS = {0: 'd', 1: 'c', 2: 'h', 3: 's'}


def decode_card(code):
    """Código int da Suprema -> 'As'/'Td'/... ; None se oculto/ inválido ([0,0], null)."""
    if not isinstance(code, int) or code < 8:
        return None                     # 0 / [0,0] / null = carta oculta
    rank, suit = code // 4, code % 4
    if rank not in _RANKS:
        return None
    return _RANKS[rank] + _SUITS[suit]


def decode_cards(codes):
    """Lista de códigos -> lista de strings; descarta ocultas. [0,0]/null viram []."""
    if not isinstance(codes, list):
        return []
    out = [decode_card(c) for c in codes]
    return [c for c in out if c]


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
        if act == 'raise' and isinstance(v, str):
            out['actions'].add('raise'); out['raise_range'] = parse_raise_range(v)
        elif act == 'call' and isinstance(v, (int, float)):
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
        self.dealer_seat = None
        self.board = []
        self.pot_chips = None
        self.state = None
        self.hero_seat = None
        self.prompt = {'actions': set(), 'call_amount': None, 'raise_range': None}

    def _reset_hand(self):
        """Nova mão: zera cartas/board/pot/prompt (mantém bb, hero_uid e os stacks)."""
        for p in self.players.values():
            p['cards'] = []
        self.board, self.pot_chips, self.state, self.hero_seat = [], None, None, None
        self.prompt = {'actions': set(), 'call_amount': None, 'raise_range': None}

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
            self._reset_hand()
        if ev == 'gameinfo':
            self._gameinfo(data.get('game_info') or {})
        elif ev in ('moveturn', 'prompt'):
            if isinstance(data.get('game_seat'), dict):
                self._seats(data['game_seat'])
        if ev == 'prompt' and isinstance(data.get('gamer_prompt'), dict):
            self.prompt = parse_prompt(data['gamer_prompt'])
        if ev in ('gameover', 'handover', 'gameResult', 'settle'):
            self.board, self.pot_chips, self.state = [], None, None
            self.prompt = {'actions': set(), 'call_amount': None, 'raise_range': None}

    def _gameinfo(self, gi):
        if gi.get('dealer_seat') is not None:
            self.dealer_seat = gi['dealer_seat']
        if isinstance(gi.get('shared_cards'), list):
            self.board = decode_cards(gi['shared_cards'])
        if isinstance(gi.get('pot'), (int, float)):
            self.pot_chips = float(gi['pot'])
        if gi.get('state') is not None:
            self.state = gi['state']
        if isinstance(gi.get('game_seat'), dict):
            self._seats(gi['game_seat'])

    def _seats(self, game_seat):
        for _uid, p in game_seat.items():
            if not isinstance(p, dict):
                continue
            seat = p.get('seat')
            if seat is None:
                continue
            cards = decode_cards(p.get('cards') or [])
            rec = self.players.setdefault(seat, {})
            uid = p.get('uid')
            if uid is not None:
                rec['uid'] = uid
            if isinstance(p.get('coins'), (int, float)):
                rec['coins'] = float(p['coins'])
            if isinstance(p.get('chips'), (int, float)):
                rec['chips'] = float(p['chips'])
            if 'sitout' in p:
                rec['sitout'] = bool(p.get('sitout'))
            rec['role'] = p.get('role')
            if len(cards) == 2:                 # cartas reais presentes -> guarda (persistem na mão)
                rec['cards'] = cards
            elif 'cards' not in rec:
                rec['cards'] = []
            # HERÓI: pelo uid da raiz (definitivo); fallback = assento com 2 cartas reais.
            if (self.hero_uid is not None and uid == self.hero_uid) or len(cards) == 2:
                self.hero_seat = seat

    # ---- conversão p/ o cérebro ----
    def bb(self):
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
        if len(active) < 2:
            return None, 'POUCOS_JOGADORES'
        if self.hero_seat is None or self.hero_seat not in self.players:
            return None, 'HERO_CARDS_UNKNOWN'
        hero_cards = list(self.players[self.hero_seat].get('cards') or [])
        if len(hero_cards) != 2:
            return None, 'HERO_CARDS_UNKNOWN'
        if self.hero_seat not in active:
            active.append(self.hero_seat)
        pos_by_seat = assign_positions(active, self.dealer_seat, None, None)
        if not pos_by_seat or self.hero_seat not in pos_by_seat:
            return None, 'POSICOES_INCONSISTENTES'

        def key(seat):
            return 'hero' if seat == self.hero_seat else 'seat%s' % seat

        positions, seats, bets = {}, {}, []
        for seat in active:
            p = self.players[seat]
            k = key(seat)
            positions[k] = pos_by_seat[seat]
            coins = p.get('coins')
            seats[k] = dict(stack_bb=(coins / bb if isinstance(coins, (int, float)) else None),
                            occupied=True, source='suprema')
            bets.append(dict(seat=k, bet_bb=round(float(p.get('chips') or 0.0) / bb, 4)))

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
        state = dict(positions=positions, seats=seats, bets=bets, phase='mid',
                     source='suprema', room='SupremaPoker',
                     scope=('POSTFLOP_SUPREMA' if n >= 3 else 'PREFLOP_SUPREMA'),
                     board=list(self.board), street=street,
                     legal_actions=sorted(self.legal_actions()),
                     to_call={'to_call_bb': to_call_bb}, pot={'pot_bb': pot_bb})
        return state, hero_cards


def advise_from_suprema(table, advisor, **kwargs):
    """Decide a partir do estado vivo da Suprema, pelo MESMO roteamento do OCR/protobuf.
    `table` é um SupremaTable alimentado. Devolve o dict do advisor, ou {status:'ABSTAIN'}."""
    state, hero_or_reason = table.to_table_state()
    if state is None:
        return dict(status='ABSTAIN', reason=hero_or_reason, source='suprema')
    return advisor.advise_from_reading(state, hero_or_reason, **kwargs)
