"""ACUMULADOR de mão (fase 2 do tracker): recebe os eventos do stream IL2CPP do PPPoker
(uma mesa) e monta a mão, emitindo no formato Hand2Note via hand_history_emit.emit_hand.

Ciclo (decodificado ao vivo 18/11 — ver FINDINGS_HANDS.md):
  antes (ActionBRC type=10) -> RoundStart(stage=1)=preflop [+HandCardRSP cartas do herói,
  +SB type=8 / +BB type=9] -> ações -> RoundOver -> RoundStart(stage=2/3/4)=flop/turn/river
  -> ... -> WinnerRSP (fim).

É PER-MESA: a camada viva (Frida) cria um HandAccumulator por mesa e roteia os eventos
daquela mesa. Campos ainda dependentes de RE (board array, assento->conta, botão, hand_id,
pote do WinnerRSP) entram por setter/meta; na ausência, usa defaults que mantêm o HH válido.
"""
from __future__ import annotations

from ppp_cards import decode_card, decode_cards
from ppp_actions import to_hh_action, stage_name, is_post, ACTION_TYPES
from hand_history_emit import emit_hand

_STREETS = ('preflop', 'flop', 'turn', 'river')


class HandAccumulator:
    def __init__(self, *, tournament_id='', club_id='', table_tag='', max_seats=9,
                 buyin='$0 USD', sink=None, on_hand=None):
        self.meta = dict(tournament_id=tournament_id, club_id=club_id,
                         table_tag=table_tag, max_seats=max_seats, buyin=buyin)
        self.sink = sink              # ex. DayTournamentSink (opcional)
        self.on_hand = on_hand        # callback(texto, hand_dict) ao fechar (opcional)
        self.seat_player = {}         # seatid -> rótulo do jogador (conta); fallback = seatid
        self.seat_stack = {}          # seatid -> stack inicial (chips)
        self._seq = 0
        self._pending_antes = []      # antes vistas antes do round_start do novo mão
        self._h = None                # mão em construção

    # ---------- mapa de assentos (do EnterRoomRSP/SeatStatus, quando houver) ----------
    def set_seat(self, seatid, player=None, stack=None):
        if player is not None:
            self.seat_player[int(seatid)] = str(player)
        if stack is not None:
            self.seat_stack[int(seatid)] = int(stack)

    def _player(self, seatid):
        return self.seat_player.get(int(seatid), str(int(seatid)))

    # ---------- eventos ----------
    def on_ante(self, seatid, amount):
        self._pending_antes.append((int(seatid), int(amount)))

    def on_round_start(self, stage, *, cur_blind=0, board=None, hero_cards=None,
                       hero_seat=None, button_seat=None, hand_id=None, datetime=None):
        stage = int(stage)
        if stage == 1:
            self._begin_hand(cur_blind=cur_blind, button_seat=button_seat,
                             hand_id=hand_id, datetime=datetime, hero_seat=hero_seat)
            if hero_cards:
                self.on_hand_card(hero_cards, seatid=hero_seat)
        else:
            if self._h is None:
                return
            self._h['street'] = stage_name(stage)
            if board is not None:
                self._set_board(board)

    def on_hand_card(self, cards, seatid=None):
        if self._h is None:
            self._begin_hand()
        decoded = decode_cards(cards) if cards and not isinstance(cards[0], str) else list(cards or [])
        if decoded:
            self._h['hero_cards'] = decoded
        if seatid is not None:
            self._h['hero_seat'] = int(seatid)
            self._h['hero'] = self._player(seatid)

    def on_action(self, seatid, action_type, chips, hand_chips=None, is_all_in=False):
        if self._h is None:
            self._begin_hand()
        seatid = int(seatid)
        atype = int(action_type)
        chips = int(chips or 0)
        self._ensure_seat(seatid)
        # posts (ante/sb/bb) não são "ação" de rua -> vão em posts
        if is_post(atype):
            kind = {8: 'sb', 9: 'bb', 10: 'ante'}.get(atype)
            if kind:
                self._h['posts'].append({'player': self._player(seatid), 'kind': kind,
                                         'amount': chips})
                if kind == 'sb':
                    self._h['sb'] = chips or self._h['sb']
                elif kind == 'bb':
                    self._h['bb'] = chips or self._h['bb']
            return
        street = self._h['street']
        act = to_hh_action(atype, chips, street_has_aggression=self._h['_aggr'].get(street, False),
                           is_all_in=is_all_in)
        if act is None:
            return
        if act['action'] in ('bets', 'raises', 'all-in'):
            self._h['_aggr'][street] = True
        act = dict(act, player=self._player(seatid))
        self._h['streets'].setdefault(street, []).append(act)

    def on_winner(self, *, collected=None, total_pot=None):
        if self._h is None:
            return
        if collected:
            self._h['collected'] = [{'player': self._player(s) if isinstance(s, int) else str(s),
                                     'amount': int(a)} for s, a in collected]
        if total_pot is not None:
            self._h['total_pot'] = int(total_pot)
        self._h['_closing'] = True

    def on_hand_over(self):
        return self._finalize()

    # ---------- interno ----------
    def _begin_hand(self, *, cur_blind=0, button_seat=None, hand_id=None, datetime=None,
                    hero_seat=None):
        # fecha a anterior se ainda aberta
        if self._h is not None:
            self._finalize()
        self._seq += 1
        sb = int(cur_blind or 0)
        self._h = {
            'hand_id': hand_id or self._synth_id(),
            'sb': sb, 'bb': sb * 2 if sb else 0, 'ante': 0,
            'button_seat': button_seat,
            'hero_seat': hero_seat, 'hero': self._player(hero_seat) if hero_seat is not None else 'Hero',
            'hero_cards': [],
            'posts': [], 'streets': {}, 'board_cumulative': [],
            'street': 'preflop', '_aggr': {}, '_closing': False,
            'datetime': datetime or '',
            'seats_seen': set(),
        }
        # antes acumuladas antes do início entram agora
        for seatid, amount in self._pending_antes:
            self._ensure_seat(seatid)
            self._h['posts'].append({'player': self._player(seatid), 'kind': 'ante', 'amount': amount})
            self._h['ante'] = amount or self._h['ante']
        self._pending_antes = []

    def _ensure_seat(self, seatid):
        if self._h is not None:
            self._h['seats_seen'].add(int(seatid))

    def _set_board(self, board_cards):
        cards = decode_cards(board_cards) if board_cards and not isinstance(board_cards[0], str) \
            else list(board_cards or [])
        self._h['board_cumulative'] = cards

    def _synth_id(self):
        base = self.meta.get('tournament_id') or '0'
        return f"{base}{self._seq:06d}"

    def _build_board(self, h):
        c = h['board_cumulative']
        b = {}
        if len(c) >= 3:
            b['flop'] = c[:3]
        if len(c) >= 4:
            b['turn'] = c[3:4]
        if len(c) >= 5:
            b['river'] = c[4:5]
        return b

    def _seats_list(self, h):
        seats = []
        for seatid in sorted(h['seats_seen']):
            seats.append({'seat': seatid, 'player': self._player(seatid),
                          'chips': self.seat_stack.get(seatid, 0)})
        return seats

    def _finalize(self):
        if self._h is None:
            return None
        h = self._h
        self._h = None
        if not h['streets'] and not h['posts']:
            return None            # mão vazia (nada capturado)
        board = self._build_board(h)
        total_pot = h.get('total_pot')
        if total_pot is None:
            total_pot = sum(p['amount'] for p in h['posts']) + sum(
                a.get('amount', a.get('to', 0)) for acts in h['streets'].values() for a in acts)
        hand = dict(
            hand_id=h['hand_id'], tournament_id=self.meta['tournament_id'],
            buyin=self.meta['buyin'], sb=h['sb'] or 0, bb=h['bb'] or 0, ante=h['ante'] or 0,
            datetime=h['datetime'], club_id=self.meta['club_id'],
            table_tag=self.meta['table_tag'], max_seats=self.meta['max_seats'],
            button_seat=h['button_seat'] if h['button_seat'] is not None else 0,
            seats=self._seats_list(h), hero=h['hero'], hero_cards=h['hero_cards'],
            posts=h['posts'], streets=h['streets'], board=board,
            collected=h.get('collected', []), total_pot=total_pot, rake=0,
        )
        text = emit_hand(hand)
        if self.sink is not None:
            try:
                self.sink.write(text, tournament=self.meta.get('table_tag')
                                or self.meta.get('tournament_id') or 'torneio')
            except Exception:
                pass
        if self.on_hand is not None:
            try:
                self.on_hand(text, hand)
            except Exception:
                pass
        return text
