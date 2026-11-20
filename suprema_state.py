"""Percepção AO VIVO da SUPREMA (Cocos/V8) via STREAM DE EVENTOS -> table_state genérico.

Acumula os eventos NVT emitidos pelo JS do jogo (contrato em
research/suprema_cocos/inject_emit.js: seat / round_start / hand_card / action /
winner / hand_over) e mantém o estado da mão VIVA, convertível no MESMO `table_state`
que `PreflopAdvisor.advise_from_reading` consome — decidido pelo MESMO cérebro/roteamento
do PPPoker. É o análogo de `protobuf_state`, mas por STREAM de eventos (não snapshot de
memória). READ-ONLY: nenhuma ação aqui.

Reúsa `protobuf_state.assign_positions` (ancoragem no BOTÃO) para rotular posições, e a
conversão por BIG BLIND. As cartas chegam como STRING ('As','Kd') — formato nativo do
cérebro (sem round-trip de encoding).

FASE 1 (percepção, offline): este módulo é testável 100% offline com fixtures de eventos
(test_suprema_state). A fiação AO VIVO (inject_emit.js plugar os hooks reais do spp/
WebSocket + o runner) é a Fase 1b, que PRECISA de recon no cliente aberto — ver
research/suprema_cocos/FINDINGS_SUPREMA.md. ZERO clique nesta fase.

PONTOS A CONFIRMAR NO RECON AO VIVO (marcados no código):
  - semântica de `action.chips`: INCREMENTO da rua vs TOTAL comprometido (assumo incremento);
  - quais assentos estão DEALT na mão (assumo todos os sentados c/ stack; a Suprema pode
    ter sit-out) — idealmente o 'seat'/'round_start' trazer essa marca.
"""
from __future__ import annotations

import ppp_actions
from protobuf_state import assign_positions


class SupremaTable:
    """Estado vivo de UMA mesa da Suprema, alimentado por eventos NVT via `feed`."""

    def __init__(self):
        self.reset_hand()

    def reset_hand(self):
        self.players = {}        # seat(int) -> {name, stack(fichas), bet(fichas, rua atual), cards[str], dealt}
        self.button = None       # assento do botão (round_start.button_seat)
        self.sb_chips = None     # small blind em fichas (round_start.cur_blind)
        self.board = []          # cartas comunitárias (strings)
        self.hero_seat = None
        self.stage = 1           # 1=preflop 2=flop 3=turn 4=river
        self.hand_id = None
        self.pot_carry = 0.0     # fichas apostadas em ruas ANTERIORES (fechadas)

    # ---- ingestão de eventos --------------------------------------------------
    def feed(self, ev):
        """Consome um evento NVT (dict com chave 't'). Ignora o que não reconhece."""
        if not isinstance(ev, dict):
            return
        t = ev.get('t')
        if t == 'seat':
            self._seat(ev)
        elif t == 'round_start':
            self._round_start(ev)
        elif t == 'hand_card':
            self._hand_card(ev)
        elif t == 'action':
            self._action(ev)
        elif t == 'hand_over':
            self.reset_hand()
        # 'ante'/'winner' não afetam a decisão viva pré-ação; ignorados aqui.

    def _p(self, seat):
        return self.players.setdefault(seat, dict(name=None, stack=None, bet=0.0,
                                                  cards=[], dealt=False))

    def _seat(self, ev):
        seat = ev.get('seat')
        if seat is None:
            return
        p = self._p(seat)
        if ev.get('player') is not None:
            p['name'] = ev.get('player')
        if isinstance(ev.get('stack'), (int, float)):
            p['stack'] = float(ev['stack'])
        p['dealt'] = True        # RECON: confirmar sit-out; por ora sentado = na mão

    def _round_start(self, ev):
        stage = ev.get('stage')
        # NOVA RUA: fecha as apostas da rua anterior no pote e zera os bets da rua nova.
        if isinstance(stage, int):
            if stage != self.stage:
                self.pot_carry += sum(p['bet'] for p in self.players.values())
                for p in self.players.values():
                    p['bet'] = 0.0
            self.stage = stage
        if isinstance(ev.get('cur_blind'), (int, float)) and ev['cur_blind'] > 0:
            self.sb_chips = float(ev['cur_blind'])
        if ev.get('button_seat') is not None:
            self.button = ev['button_seat']
        if ev.get('hand_id') is not None:
            self.hand_id = ev['hand_id']
        if isinstance(ev.get('board'), list):
            self.board = [c for c in ev['board'] if isinstance(c, str)]
        # cartas do herói podem vir no round_start OU no hand_card
        hc = ev.get('hero_cards')
        if isinstance(hc, list) and len(hc) == 2 and self.hero_seat is not None:
            self._p(self.hero_seat)['cards'] = [c for c in hc if isinstance(c, str)]

    def _hand_card(self, ev):
        seat = ev.get('seat')
        cards = ev.get('cards')
        if seat is None or not isinstance(cards, list):
            return
        p = self._p(seat)
        p['cards'] = [c for c in cards if isinstance(c, str)]
        p['dealt'] = True
        if len(p['cards']) == 2:          # o único assento com 2 cartas FACE-UP = herói
            self.hero_seat = seat

    def _action(self, ev):
        seat = ev.get('seat')
        if seat is None:
            return
        p = self._p(seat)
        p['dealt'] = True
        atype = ev.get('atype')
        chips = ev.get('chips')
        # RECON: assumo `chips` = INCREMENTO investido nesta ação (blind/call/aposta).
        if isinstance(chips, (int, float)) and chips > 0:
            p['bet'] = round(p['bet'] + float(chips), 4)
        if ev.get('all_in'):
            p['all_in'] = True
        if isinstance(ev.get('hand_chips'), (int, float)):
            p['stack'] = float(ev['hand_chips'])     # stack REMANESCENTE após a ação
        if atype == 1:                                # fold: sai da mão
            p['dealt'] = False

    # ---- conversão para o cérebro --------------------------------------------
    def bb(self):
        """Fichas por BIG BLIND = 2*small blind. None se desconhecido."""
        if isinstance(self.sb_chips, (int, float)) and self.sb_chips > 0:
            return 2.0 * self.sb_chips
        return None

    def to_table_state(self):
        """(table_state, hero_cards) pronto p/ advise_from_reading, ou (None, motivo).

        Mesma semântica de abstenção do protobuf_state: sem BB, sem herói com 2 cartas, ou
        posições inconsistentes -> (None, motivo) e o chamador ABSTÉM (não chuta)."""
        bb = self.bb()
        if bb is None:
            return None, 'SB_DESCONHECIDO'
        active = [s for s, p in self.players.items() if p.get('dealt')]
        if len(active) < 2:
            return None, 'POUCOS_JOGADORES'
        if self.hero_seat is None:
            return None, 'HERO_CARDS_UNKNOWN'
        hero = self.players.get(self.hero_seat) or {}
        hero_cards = list(hero.get('cards') or [])
        if len(hero_cards) != 2:
            return None, 'HERO_CARDS_UNKNOWN'
        if self.hero_seat not in active:
            active.append(self.hero_seat)
        pos_by_seat = assign_positions(active, self.button, None, None)
        if not pos_by_seat or self.hero_seat not in pos_by_seat:
            return None, 'POSICOES_INCONSISTENTES'

        def key(seat):
            return 'hero' if seat == self.hero_seat else 'seat%s' % seat

        positions, seats, bets = {}, {}, []
        for seat in active:
            p = self.players[seat]
            k = key(seat)
            positions[k] = pos_by_seat[seat]
            stack = p.get('stack')
            seats[k] = dict(stack_bb=(float(stack) / bb if isinstance(stack, (int, float)) else None),
                            occupied=True, source='suprema')
            bets.append(dict(seat=k, bet_bb=round(float(p.get('bet') or 0.0) / bb, 4)))

        n = len(self.board)
        street = ('RIVER' if n >= 5 else 'TURN' if n == 4 else 'FLOP' if n == 3 else 'PREFLOP')
        max_bet = max((b['bet_bb'] for b in bets), default=0.0)
        hero_bet = next((b['bet_bb'] for b in bets if b['seat'] == 'hero'), 0.0)
        to_call_bb = round(max(0.0, max_bet - hero_bet), 2)
        pot_bb = round((self.pot_carry + sum(p['bet'] for p in self.players.values())) / bb, 2)
        state = dict(positions=positions, seats=seats, bets=bets, phase='mid',
                     source='suprema', room='SupremaPoker',
                     scope=('POSTFLOP_SUPREMA' if n >= 3 else 'PREFLOP_SUPREMA'),
                     board=list(self.board), street=street,
                     to_call={'to_call_bb': to_call_bb}, pot={'pot_bb': pot_bb})
        return state, hero_cards


def advise_from_suprema(table, advisor, **kwargs):
    """Decide a partir do estado vivo da Suprema, pelo MESMO roteamento do OCR/protobuf
    (advise_from_reading). `table` é um SupremaTable já alimentado. Devolve o dict do
    advisor, ou {status:'ABSTAIN', reason} quando o estado não dá p/ decidir (sem chutar)."""
    state, hero_or_reason = table.to_table_state()
    if state is None:
        return dict(status='ABSTAIN', reason=hero_or_reason, source='suprema')
    return advisor.advise_from_reading(state, hero_or_reason, **kwargs)
