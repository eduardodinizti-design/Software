"""Testes unitários para o Motor GTO Pós-Flop em Potes 3-Bet."""
import unittest
from visualpilot.pppoker.postflop_gto_engine import (
    PostflopGtoEngine,
    rank5,
    rank7,
    classify_made_hand,
    expand_range_combos,
    PRESET_3BET_VILLAIN_RANGES
)

class TestPostflopGtoEngine(unittest.TestCase):

    def setUp(self):
        self.engine = PostflopGtoEngine()

    def test_rank5_and_rank7_evaluations(self):
        # Royal flush / Straight flush
        sf = rank5(("As", "Ks", "Qs", "Js", "Ts"))
        self.assertEqual(sf[0], 8)
        self.assertEqual(sf[1], 14)

        # Full House
        fh = rank5(("Ah", "As", "Ac", "Kd", "Kh"))
        self.assertEqual(fh[0], 6)
        self.assertEqual(fh[1], 14)
        self.assertEqual(fh[2], 13)

        # Wheel Straight (A-2-3-4-5)
        wheel = rank5(("Ah", "2s", "3c", "4d", "5h"))
        self.assertEqual(wheel[0], 4)
        self.assertEqual(wheel[1], 5)

        # Test rank7 with two pairs vs trips
        cards_trips = ["Ah", "As", "Ac", "Kd", "Qc", "2s", "3d"]
        res_trips = rank7(cards_trips)
        self.assertEqual(res_trips[0], 3)
        self.assertEqual(res_trips[1], 14)

    def test_hand_classification(self):
        # Overpair
        c1 = classify_made_hand(["Kh", "Kd"], ["Qs", "8c", "2d"])
        self.assertIn("Overpair", c1)

        # Top pair
        c2 = classify_made_hand(["Ah", "Kd"], ["As", "8c", "2d"])
        self.assertIn("Top Pair", c2)

        # Flush
        c3 = classify_made_hand(["Kh", "Qh"], ["Ah", "8h", "2h"])
        self.assertIn("Flush", c3)

    def test_expand_range_combos_blockers(self):
        # Range com AA e KK (12 combos sem blockers)
        range_test = {"AA": 1.0, "KK": 1.0}
        # Hero tem As, Board tem Ad -> Sobram apenas 1 combo de AA (Ah-Ac) e 6 combos de KK
        dead = ["As", "Ad", "2c"]
        combos = expand_range_combos(range_test, dead)
        self.assertEqual(len(combos), 7)  # 1 combo de AA + 6 combos de KK

    def test_equity_on_river_exact(self):
        # River com board de 5 cartas
        hero = ["As", "Ah"]  # Set de Ases
        board = ["Ad", "Kd", "Qc", "7s", "2h"]
        villain_range = {"KK": 1.0, "QQ": 1.0, "AKs": 1.0}

        res = self.engine.calculate_equity(hero, board, villain_range)
        self.assertEqual(res.street, "RIVER")
        # Hero tem Top Set contra Sets menores e Top Two Pair -> 100% de vitória
        self.assertEqual(res.hero_equity_pct, 100.0)
        self.assertIn("BET", res.recommended_gto_action)

    def test_equity_flop_3bet_pot(self):
        # Flop A♠ 8♥ 3♦: Hero tem AK (Top Pair Top Kicker)
        hero = ["As", "Kd"]
        board = ["Ah", "8c", "3s"]
        res = self.engine.calculate_equity(hero, board, "LINEAR_3BET", trials=1000)

        self.assertEqual(res.street, "FLOP")
        self.assertGreater(res.hero_equity_pct, 60.0)
        self.assertGreater(res.combos_evaluated, 10)
        self.assertIn("BET", res.recommended_gto_action)

    def test_board_texture_classification(self):
        self.assertIn("Rainbow", self.engine.detect_board_texture(["As", "Kh", "Qd"]))
        self.assertIn("Monotone", self.engine.detect_board_texture(["As", "Ks", "2s"]))
        self.assertIn("Pareado", self.engine.detect_board_texture(["7s", "7d", "2c"]))

if __name__ == "__main__":
    unittest.main()
