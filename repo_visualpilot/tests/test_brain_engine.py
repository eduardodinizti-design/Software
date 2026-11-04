"""
Unit tests for Bot Brain, Human Feedback & Lines of Play Analyzer
"""

import unittest
from visualpilot.pppoker.brain_engine import (
    BotBrain,
    PreflopRangeFeeder,
    HumanFeedbackEngine,
    LinesOfPlayAnalyzer,
    LeakDetectorEngine,
    EvolutionaryTrainer
)


class TestBrainEngine(unittest.TestCase):

    def setUp(self):
        self.brain = BotBrain()

    def test_preflop_feeder_default_profiles(self):
        feeder = self.brain.range_feeder
        self.assertIn("MTT_DEEP_40BB", feeder.tournament_profiles)
        self.assertIn("PKO_BOUNTY_25BB", feeder.tournament_profiles)
        self.assertIn("TURBO_PUSH_FOLD_15BB", feeder.tournament_profiles)

        btn_range = feeder.get_range("MTT_DEEP_40BB", "BTN")
        self.assertIn("AA", btn_range)
        self.assertIn("KQs", btn_range)

    def test_import_external_ranges_json(self):
        feeder = self.brain.range_feeder
        custom_ranges = {
            "UTG": ["AA", "KK", "AKs"],
            "BTN": ["AA", "KK", "QQ", "JJ", "AKs", "AKo", "76s"]
        }
        res = feeder.import_ranges_json("CUSTOM_MYSTERY", "Mystery Bounty Custom 30BB", custom_ranges)
        self.assertTrue(res)
        self.assertIn("CUSTOM_MYSTERY", feeder.tournament_profiles)
        self.assertEqual(feeder.get_range("CUSTOM_MYSTERY", "UTG"), ["AA", "KK", "AKs"])

    def test_human_feedback_engine(self):
        feedback_engine = self.brain.human_feedback
        self.assertGreaterEqual(len(feedback_engine.hand_records), 4)

        # Submit positive feedback (CORRECT)
        res_correct = feedback_engine.register_feedback(
            hand_id="hand_10482",
            feedback="CORRECT",
            notes="Decisão perfeitamente avaliada"
        )
        self.assertTrue(res_correct["success"])
        self.assertGreater(res_correct["new_weight"], 1.0)

        # Submit negative feedback (MISTAKE)
        res_mistake = feedback_engine.register_feedback(
            hand_id="hand_10479",
            feedback="MISTAKE",
            correction_action="Fold obrigatório pré-flop",
            notes="Call com KJo foi dreno"
        )
        self.assertTrue(res_mistake["success"])
        self.assertLess(res_mistake["new_weight"], 1.0)

    def test_lines_of_play_analyzer(self):
        analyzer = self.brain.lines_analyzer
        self.assertGreaterEqual(len(analyzer.lines), 5)

        summary = analyzer.get_lines_summary()
        self.assertGreater(summary["total_lines_tracked"], 4)
        self.assertGreater(summary["profitable_lines"], 0)
        self.assertGreater(summary["unprofitable_lines"], 0)

        # Verify line 1 (Triple barrel IP) is profitable
        line_01 = analyzer.lines[0]
        self.assertEqual(line_01["id"], "line_01")
        self.assertGreater(line_01["winrate_bb_100"], 50.0)

    def test_leak_detector_identification_and_fix(self):
        detector = self.brain.leak_detector
        self.assertGreaterEqual(len(detector.leaks), 3)
        self.assertGreaterEqual(len(detector.profitable_lines), 3)
        self.assertGreaterEqual(len(detector.site_analytics), 4)

        leak_01 = detector.leaks[0]
        initial_loss = leak_01["loss_bb_per_100"]

        fix_res = detector.apply_auto_fix_for_leak("leak_01")
        self.assertTrue(fix_res["success"])
        self.assertEqual(leak_01["severity"], "RESOLVED")
        self.assertLess(abs(leak_01["loss_bb_per_100"]), abs(initial_loss))

    def test_evolutionary_training_cycle(self):
        trainer = self.brain.trainer
        initial_epochs = trainer.training_epochs_completed

        cycle_res = trainer.run_training_cycle(epochs=50)
        self.assertTrue(cycle_res["success"])
        self.assertEqual(trainer.training_epochs_completed, initial_epochs + 50)
        self.assertGreater(cycle_res["improved_winrate"], cycle_res["previous_winrate"])
        self.assertIn("cbet_dry_ip", trainer.postflop_weights)

    def test_export_lines_with_hands_json(self):
        analyzer = self.brain.lines_analyzer
        export_payload = analyzer.export_lines_with_hands_json()

        self.assertIn("export_metadata", export_payload)
        self.assertIn("lines_of_play", export_payload)
        metadata = export_payload["export_metadata"]
        self.assertEqual(metadata["system"], "VisualPilot Brain & Evolutionary Engine")
        self.assertIn("summary", metadata)

        lines = export_payload["lines_of_play"]
        self.assertGreaterEqual(len(lines), 5)
        # Verify first line has detailed played hands
        first_line = lines[0]
        self.assertIn("played_hands", first_line)
        self.assertGreaterEqual(len(first_line["played_hands"]), 2)
        sample_hand = first_line["played_hands"][0]
        self.assertIn("hand_id", sample_hand)
        self.assertIn("hole_cards", sample_hand)
        self.assertIn("combo", sample_hand)
        self.assertIn("position", sample_hand)
        self.assertIn("outcome_bb", sample_hand)
        self.assertIn("result", sample_hand)

    def test_compare_ev_expected_vs_real(self):
        analyzer = self.brain.lines_analyzer
        res = analyzer.compare_ev_expected_vs_real()

        self.assertIn("comparisons", res)
        self.assertIn("profitable_patterns_count", res)
        self.assertIn("losing_patterns_count", res)
        self.assertGreater(res["profitable_patterns_count"], 0)
        self.assertGreater(res["losing_patterns_count"], 0)

        # Verify 3-bet light vs 3-bet value
        three_bet_items = [c for c in res["comparisons"] if c["category"] == "3BET"]
        self.assertEqual(len(three_bet_items), 2)
        three_bet_light = next(c for c in three_bet_items if c["id"] == "3bet_light")
        three_bet_value = next(c for c in three_bet_items if c["id"] == "3bet_value")
        self.assertEqual(three_bet_light["pattern"], "PROFITABLE")
        self.assertGreater(three_bet_light["actual_ev_bb100"], three_bet_light["expected_ev_bb100"])
        self.assertGreater(three_bet_value["actual_ev_bb100"], 80.0)

    def test_learning_rate_and_session_errors(self):
        feedback = self.brain.human_feedback
        # Test custom learning rate configuration
        config_res = feedback.configure_learning_rate(
            learning_rate=0.16,
            weight_correct=0.20,
            weight_mistake=-0.40,
            postflop_multiplier=2.5
        )
        self.assertTrue(config_res["success"])
        self.assertEqual(feedback.learning_rate, 0.16)
        self.assertEqual(feedback.weight_correct, 0.20)

        # Test session error history
        error_hist = feedback.get_session_error_history()
        self.assertIn("session_blocks", error_hist)
        self.assertEqual(len(error_hist["session_blocks"]), 5)
        self.assertGreater(error_hist["reduction_percentage"], 50.0)
        self.assertIn("category_totals", error_hist)
        self.assertIn("range_incorreto", error_hist["category_totals"])
        self.assertIn("leitura_board_errada", error_hist["category_totals"])
        self.assertIn("gestao_pote_falha", error_hist["category_totals"])


if __name__ == "__main__":
    unittest.main()
