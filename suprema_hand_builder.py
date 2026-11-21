"""Reconstrói HAND HISTORY da Suprema a partir dos eventos de REDE (suprema_net).

A Suprema manda ESTADO (snapshots de game_seat), não ações. Este builder bufferiza os
eventos de UMA mão (gamestart..gameover) e, no gameover, infere a sequência de ações por
DELTA de `chips_round` por assento, conservando o dinheiro, e dirige o MESMO HandAccumulator
do PPPoker (destino: .txt sala 'SupremaPoker' -> watcher -> banco NVT). READ-ONLY.

Protocolo (SUPREMA_PROTOCOL.md): ante=chips de role 0; blinds por role (82=SB,93=BB);
coins=stack, chips=apostado na mão, chips_round=apostado na rua; board=gameinfo.shared_cards;
INVARIANTE coins+chips=stack inicial; game_counter=ID; room_status.seats=uid por assento.
Códigos ppp_actions: 1=fold 2=check 3=call 4=agressão 8=SB 9=BB 10=ante.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from suprema_state import decode_cards   # noqa: E402

FOLD, CHECK, CALL, AGGR, SB, BB, ANTE = 1, 2, 3, 4, 8, 9, 10
ROLE_SB, ROLE_BB = 82, 93


def _street_of(nshared):
    return 1 if nshared < 3 else 2 if nshared == 3 else 3 if nshared == 4 else 4


class SupremaHandBuilder:
    def __init__(self, acc):
        self.acc = acc
        self.counter = None
        self.open = False
        self.buf = []
        self.built = 0

    def feed(self, msg):
        if not isinstance(msg, dict):
            return
        ev = msg.get("event")
        d = msg.get("data") or {}
        if ev == "gamestart":
            c = (d.get("game_info") or {}).get("game_counter")
            if c is not None and c != self.counter:
                self.counter = c
                self.buf = []
                self.open = True
            if self.open:
                self.buf.append(msg)
        elif ev in ("moveturn", "gameinfo", "prompt"):
            if self.open:
                self.buf.append(msg)
        elif ev == "gameover":
            if self.open:
                self.buf.append(msg)
                try:
                    self._build(d)
                    self.built += 1
                except Exception as e:  # nunca derruba a captura
                    print("[suprema-build] erro ao montar mão %s: %s" % (self.counter, e), flush=True)
                self.open = False

    # ------------------------------------------------------------------
    def _build(self, gameover_data):
        acc = self.acc
        dealer = None
        seat_uid = {}        # seat -> uid
        start_stack = {}     # seat -> coins+chips no 1º avistamento (= stack inicial)
        latest_gs = {}       # seat -> último game_seat (dos frames de gamestart)
        hero_seat = None
        hero_cards = None
        ts = None

        gamestart_msgs = [m for m in self.buf if m.get("event") == "gamestart"]
        flow_msgs = [m for m in self.buf if m.get("event") in ("moveturn", "gameinfo")]

        # ---- 1) estática (gamestart) ----
        for m in gamestart_msgs:
            d = m.get("data") or {}
            gi = d.get("game_info") or {}
            if gi.get("dealer_seat") is not None:
                dealer = gi["dealer_seat"]
            if d.get("ts"):
                ts = d["ts"]
            rs = d.get("room_status") or {}
            if isinstance(rs.get("seats"), list):
                for idx, uid in enumerate(rs["seats"]):
                    if uid is not None:
                        seat_uid[idx] = uid
            gs = d.get("game_seat")
            if isinstance(gs, dict):
                for uid, p in gs.items():
                    seat = p.get("seat")
                    if seat is None:
                        continue
                    seat_uid[seat] = _as_uid(uid)
                    if seat not in start_stack:
                        start_stack[seat] = (p.get("coins") or 0) + (p.get("chips") or 0)
                    latest_gs[seat] = p

        if not start_stack:
            return  # sem assentos — nada a montar

        # ante / blinds pelos roles do estado final de gamestart
        role0_chips = [p.get("chips") or 0 for p in latest_gs.values() if p.get("role") == 0]
        ante = min(role0_chips) if role0_chips else 0
        sb_seat = sb_amt = bb_seat = bb_amt = None
        for seat, p in latest_gs.items():
            if p.get("role") == ROLE_SB:
                sb_seat, sb_amt = seat, (p.get("chips") or 0) - ante
            elif p.get("role") == ROLE_BB:
                bb_seat, bb_amt = seat, (p.get("chips") or 0) - ante
        bb_amt = bb_amt or 0
        sb_amt = sb_amt or 0

        # herói: assento com cartas reais em qualquer frame (ou uid do prompt)
        for m in self.buf:
            d = m.get("data") or {}
            gs = d.get("game_seat")
            if isinstance(gs, dict):
                for uid, p in gs.items():
                    cc = decode_cards(p.get("cards") or [])
                    if len(cc) == 2 and p.get("seat") is not None:
                        hero_seat, hero_cards = p["seat"], cc
            if m.get("event") == "prompt" and m.get("uid") is not None:
                for s, u in seat_uid.items():
                    if u == m["uid"]:
                        hero_seat = s

        seats_sorted = sorted(start_stack)

        # ---- 2) abre a mão no accumulator ----
        for s in seats_sorted:
            acc.set_seat(s, player=seat_uid.get(s, s), stack=start_stack[s])
        acc.on_dealer(button_seat=dealer, seats=[{"seat": s, "stack": start_stack[s]} for s in seats_sorted])
        dt = datetime.fromtimestamp(ts / 1000).strftime("%Y/%m/%d %H:%M:%S") if ts else None
        acc.on_round_start(1, cur_blind=sb_amt or bb_amt // 2, button_seat=dealer,
                           hand_id=str(self.counter), datetime=dt)
        # posts: antes + blinds
        for s in seats_sorted:
            if ante > 0:
                acc.on_action(s, ANTE, ante)
        if sb_seat is not None and sb_amt > 0:
            acc.on_action(sb_seat, SB, sb_amt)
        if bb_seat is not None and bb_amt > 0:
            acc.on_action(bb_seat, BB, bb_amt)
        if hero_seat is not None:
            acc.mark_hero(hero_seat)
            if hero_cards:
                acc.on_hand_card(hero_cards, seatid=hero_seat)

        # ---- 3) ações por delta de chips_round, rua a rua ----
        street = 1
        street_max = bb_amt
        committed = {s: 0 for s in seats_sorted}
        if sb_seat is not None:
            committed[sb_seat] = sb_amt
        if bb_seat is not None:
            committed[bb_seat] = bb_amt
        last_active_street = {s: 1 for s in seats_sorted}
        board_codes = []

        for m in flow_msgs:
            d = m.get("data") or {}
            gi = d.get("game_info") or {}
            sc = gi.get("shared_cards")
            if isinstance(sc, list) and len(sc) >= len(board_codes):
                board_codes = sc
            # mudança de rua pelo nº de shared_cards
            if isinstance(sc, list):
                ns = _street_of(len(sc))
                if ns > street:
                    street = ns
                    acc.on_round_start(street, board=decode_cards(sc))
                    street_max = 0
                    committed = {s: 0 for s in committed}
            gs = d.get("game_seat") or gi.get("game_seat")
            if not isinstance(gs, dict):
                continue
            # ordena por assento p/ determinismo
            for uid, p in sorted(gs.items(), key=lambda kv: (kv[1] or {}).get("seat", 99)):
                seat = p.get("seat")
                if seat is None:
                    continue
                cr = p.get("chips_round")
                if cr is None:
                    # sem chips_round: deriva do chips desta rua não é confiável -> pula
                    continue
                prev = committed.get(seat, 0)
                if cr > prev:
                    delta = cr - prev
                    allin = (p.get("coins") or 0) == 0
                    code = AGGR if cr > street_max else CALL
                    if cr > street_max:
                        street_max = cr
                    acc.on_action(seat, code, delta, is_all_in=allin)
                    committed[seat] = cr
                    last_active_street[seat] = street

        # ---- 4) folds dos que não foram ao showdown ----
        go_seats = set()
        gr = (gameover_data or {}).get("game_result") or {}
        for uid, p in (gr.get("seats") or {}).items():
            if p.get("seat") is not None:
                go_seats.add(p["seat"])
        for s in seats_sorted:
            if s in go_seats:
                continue
            # não chegou ao showdown e não está all-in -> foldou (na sua última rua ativa)
            acc.on_action(s, FOLD, 0)

        # ---- 5) winner + fim ----
        allpots = gr.get("allpots") or []
        total_pot = int(allpots[0]) if allpots else sum(
            (p.get("chips") or 0) for p in latest_gs.values())
        # ganhador(es): maior coins final entre os do showdown
        winners = []
        if gr.get("seats"):
            mx = max((p.get("coins") or 0) for p in gr["seats"].values())
            winners = [p["seat"] for p in gr["seats"].values() if (p.get("coins") or 0) == mx]
        seat_uids = [{"seat": s, "uid": seat_uid.get(s)} for s in seats_sorted]
        collected = [(w, total_pot // len(winners)) for w in winners] if winners else None
        acc.on_winner(collected=collected, total_pot=total_pot, seat_uids=seat_uids)
        acc.on_hand_over()


def _as_uid(uid):
    try:
        return int(uid)
    except (TypeError, ValueError):
        return uid
