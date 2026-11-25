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

from datetime import datetime as _dt, timezone as _tz

from ppp_cards import decode_card, decode_cards
from ppp_actions import to_hh_action, stage_name, is_post, ACTION_TYPES
from hand_history_emit import emit_hand

_STREETS = ('preflop', 'flop', 'turn', 'river')


def _utc_stamp() -> str:
    """Timestamp UTC no formato EXATO do cabeçalho Hand2Note/PokerStars
    (`AAAA/MM/DD H:MM:SS`), que o parser ESTRITO do NvtTracker (nlhe_text.HEADER)
    exige — sem ele toda mão vira quarentena `bad_header`."""
    return _dt.now(_tz.utc).strftime('%Y/%m/%d %H:%M:%S')


class HandAccumulator:
    def __init__(self, *, room='PPPoker', tournament_id='', club_id='', table_tag='', max_seats=9,
                 buyin='$0 USD', sink=None, on_hand=None):
        self.meta = dict(room=room, tournament_id=tournament_id, club_id=club_id,
                         table_tag=table_tag, max_seats=max_seats, buyin=buyin)
        self.sink = sink              # ex. DayTournamentSink (opcional)
        self.on_hand = on_hand        # callback(texto, hand_dict) ao fechar (opcional)
        self.seat_player = {}         # seatid -> rótulo do jogador (conta); fallback = seatid
        self.seat_stack = {}          # seatid -> stack inicial (chips)
        self._seq = 0
        self._pending_antes = []      # antes vistas antes do round_start do novo mão
        self._pending_button = None   # botão do DealerInfoRSP (antes do round_start)
        self._pending_seats = []      # [seatid] em jogo no DealerInfoRSP (semeia os Seat:)
        self._hero_seat = None        # assento do herói (só ele tem carta visível no SeatStatus)
        self._h = None                # mão em construção

    def mark_hero(self, seatid):
        """O assento do HERÓI = o único com cartas face-up (SeatStatus.card1!=0). Persiste
        entre mãos (o herói fica no mesmo assento) até mudar."""
        self._hero_seat = int(seatid)

    # ---------- mapa de assentos (do EnterRoomRSP/SeatStatus, quando houver) ----------
    def set_seat(self, seatid, player=None, stack=None):
        if player is not None:
            self.seat_player[int(seatid)] = str(player)
        if stack is not None:
            self.seat_stack[int(seatid)] = int(stack)

    def _player(self, seatid):
        return self.seat_player.get(int(seatid), str(int(seatid)))

    # ---------- eventos ----------
    def on_dealer(self, button_seat=None, seats=None):
        """DealerInfoRSP (início da mão): botão + stacks iniciais por assento. Fica
        PENDENTE e é consumido quando o RoundStart(stage=1) abrir a mão."""
        if button_seat is not None:
            self._pending_button = int(button_seat)
        self._pending_seats = []
        for s in (seats or []):
            seatid = int(s['seat'])
            self._pending_seats.append(seatid)
            if s.get('stack') is not None:
                self.seat_stack[seatid] = int(s['stack'])

    def on_ante(self, seatid, amount):
        self._pending_antes.append((int(seatid), int(amount)))

    def on_round_start(self, stage, *, cur_blind=0, board=None, hero_cards=None,
                       hero_seat=None, button_seat=None, hand_id=None, datetime=None):
        stage = int(stage)
        if stage == 1:
            self._begin_hand(cur_blind=cur_blind, button_seat=button_seat,
                             hand_id=hand_id, datetime=datetime, hero_seat=hero_seat, clean=True)
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
                # guarda SEATID; o rótulo do jogador (uid) é resolvido no finalize — o uid
                # só chega depois (WinnerRSP). Ligar cedo gerava linhas "2: calls" que não
                # batiam com "Seat 2: <uid>" e o parser descartava a ação.
                self._h['posts'].append({'seatid': seatid, 'kind': kind, 'amount': chips})
                if kind == 'sb':
                    self._h['sb'] = chips or self._h['sb']
                elif kind == 'bb':
                    self._h['bb'] = chips or self._h['bb']
                if kind in ('sb', 'bb'):      # semeia o comprometido do preflop (p/ o 'to' dos raises)
                    cs = self._h['_cs'].setdefault('preflop', {})
                    cs[seatid] = cs.get(seatid, 0) + chips
            return
        street = self._h['street']
        act = to_hh_action(atype, chips, street_has_aggression=self._h['_aggr'].get(street, False),
                           is_all_in=is_all_in)
        if act is None:
            return
        # chips = fichas DESTA ação (incremento). Rastreia o total comprometido na rua por
        # assento (semeado pelos blinds) p/ emitir o 'to' CORRETO do raise. Sem isso o 'to'
        # saía errado (to_hh_action tratava chips como total) e a conservação quebrava.
        cs = self._h['_cs'].setdefault(street, {})
        a = act['action']
        if a == 'raises':
            to = cs.get(seatid, 0) + chips
            cs[seatid] = to
            act = {'action': 'raises', 'amount': chips, 'to': to}
        elif a in ('bets', 'calls', 'all-in'):
            cs[seatid] = cs.get(seatid, 0) + chips
        if a in ('bets', 'raises', 'all-in'):
            self._h['_aggr'][street] = True
        act = dict(act, seatid=seatid)          # rótulo resolvido no finalize
        self._h['streets'].setdefault(street, []).append(act)

    def on_winner(self, *, collected=None, total_pot=None, seat_uids=None):
        if self._h is None:
            return
        # seat->uid (WinnerRSP.currentProfit_ traz TODOS os assentos) preenche o mapa de
        # contas ANTES de montar os Seat: / collected — assim o HH usa o ID real do jogador.
        for s in (seat_uids or []):
            if s.get('uid'):
                self.seat_player[int(s['seat'])] = str(s['uid'])
        if collected:
            self._h['collected_raw'] = [(int(s), int(a)) for s, a in collected]   # resolvido no finalize
        if total_pot is not None:
            self._h['total_pot'] = int(total_pot)
        self._h['_closing'] = True

    def on_hand_over(self):
        return self._finalize()

    # ---------- interno ----------
    def _begin_hand(self, *, cur_blind=0, button_seat=None, hand_id=None, datetime=None,
                    hero_seat=None, clean=False):
        # fecha a anterior se ainda aberta
        if self._h is not None:
            self._finalize()
        self._seq += 1
        sb = int(cur_blind or 0)
        if button_seat is None:
            button_seat = self._pending_button      # do DealerInfoRSP
        self._h = {
            'hand_id': hand_id or self._synth_id(),
            'sb': sb, 'bb': sb * 2 if sb else 0, 'ante': 0,
            'button_seat': button_seat,
            'hero_seat': hero_seat,
            'hero_cards': [],
            'posts': [], 'streets': {}, 'board_cumulative': [],
            # preflop JÁ tem "agressão" (o BB é a aposta) -> a 1ª voluntária vira RAISE (PFR
            # conta); pós-flop começa limpo -> a 1ª vira BET. _cs = comprometido por rua/assento.
            'street': 'preflop', '_aggr': {'preflop': True}, '_cs': {}, '_closing': False,
            # _clean = a mão começou num RoundStart(stage=1) de verdade (não "nasceu" no meio,
            # via on_action, quando anexamos no meio dela). Mão suja é DESCARTADA no finalize.
            '_clean': clean,
            # datetime REAL (o driver pode passar o do jogo; senão carimba o relógio
            # UTC AQUI). Nunca vazio -> o cabeçalho sempre passa no parser estrito.
            'datetime': datetime or _utc_stamp(),
            'end_datetime': None,
            'seats_seen': set(),
        }
        # assentos em jogo (DealerInfoRSP) semeiam os Seat: mesmo que o jogador não aja
        for seatid in self._pending_seats:
            self._ensure_seat(seatid)
        # antes acumuladas antes do início entram agora
        for seatid, amount in self._pending_antes:
            self._ensure_seat(seatid)
            self._h['posts'].append({'seatid': seatid, 'kind': 'ante', 'amount': amount})
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

    def _committed(self, h):
        """Replica a contabilidade do parser (committed[street][seat] + invested[seat]) a
        partir dos SEATIDS, p/ achar o gross investido e a maior aposta por rua."""
        from collections import defaultdict
        committed = defaultdict(lambda: defaultdict(int))
        invested = defaultdict(int)
        for p in h['posts']:
            s = p['seatid']
            invested[s] += int(p['amount'])
            if p['kind'] in ('sb', 'bb'):
                committed['preflop'][s] += int(p['amount'])
        for street in _STREETS:
            for a in h['streets'].get(street, []):
                s = a['seatid']
                if a['action'] in ('calls', 'bets', 'all-in'):
                    amt = int(a.get('amount', 0)); committed[street][s] += amt; invested[s] += amt
                elif a['action'] == 'raises':
                    to = int(a.get('to', 0)); inc = to - committed[street][s]
                    committed[street][s] = to; invested[s] += max(0, inc)
        return committed, invested

    def _uncalled(self, h, committed, invested, total_pot):
        """Aposta NÃO paga (devolvida) = gross − pote casado (real, do WinnerRSP), entregue
        ao maior apostador da ÚLTIMA rua com ação. Sem isso, mão que termina em fold
        desbalanceia (Σnet = pote). Devolve (amount, seatid) ou None."""
        gross = sum(invested.values())
        if total_pot is None or total_pot <= 0:
            return None, gross
        unc = gross - int(total_pot)
        if unc <= 0:
            return None, gross
        last = next((st for st in reversed(_STREETS) if committed.get(st)), None)
        if last is None:
            return None, gross
        top = max(committed[last].items(), key=lambda kv: kv[1], default=(None, 0))
        if top[0] is None or unc > top[1]:
            return None, gross        # não deu p/ atribuir com segurança -> sem uncalled
        return (unc, top[0]), gross

    def _finalize(self):
        if self._h is None:
            return None
        h = self._h
        self._h = None
        if not h['streets'] and not h['posts']:
            return None            # mão vazia (nada capturado)
        if not h.get('_clean'):
            return None            # anexamos no meio dela -> parcial/inconsistente, descarta
        board = self._build_board(h)
        committed, invested = self._committed(h)
        total_pot = h.get('total_pot')
        unc, gross = self._uncalled(h, committed, invested, total_pot)
        if total_pot is None:
            total_pot = gross - (unc[0] if unc else 0)
        # resolve TODOS os rótulos (uid) agora que o mapa seat->conta está completo
        posts = [{'player': self._player(p['seatid']), 'kind': p['kind'], 'amount': p['amount']}
                 for p in h['posts']]
        streets = {st: [dict({k: v for k, v in a.items() if k != 'seatid'},
                             player=self._player(a['seatid'])) for a in acts]
                   for st, acts in h['streets'].items()}
        collected = [{'player': self._player(s), 'amount': a} for s, a in h.get('collected_raw', [])]
        uncalled = (unc[0], self._player(unc[1])) if unc else None
        # HERÓI: assento vindo do round_start, ou a dica do SeatStatus (card1!=0). Se o
        # rótulo resolvido não for um dos Seat: da mão, NÃO emite "Dealt to" (senão o parser
        # dá unknown_player). Assim a mão entra válida mesmo sem sabermos o assento do herói.
        hs = h.get('hero_seat')
        if hs is None:
            hs = self._hero_seat
        seat_labels = {self._player(s) for s in h['seats_seen']}
        hero_label = self._player(hs) if hs is not None else None
        if hero_label not in seat_labels:
            hero_label = None
        hand = dict(
            room=self.meta['room'],
            hand_id=h['hand_id'], tournament_id=self.meta['tournament_id'],
            buyin=self.meta['buyin'], sb=h['sb'] or 0, bb=h['bb'] or 0, ante=h['ante'] or 0,
            datetime=h['datetime'], club_id=self.meta['club_id'],
            table_tag=self.meta['table_tag'], max_seats=self.meta['max_seats'],
            button_seat=h['button_seat'] if h['button_seat'] is not None else 0,
            seats=self._seats_list(h),
            hero=hero_label, hero_cards=h['hero_cards'] if hero_label else [],
            posts=posts, streets=streets, board=board, uncalled=uncalled,
            collected=collected, total_pot=total_pot, rake=0,
            # "Hand ended at ..." — o SPLITTER do watcher usa esta linha p/ saber que a
            # mão está COMPLETA (não lê mão pela metade). Carimba o fim se o driver não deu.
            end_datetime=h.get('end_datetime') or _utc_stamp(),
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
