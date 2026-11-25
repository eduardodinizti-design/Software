"""TRAVA do roteador multi-mesa da Suprema: eventos de 2 salas INTERCALADOS não podem cruzar —
cada roomID mantém seu próprio estado, com o mesmo hero_uid ancorando o herói em cada mesa."""
import unittest

from suprema_multi import RoomOrder, SupremaRouter, event_ts, room_of


def gi(room, board):
    return {"event": "gameinfo", "data": {"roomID": room,
            "game_info": {"dealer_seat": 2, "shared_cards": board, "pot": 1000, "state": 4}}}


def mv(room, hero_uid, hero_seat, cards):
    return {"event": "moveturn", "uid": hero_uid, "data": {"roomID": room, "game_seat": {
        str(hero_uid): {"seat": hero_seat, "uid": hero_uid, "coins": 50000,
                        "cards": cards, "chips": 0, "chips_round": 0, "sitout": False},
        "999": {"seat": 5, "uid": 999, "coins": 40000, "cards": None,
                "chips": 0, "chips_round": 0, "sitout": False}}}}


class Router(unittest.TestCase):

    def test_room_of_normaliza_sufixo(self):
        self.assertEqual(room_of({"data": {"roomID": "14625_50738142_4#113"}}), "14625_50738142_4")
        self.assertEqual(room_of({"data": {"roomID": "A_B_4"}}), "A_B_4")
        self.assertIsNone(room_of({"data": {}}))

    def test_duas_salas_nao_cruzam(self):
        A, B = "112214625_41050741133_312143", "112214625_58050741355_44114"
        r = SupremaRouter(bb_chips=600, hero_uid=100)
        # INTERCALA as duas mesas (como chega no stream único)
        r.feed_json(gi(A, [73, 77, 20]))        # mesa A: board 9s Ks 4d (3 cartas)
        r.feed_json(mv(A, 100, 2, [78, 62]))    # herói A: As Ah
        r.feed_json(gi(B, [40, 39]))            # mesa B: board 8c 7c (2... na vdd flop parcial)
        r.feed_json(mv(B, 100, 7, [59, 56]))    # herói B: Jh 8h
        r.feed_json(gi(B, [40, 39, 41]))        # mesa B cresce p/ 3
        self.assertEqual(set(r.rooms()), {A, B})
        ta, tb = r.table(A), r.table(B)
        # herói ancorado por uid em CADA mesa, cartas NÃO cruzam
        self.assertEqual(ta.players[ta.hero_seat]["cards"], ["As", "Ah"])
        self.assertEqual(tb.players[tb.hero_seat]["cards"], ["Jh", "8h"])
        self.assertEqual(ta.hero_seat, 2)
        self.assertEqual(tb.hero_seat, 7)
        # boards independentes
        self.assertEqual(ta.board, ["9s", "Ks", "4d"])
        self.assertEqual(tb.board, ["8c", "7c", "9c"])

    def test_hero_uid_aprendido_propaga_p_todas(self):
        A, B = "salaA_4", "salaB_4"
        r = SupremaRouter(bb_chips=600)                 # sem hero_uid no início
        r.feed_json(gi(A, []))                           # cria mesa A sem uid
        r.feed_json(mv(B, 100, 3, [78, 62]))            # chega uid=100 na mesa B
        self.assertEqual(r.hero_uid, 100)
        self.assertEqual(r.table(A).hero_uid, 100)      # propagou p/ a mesa A também
        self.assertEqual(r.table(B).hero_uid, 100)


class Order(unittest.TestCase):
    """RoomOrder: mapa roomID->COLUNA estável (append-only) + contagem de mesas VIVAS (poda
    bustadas por staleness relativa). Sem sinal de posição no protocolo -> ordem de 1ª aparição."""

    def test_ordem_primeira_aparicao_append_only(self):
        o = RoomOrder()
        o.touch("B", 1.0)                 # B aparece ANTES (fora de ordem alfabética)
        o.touch("A", 1.0)
        self.assertEqual(o.index("B"), 0)      # coluna por 1ª aparição, NÃO por sorted()
        self.assertEqual(o.index("A"), 1)
        self.assertEqual(o.n_rooms(), 2)

    def test_mesa_nova_nao_embaralha_colunas_vivas(self):
        # O BUG antigo (_order.sort()) movia as colunas de mesas VIVAS quando entrava uma sala nova.
        o = RoomOrder()
        o.touch("m9", 1.0)                # roomID que viria ANTES num sorted()
        o.touch("m5", 1.0)
        i9, i5 = o.index("m9"), o.index("m5")
        o.touch("m1", 2.0)               # entra uma 3ª sala (sorted() a poria no índice 0)
        self.assertEqual(o.index("m9"), i9)    # colunas das vivas INTACTAS
        self.assertEqual(o.index("m5"), i5)
        self.assertEqual(o.index("m1"), 2)     # a nova vai pra ÚLTIMA coluna
        self.assertEqual(o.n_rooms(), 3)

    def test_bustada_removida_e_n_rooms_reflete_vivas(self):
        o = RoomOrder(ttl=90.0)
        o.touch("A", 100.0)
        o.touch("B", 100.0)
        o.touch("C", 100.0)
        self.assertEqual(o.n_rooms(), 3)
        # A some (bustou); B e C seguem jogando bem depois -> A fica >ttl atrás da + recente
        o.touch("B", 300.0)
        o.touch("C", 300.0)
        self.assertEqual(o.n_rooms(), 2)          # só as vivas
        self.assertEqual(o.live_rooms(), ["B", "C"])
        self.assertEqual(o.index("B"), 0)         # lista viva COMPACTADA (A saiu, B desliza p/ 0)
        self.assertEqual(o.index("C"), 1)
        self.assertEqual(o.all_rooms(), ["A", "B", "C"])   # histórico preserva a 1ª aparição

    def test_break_global_nao_poda_ninguem(self):
        # Break da Suprema (:55->:00): TODAS as mesas param juntas; staleness RELATIVA não poda.
        o = RoomOrder(ttl=90.0)
        o.touch("A", 100.0)
        o.touch("B", 101.0)
        # ninguém recebe evento por muito tempo (break) -> gap entre elas continua ~0
        self.assertEqual(o.n_rooms(), 2)
        self.assertEqual(o.live_rooms(), ["A", "B"])

    def test_sala_revive_ao_reaparecer(self):
        o = RoomOrder(ttl=90.0)
        o.touch("A", 100.0)
        o.touch("B", 100.0)
        o.touch("B", 300.0)              # A bustou (podada)
        self.assertEqual(o.live_rooms(), ["B"])
        o.touch("A", 310.0)              # A volta a dar evento -> revive na coluna original
        self.assertEqual(o.index("A"), 0)
        self.assertEqual(o.live_rooms(), ["A", "B"])

    def test_uma_mesa_nunca_poda(self):
        o = RoomOrder(ttl=90.0)
        o.touch("solo", 100.0)
        o.touch("solo", 100000.0)        # muito tempo depois, ainda sozinha
        self.assertEqual(o.n_rooms(), 1)
        self.assertEqual(o.index("solo"), 0)

    def test_n_rooms_minimo_1_sem_salas(self):
        self.assertEqual(RoomOrder().n_rooms(), 1)     # camada de clique nunca divide por 0

    def test_mark_dead_explicito(self):
        o = RoomOrder(ttl=None)          # sem poda por tempo
        o.touch("A", 1.0)
        o.touch("B", 1.0)
        o.mark_dead("A")
        self.assertEqual(o.live_rooms(), ["B"])

    def test_event_ts_ms_para_segundos(self):
        self.assertEqual(event_ts({"data": {"ts": 1795280170226}}), 1795280170.226)
        self.assertEqual(event_ts({"data": {"ts": 1795280170}}), 1795280170.0)  # já em s
        self.assertIsNone(event_ts({"data": {}}))
        self.assertIsNone(event_ts({"data": {"ts": 0}}))


if __name__ == "__main__":
    unittest.main()
