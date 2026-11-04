"""Testes unitários para detecção e automação dos botões de ação do Hero (Fold, Check, Call, Raise)."""
import unittest
from visualpilot.pppoker.hero_action_detector import (
    HeroActionDetector,
    parse_action_text,
    calculate_button_center,
    calculate_jittered_click_point,
    scale_roi
)


class TestHeroActions(unittest.TestCase):

    def test_parse_action_text(self):
        """Testa a extração correta de tipo de ação, quantia e unidade."""
        # Fold
        res = parse_action_text("Fold")
        self.assertTrue(res["valid"])
        self.assertEqual(res["action_type"], "fold")
        self.assertEqual(res["label"], "Fold")
        self.assertIsNone(res["amount"])

        # Check
        res = parse_action_text("Check")
        self.assertTrue(res["valid"])
        self.assertEqual(res["action_type"], "check")
        self.assertEqual(res["label"], "Check")

        # Call com BB
        res = parse_action_text("Call 2.5 BB")
        self.assertTrue(res["valid"])
        self.assertEqual(res["action_type"], "call")
        self.assertEqual(res["amount"], 2.5)
        self.assertEqual(res["unit"], "BB")

        # Raise com vírgula decimal
        res = parse_action_text("Raise 9,5 BB")
        self.assertTrue(res["valid"])
        self.assertEqual(res["action_type"], "raise")
        self.assertEqual(res["amount"], 9.5)
        self.assertEqual(res["unit"], "BB")

        # All-in
        res = parse_action_text("All-in 54 BB")
        self.assertTrue(res["valid"])
        self.assertEqual(res["action_type"], "all_in")
        self.assertEqual(res["amount"], 54.0)

    def test_calculate_button_center(self):
        """Testa o cálculo geométrico do centro do botão."""
        box = (1370, 20, 1450, 260)
        cx, cy = calculate_button_center(box)
        self.assertEqual(cx, 140)
        self.assertEqual(cy, 1410)

    def test_jittered_click_point_in_bounds(self):
        """Testa que o clique com dispersão gaussiana de camuflagem fica dentro da caixa do botão."""
        box = (1370, 20, 1450, 260)
        ymin, xmin, ymax, xmax = box
        for _ in range(50):
            jx, jy = calculate_jittered_click_point(box, sigma=4.0)
            self.assertGreater(jx, xmin)
            self.assertLess(jx, xmax)
            self.assertGreater(jy, ymin)
            self.assertLess(jy, ymax)

    def test_detector_snapshot_generation(self):
        """Testa a geração do snapshot completo de ações do Hero."""
        detector = HeroActionDetector()
        mock_data = {
            "is_hero_turn": True,
            "time_bank_sec": 10.0,
            "time_bank_total_sec": 15.0,
            "pot_bb": 20.0,
            "bet_to_call_bb": 4.0,
            "buttons": [
                {"id": "btn_left", "text": "Fold"},
                {"id": "btn_center", "text": "Call 4.0 BB"},
                {"id": "btn_right", "text": "Raise 12.0 BB"}
            ]
        }
        snap = detector.detect_actions(mock_scenario=mock_data)
        self.assertTrue(snap.is_hero_turn)
        self.assertAlmostEqual(snap.time_bank_percent, 66.7, delta=0.5)
        self.assertEqual(len(snap.buttons), 3)
        self.assertEqual(snap.buttons[0].label, "Fold")
        self.assertEqual(snap.buttons[1].amount, 4.0)
        self.assertEqual(snap.buttons[2].amount, 12.0)
        self.assertEqual(len(snap.sizing_options), 5)


if __name__ == "__main__":
    unittest.main()
