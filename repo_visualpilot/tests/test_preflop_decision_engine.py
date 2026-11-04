"""Testes unitários para o Motor de Decisão Pré-Flop GTO."""
import unittest
from visualpilot.pppoker.preflop_decision_engine import (
    PreflopDecisionEngine,
    ALL_169_HANDS,
    ALL_169_HANDS_MATRIX,
    TOTAL_COMBOS,
    get_combos_count
)

class TestPreflopDecisionEngine(unittest.TestCase):

    def setUp(self):
        self.engine = PreflopDecisionEngine()

    def test_canonical_hand_representation(self):
        # Pares
        self.assertEqual(self.engine.canonical_hand("Ah", "Ad"), "AA")
        self.assertEqual(self.engine.canonical_hand("7c", "7s"), "77")
        # Suited
        self.assertEqual(self.engine.canonical_hand("Ah", "Kh"), "AKs")
        self.assertEqual(self.engine.canonical_hand("5d", "Ad"), "A5s")
        self.assertEqual(self.engine.canonical_hand("9s", "Ts"), "T9s")
        # Offsuit
        self.assertEqual(self.engine.canonical_hand("Ah", "Kd"), "AKo")
        self.assertEqual(self.engine.canonical_hand("2c", "7h"), "72o")
        self.assertEqual(self.engine.canonical_hand("Jh", "Qc"), "QJo")

    def test_169_hands_matrix_integrity(self):
        self.assertEqual(len(ALL_169_HANDS_MATRIX), 13)
        self.assertEqual(len(ALL_169_HANDS), 169)
        self.assertEqual(len(set(ALL_169_HANDS)), 169)

        # Verificar contagem de combinações: 1326 no total
        total = sum(get_combos_count(h) for h in ALL_169_HANDS)
        self.assertEqual(total, TOTAL_COMBOS)

    def test_rfi_utg_tight_range(self):
        # AA deve ser raise 100%
        aa_res = self.engine.evaluate_hand(["Ah", "As"], "UTG", "RFI", 100.0)
        self.assertEqual(aa_res.recommended_action, "RAISE")
        self.assertEqual(aa_res.strategy_mix.get("RAISE"), 1.0)
        self.assertTrue(aa_res.in_range)
        self.assertEqual(aa_res.category, "VALUE_RAISE")

        # 72o deve ser FOLD
        trash_res = self.engine.evaluate_hand(["7c", "2h"], "UTG", "RFI", 100.0)
        self.assertEqual(trash_res.recommended_action, "FOLD")
        self.assertFalse(trash_res.in_range)

        # Estatísticas do UTG devem ser ~14-16%
        stats = self.engine.get_range_statistics("UTG", "RFI", 100.0)
        self.assertGreater(stats.percentage_played, 12.0)
        self.assertLess(stats.percentage_played, 18.0)

    def test_rfi_btn_wide_range(self):
        # BTN deve abrir muito mais mãos que UTG
        btn_stats = self.engine.get_range_statistics("BTN", "RFI", 100.0)
        utg_stats = self.engine.get_range_statistics("UTG", "RFI", 100.0)
        self.assertGreater(btn_stats.percentage_played, utg_stats.percentage_played)
        self.assertGreater(btn_stats.percentage_played, 40.0)

        # Mãos como K7s ou 87o devem estar no range de abertura do BTN
        k7s_res = self.engine.evaluate_hand(["Ks", "7s"], "BTN", "RFI", 100.0)
        self.assertEqual(k7s_res.recommended_action, "RAISE")
        self.assertTrue(k7s_res.in_range)

    def test_bb_defense_vs_btn(self):
        # T9s deve ser CALL contra open do BTN
        t9s_res = self.engine.evaluate_hand(["Th", "9h"], "BB", "VS_RFI", 100.0, vs_position="BTN")
        self.assertEqual(t9s_res.recommended_action, "CALL")
        self.assertTrue(t9s_res.in_range)

        # AKs deve ser 3-BET (RAISE)
        aks_res = self.engine.evaluate_hand(["As", "Ks"], "BB", "VS_RFI", 100.0, vs_position="BTN")
        self.assertEqual(aks_res.recommended_action, "RAISE")
        self.assertGreater(aks_res.recommended_sizing_bb, 7.0)

    def test_push_fold_short_stack(self):
        # Em 15 BB, BTN shova all-in com mãos fortes
        shove_res = self.engine.evaluate_hand(["As", "Qs"], "BTN", "PUSH_FOLD", 15.0)
        self.assertEqual(shove_res.recommended_action, "ALL_IN")
        self.assertEqual(shove_res.recommended_sizing_bb, 15.0)

    def test_simulation_random_hands(self):
        sim = self.engine.simulate_random_hands("CO", "RFI", 100.0, num_trials=100)
        self.assertEqual(sim["trials"], 100)
        self.assertIn("distribution", sim)
        self.assertGreater(sim["distribution"]["FOLD"], 30)

if __name__ == "__main__":
    unittest.main()
