"""Testes das GUARDAS do PPPoker (bust/sit-out) — decisões puras sobre o estado protobuf.
Offline: estados sintéticos + a captura de exemplo do repo."""
import json
import os
import unittest

import ppp_guards as G
from ppp_cards import encode_card

CAP = os.path.join("research", "ppp_il2cpp", "estado_mesa_multitable_20261120.json")


def _cards(*txt):
    return [encode_card(t) for t in txt]


def _player(seat, uid, *, stack=10000, sit=0, bet=0, act=0, hascard=1, cards=None):
    return dict(seat=seat, uid=uid, name="p%d" % uid, stack=stack, sit=sit, bet=bet,
                act=act, hascard=hascard, cards=cards or [])


def _entry(players, *, sb=100, board=None):
    return dict(ts=1.0, room="T", players=players,
                table=dict(dealer=0, sbseat=0, bbseat=1, sb=sb, board=board or [],
                           stage=1, tocall=0, pot=0))


def _estado(entry, roomid="123"):
    return {roomid: entry}


class HeroResolveTests(unittest.TestCase):
    def test_learn_uid_por_cartas(self):
        e = _entry([_player(6, 999, cards=_cards("As", "Kd")),
                    _player(1, 111), _player(2, 222)])
        self.assertEqual(G.learn_hero_uid(_estado(e)), 999)

    def test_uid_ambiguo_quando_dois_revelam(self):
        e = _entry([_player(6, 999, cards=_cards("As", "Kd")),
                    _player(1, 111, cards=_cards("Qh", "Qs"))])
        self.assertIsNone(G.learn_hero_uid(_estado(e)))

    def test_resolve_por_uid_robusto_a_showdown(self):
        e = _entry([_player(6, 999, cards=_cards("As", "Kd")),
                    _player(1, 111, cards=_cards("Qh", "Qs"))])
        hero = G.resolve_hero(e, hero_uid=999)
        self.assertEqual(hero["uid"], 999)


class SitoutTests(unittest.TestCase):
    def test_detecta_sitout_por_flag(self):
        e = _entry([_player(6, 999, sit=1, cards=_cards("As", "Kd")), _player(1, 111)])
        self.assertTrue(G.detect_sitout(_estado(e), "123", hero_uid=999))

    def test_sem_sitout_quando_flag_zero(self):
        e = _entry([_player(6, 999, sit=0, cards=_cards("As", "Kd")), _player(1, 111)])
        self.assertFalse(G.detect_sitout(_estado(e), "123", hero_uid=999))

    def test_decision_sitout_manda_voltar_nunca_folda(self):
        e = _entry([_player(6, 999, sit=1), _player(1, 111)])
        d = G.guard_decision(_estado(e), "123", hero_uid=999)
        self.assertEqual(d["action"], "SITOUT_RETURN")   # LEI: voltar, jamais foldar p/ walk
        self.assertNotIn("FOLD", d["action"])


class BustTests(unittest.TestCase):
    def test_bust_uid_ausente_da_mesa(self):
        # herói (uid 999) sumiu dos assentos, mesa segue viva -> eliminado
        e = _entry([_player(1, 111), _player(2, 222)])
        self.assertTrue(G.detect_bust(_estado(e), "123", hero_uid=999))

    def test_bust_stack_zero_sem_carta(self):
        e = _entry([_player(6, 999, stack=0, hascard=0, cards=[]), _player(1, 111)])
        self.assertTrue(G.detect_bust(_estado(e), "123", hero_uid=999))

    def test_allin_nao_e_bust(self):
        # stack 0 mas COM carta nesta mão = all-in VIVO, nunca bust (veto)
        e = _entry([_player(6, 999, stack=0, hascard=1, cards=_cards("As", "Kd")),
                    _player(1, 111)])
        self.assertFalse(G.detect_bust(_estado(e), "123", hero_uid=999))

    def test_conservador_sem_identidade(self):
        # sem uid e sem assento único de 2 cartas -> não dá p/ afirmar bust
        e = _entry([_player(1, 111), _player(2, 222)])
        self.assertFalse(G.detect_bust(_estado(e), "123"))

    def test_decision_bust_manda_parar(self):
        e = _entry([_player(1, 111), _player(2, 222)])
        d = G.guard_decision(_estado(e), "123", hero_uid=999)
        self.assertEqual(d["action"], "STOP")
        self.assertEqual(d["reason"], "BUST")

    def test_bust_tem_precedencia_sobre_sitout(self):
        # herói ausente (bust) -> STOP mesmo que houvesse flag de sit em outro frame
        e = _entry([_player(1, 111)])
        d = G.guard_decision(_estado(e), "123", hero_uid=999)
        self.assertEqual(d["action"], "STOP")


class MonitorTests(unittest.TestCase):
    def test_debounce_bust_precisa_de_n_frames(self):
        mon = G.GuardMonitor(need=3, hero_uid=999)
        e = _entry([_player(1, 111), _player(2, 222)])
        self.assertEqual(mon.update(_estado(e), "123")["action"], "OK")
        self.assertEqual(mon.update(_estado(e), "123")["action"], "OK")
        self.assertEqual(mon.update(_estado(e), "123")["action"], "STOP")  # 3ª seguida confirma
        self.assertEqual(mon.update(_estado(e), "123")["reason"], "BUST_DONE")

    def test_frame_vivo_zera_streak(self):
        mon = G.GuardMonitor(need=2, hero_uid=999)
        gone = _entry([_player(1, 111)])
        alive = _entry([_player(6, 999, cards=_cards("As", "Kd")), _player(1, 111)])
        self.assertEqual(mon.update(_estado(gone), "123")["action"], "OK")
        self.assertEqual(mon.update(_estado(alive), "123")["action"], "OK")  # zerou
        self.assertEqual(mon.update(_estado(gone), "123")["action"], "OK")
        self.assertEqual(mon.update(_estado(gone), "123")["action"], "STOP")

    def test_monitor_aprende_uid_e_detecta_sitout(self):
        mon = G.GuardMonitor(need=2)                    # sem uid inicial
        e = _entry([_player(6, 999, sit=1, cards=_cards("As", "Kd")), _player(1, 111)])
        d = mon.update(_estado(e), "123")
        self.assertEqual(mon.hero_uid, 999)
        self.assertEqual(d["action"], "SITOUT_RETURN")


class CapturaRealTests(unittest.TestCase):
    def test_captura_exemplo_herois_vivos(self):
        if not os.path.exists(CAP):
            self.skipTest("captura de exemplo ausente")
        with open(CAP, encoding="utf-8") as fh:
            estado = json.load(fh)
        # nas duas mesas o herói "Just do it♠" (uid 13797173) está com 2 cartas = VIVO
        for roomid in estado:
            d = G.guard_decision(estado, roomid, hero_uid=13797173)
            self.assertEqual(d["action"], "OK", "mesa %s deveria estar OK" % roomid)
            self.assertFalse(G.detect_bust(estado, roomid, hero_uid=13797173))
            self.assertFalse(G.detect_sitout(estado, roomid, hero_uid=13797173))


if __name__ == "__main__":
    unittest.main()
