"""Testes unitários para CalibrateWindow e TableBotRunner (PPPoker)."""
import json
from pathlib import Path
import unittest

from visualpilot.pppoker.calibrate_window import (
    WindowCalibrator,
    detect_windows_dpi_factor,
)
from visualpilot.pppoker.table_bot_runner import (
    TableBotRunner,
    LiveGameDecision,
    canonical_hand_name,
    format_card_pt,
)
from visualpilot.pppoker.hero_action_detector import ActionButton


class TestTableBotRunner(unittest.TestCase):

    def test_canonical_hand_name(self):
        self.assertEqual(canonical_hand_name("As", "Kh"), "AKo")
        self.assertEqual(canonical_hand_name("Kh", "As"), "AKo")
        self.assertEqual(canonical_hand_name("Qd", "Jd"), "QJs")
        self.assertEqual(canonical_hand_name("Ts", "Tc"), "TT")
        self.assertEqual(canonical_hand_name("7c", "2h"), "72o")

    def test_format_card_pt(self):
        self.assertEqual(format_card_pt("As"), "A♠")
        self.assertEqual(format_card_pt("Kh"), "K♥")
        self.assertEqual(format_card_pt("Qd"), "Q♦")
        self.assertEqual(format_card_pt("Jc"), "J♣")

    def test_window_calibrator_report(self):
        calibrator = WindowCalibrator(target_title="PPPoker")
        report = calibrator.run_calibration()
        self.assertIsNotNone(report)
        self.assertTrue(report.is_window_found)
        self.assertGreaterEqual(report.calibration_score, 80)
        self.assertGreater(len(report.rois_audit), 5)
        # Verifica se botões de ação estão no audit
        names = [r.name for r in report.rois_audit]
        self.assertIn("btn_left", names)
        self.assertIn("btn_right", names)
        self.assertIn("total_pot", names)

    def test_table_bot_runner_preflop_decision(self):
        runner = TableBotRunner(mode="dry-run", interval_ms=100)
        buttons = [
            ActionButton("btn_left", "fold", "Fold", (1370, 20, 1455, 255)),
            ActionButton("btn_center", "call", "Call", (1370, 270, 1455, 515)),
            ActionButton("btn_right", "raise", "Raise", (1370, 530, 1455, 770)),
        ]
        # Hero no BTN com AA pré-flop deve dar RAISE
        action, sizing, eq, ev, btn_id, label, sizing_btn = runner.query_decision(
            hero_cards=["As", "Ah"],
            board_cards=[],
            hero_pos="BTN",
            pot_bb=1.5,
            bet_to_call_bb=1.0,
            stack_bb=100.0,
            buttons=buttons,
        )
        self.assertIn(action, ("RAISE", "ALL_IN"))
        self.assertEqual(btn_id, "btn_right")
        self.assertGreater(ev, 0.0)

    def test_table_bot_runner_postflop_decision(self):
        runner = TableBotRunner(mode="dry-run", interval_ms=100)
        buttons = [
            ActionButton("btn_left", "fold", "Fold", (1370, 20, 1455, 255)),
            ActionButton("btn_center", "check", "Check", (1370, 270, 1455, 515)),
            ActionButton("btn_right", "bet", "Bet", (1370, 530, 1455, 770)),
        ]
        # Hero com trinca de Ases no flop
        action, sizing, eq, ev, btn_id, label, sizing_btn = runner.query_decision(
            hero_cards=["As", "Ah"],
            board_cards=["Ad", "7c", "2s"],
            hero_pos="BTN",
            pot_bb=6.0,
            bet_to_call_bb=0.0,
            stack_bb=97.0,
            buttons=buttons,
        )
        self.assertIn(action, ("BET_50", "BET_33", "CHECK"))
        self.assertGreater(eq, 60.0)

    def test_dry_run_safety_suppression(self):
        runner = TableBotRunner(mode="dry-run")
        decision = LiveGameDecision(
            timestamp="2026-11-01T15:00:00Z",
            hand_id="H-0001",
            street="PREFLOP",
            hero_position="BTN",
            hero_cards=["As", "Kh"],
            board_cards=[],
            pot_total_bb=2.5,
            bet_to_call_bb=1.0,
            stack_bb=100.0,
            recommended_action="RAISE",
            recommended_sizing_bb=2.5,
            equity_pct=60.0,
            expected_ev_bb=2.0,
            target_button_id="btn_right",
            target_button_label="Raise",
            click_coordinates=(650, 1410),
            is_live_click_executed=False,
            status_message="Test",
        )
        buttons = [ActionButton("btn_right", "raise", "Raise", (1370, 530, 1455, 770))]
        # Em modo dry-run, execute_live_action NUNCA dispara clique e retorna False
        executed = runner.execute_live_action(decision, buttons, (0, 0, 787, 1470))
        self.assertFalse(executed)

    def test_telemetry_snapshot_export(self):
        test_path = "public/test_live_stream.json"
        runner = TableBotRunner(mode="dry-run", telemetry_path=test_path)
        snap = runner.action_detector.detect_actions()
        runner.export_telemetry_snapshot(snap, None)

        p = Path(test_path)
        self.assertTrue(p.exists())
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["mode"], "dry-run")
        self.assertEqual(data["status"], "STOPPED")
        # Limpeza
        p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
