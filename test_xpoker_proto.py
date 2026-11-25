"""TRAVA do decoder de protocolo do X-Poker (offline): o pool dos .pb vendados carrega e
decodifica as mensagens de mesa (round-trip), e o try_decode acha o tipo sem o cmd-id.
Pula se os .pb vendados não estiverem presentes. Ver [[nvt-xpoker-recon]]."""
import os
import unittest

import xpoker_proto as X

HAVE_PB = os.path.isdir(X.PB_DIR) and any(f.endswith(".pb") for f in os.listdir(X.PB_DIR))


@unittest.skipUnless(HAVE_PB, "schemas .pb do X-Poker ausentes")
class XPokerProto(unittest.TestCase):

    def test_pool_carrega_e_mensagens_de_mesa_existem(self):
        nomes = X.list_messages("pk.")
        self.assertGreater(len(nomes), 500)
        for n in X.TABLE_MSGS:
            self.assertIn(n, nomes, n)
            X.get_class(n)                         # resolve a classe sem erro

    def test_roundtrip_round_begin_board(self):
        RB = X.get_class("pk.TexasRoundBeginBRC")
        msg = RB(round=2, board_cards=[11, 22, 33])   # flop (3 cartas, ints como na Suprema)
        raw = msg.SerializeToString()
        got = X.decode("pk.TexasRoundBeginBRC", raw)
        self.assertEqual(list(got.board_cards), [11, 22, 33])
        self.assertEqual(got.round, 2)

    def test_roundtrip_self_hand(self):
        SH = X.get_class("pk.TexasSelfHandBRC")
        raw = SH(hands=[41, 42]).SerializeToString()
        self.assertEqual(list(X.decode("pk.TexasSelfHandBRC", raw).hands), [41, 42])

    def test_player_detail_tem_require_call_amount(self):
        # o campo que torna o to_call pós-flop EXATO no X-Poker (vantagem vs Suprema)
        c = X.get_class("pk.TexasPlayerDetail")
        campos = {f.name for f in c.DESCRIPTOR.fields}
        for nome in ("require_call_amount", "minimum_bet_amount", "maximum_bet_amount", "hand_cards"):
            self.assertIn(nome, campos)

    def test_try_decode_acha_o_tipo(self):
        AC = X.get_class("pk.TexasGameActionBRC")
        raw = AC(hand_id="h1", action=1, action_chips=600, remaining_chips=5000, seat_id=3).SerializeToString()
        achados = {n for n, _ in X.try_decode(raw, candidates=X.TABLE_MSGS)}
        self.assertIn("pk.TexasGameActionBRC", achados)   # o tipo certo está entre os que parseiam


if __name__ == "__main__":
    unittest.main()
