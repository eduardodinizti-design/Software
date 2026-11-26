"""Testes do H2N do PPPoker (tracker de mãos por snapshots do estado protobuf). Offline."""
import json
import os
import tempfile
import unittest

import ppp_h2n as H
from ppp_cards import encode_card

CAP = os.path.join("research", "ppp_il2cpp", "estado_mesa_multitable_20261120.json")


def _cards(*txt):
    return [encode_card(t) for t in txt]


def _player(seat, uid, *, stack=10000, sit=0, bet=0, act=0, hascard=1, cards=None):
    return dict(seat=seat, uid=uid, name="p%d" % uid, stack=stack, sit=sit, bet=bet,
                act=act, hascard=hascard, cards=cards or [])


def _entry(hero_cards=None, *, sb=100, board=None, pot=0, hero_uid=999, hero_stack=10000,
           hero_bet=0, extra=None):
    players = [_player(6, hero_uid, stack=hero_stack, bet=hero_bet,
                       cards=(hero_cards or [])),
               _player(0, 111, stack=9000), _player(1, 222, stack=8000)]
    if extra:
        players += extra
    return dict(ts=1.0, room="SMALL PKO", players=players,
                table=dict(dealer=6, sbseat=0, bbseat=1, sb=sb, board=board or [],
                           stage=1, tocall=0, pot=pot))


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        self.t += 1.0
        return self.t


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rec = H.HandRecorder(out_dir=self.tmp, clock=_Clock())

    def test_uma_mao_completa_preflop_ao_river(self):
        rid = "500"
        flop = _cards("Ah", "7d", "2c")
        # pré-flop
        self.rec.observe({rid: _entry(_cards("As", "Kd"), pot=300, hero_stack=10000)})
        # flop
        self.rec.observe({rid: _entry(_cards("As", "Kd"), board=flop, pot=800)})
        # turn
        self.rec.observe({rid: _entry(_cards("As", "Kd"), board=flop + _cards("Qs"), pot=1600)})
        # river
        self.rec.observe({rid: _entry(_cards("As", "Kd"),
                                      board=flop + _cards("Qs", "Jc"), pot=3200)})
        closed = self.rec.flush()
        self.assertEqual(len(closed), 1)
        h = closed[0]
        self.assertEqual(h["hero"]["cards"], ["As", "Kd"])
        self.assertEqual(h["board"]["flop"], ["Ah", "7d", "2c"])
        self.assertEqual(h["board"]["turn"], ["Qs"])
        self.assertEqual(h["board"]["river"], ["Jc"])
        self.assertEqual(h["reached_street"], "river")
        self.assertEqual(h["pot_chips_final"], 3200)
        self.assertEqual(h["pot_bb_final"], 16.0)           # pot 3200 / bb 200
        self.assertEqual(h["hero"]["stack_chips_start"], 10000)
        self.assertEqual(h["blinds"]["bb_chips"], 200)

    def test_mao_nova_fecha_a_anterior(self):
        rid = "501"
        c1 = self.rec.observe({rid: _entry(_cards("As", "Kd"))})
        self.assertEqual(c1, [])                             # 1ª mão abriu
        c2 = self.rec.observe({rid: _entry(_cards("Qh", "Qs"))})
        self.assertEqual(len(c2), 1)                         # troca de dupla fechou a 1ª
        self.assertEqual(c2[0]["hero"]["cards"], ["As", "Kd"])
        rest = self.rec.flush()
        self.assertEqual(rest[0]["hero"]["cards"], ["Qh", "Qs"])

    def test_reset_de_board_fecha_mao(self):
        rid = "502"
        flop = _cards("Ah", "7d", "2c")
        self.rec.observe({rid: _entry(_cards("As", "Kd"), board=flop)})
        # herói sem cartas visíveis E board zerado -> mão anterior acabou
        closed = self.rec.observe({rid: _entry([], board=[])})
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["board"]["flop"], ["Ah", "7d", "2c"])

    def test_showdown_nao_perde_a_mao(self):
        # no showdown um vilão revela cartas; o herói é mantido pelo uid aprendido
        rid = "503"
        self.rec.observe({rid: _entry(_cards("As", "Kd"))})
        vilao = [_player(2, 333, cards=_cards("Td", "Tc"))]
        self.rec.observe({rid: _entry(_cards("As", "Kd"),
                                      board=_cards("Ah", "7d", "2c"), extra=vilao)})
        closed = self.rec.flush()
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["hero"]["cards"], ["As", "Kd"])  # não virou Td/Tc

    def test_acoes_observaveis_registram_mudanca_de_aposta(self):
        rid = "504"
        self.rec.observe({rid: _entry(_cards("As", "Kd"), hero_bet=0)})
        self.rec.observe({rid: _entry(_cards("As", "Kd"), hero_bet=200)})  # herói apostou
        h = self.rec.flush()[0]
        hero_acts = [a for a in h["actions"] if a["is_hero"] and a["bet_chips"] == 200]
        self.assertTrue(hero_acts, "deveria registrar a aposta do herói")


class PersistenceTests(unittest.TestCase):
    def test_grava_jsonl_e_rele(self):
        tmp = tempfile.mkdtemp()
        rec = H.HandRecorder(out_dir=tmp, filename="h.jsonl", clock=_Clock())
        rid = "600"
        rec.observe({rid: _entry(_cards("As", "Kd"))})
        rec.observe({rid: _entry(_cards("Qh", "Qs"))})       # fecha a 1ª e grava
        path = os.path.join(tmp, "h.jsonl")
        self.assertTrue(os.path.exists(path))
        hands = H.load_hands(path)
        self.assertEqual(len(hands), 1)
        self.assertEqual(hands[0]["source"], "pppoker")
        self.assertEqual(hands[0]["hero"]["cards"], ["As", "Kd"])
        self.assertNotIn("_last_bets", hands[0])             # estado interno não vaza p/ o DB


class MultiTableTests(unittest.TestCase):
    def test_duas_mesas_independentes(self):
        tmp = tempfile.mkdtemp()
        rec = H.HandRecorder(out_dir=tmp, clock=_Clock())
        snap = {"A": _entry(_cards("As", "Kd"), hero_uid=999),
                "B": _entry(_cards("9s", "9d"), hero_uid=999)}
        rec.observe(snap)
        closed = rec.flush()
        rooms = sorted(h["roomid"] for h in closed)
        self.assertEqual(rooms, ["A", "B"])

    def test_ignora_metachaves(self):
        tmp = tempfile.mkdtemp()
        rec = H.HandRecorder(out_dir=tmp, clock=_Clock())
        rec.observe({"_hero_turn": {"ref": "A"}, "A": _entry(_cards("As", "Kd"))})
        self.assertEqual(len(rec.flush()), 1)


class CapturaRealTests(unittest.TestCase):
    def test_processa_captura_exemplo(self):
        if not os.path.exists(CAP):
            self.skipTest("captura de exemplo ausente")
        with open(CAP, encoding="utf-8") as fh:
            estado = json.load(fh)
        tmp = tempfile.mkdtemp()
        rec = H.HandRecorder(out_dir=tmp, clock=_Clock(), hero_uid=13797173)
        rec.observe(estado)
        closed = rec.flush()
        # as 2 mesas da captura têm o herói com cartas -> 2 mãos abertas e fechadas no flush
        self.assertEqual(len(closed), 2)
        for h in closed:
            self.assertEqual(len(h["hero"]["cards"]), 2)
            self.assertIsNotNone(h["blinds"]["bb_chips"])


if __name__ == "__main__":
    unittest.main()
