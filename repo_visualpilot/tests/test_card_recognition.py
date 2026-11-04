"""Testes unitários para o Reconhecimento de Cartas (Hero + Board), ROIs e Baralho de 4 cores."""
import unittest
from visualpilot.pppoker.card_recognition import (
    CardRecognitionEngine,
    SuitDetector,
    RankClassifier,
    PokerHandEvaluator,
    scale_roi,
    rgb_to_hsv_pure
)


class TestCardRecognition(unittest.TestCase):

    def test_rgb_to_hsv_pure(self):
        """Testa a conversão RGB -> HSV em Python puro."""
        # Vermelho puro
        h, s, v = rgb_to_hsv_pure(255, 0, 0)
        self.assertAlmostEqual(h, 0.0, delta=1.0)
        self.assertGreater(s, 200.0)

        # Verde puro
        h, s, v = rgb_to_hsv_pure(0, 255, 0)
        self.assertAlmostEqual(h, 60.0, delta=2.0)

        # Azul puro
        h, s, v = rgb_to_hsv_pure(0, 0, 255)
        self.assertAlmostEqual(h, 120.0, delta=2.0)

    def test_suit_detector_4_color(self):
        """Testa a diferenciação exata dos 4 naipes coloridos do PPPoker."""
        # Vermelho (Copas - ♥)
        red_crop = (220, 30, 30)
        suit, conf, _, _ = SuitDetector.classify_crop(red_crop, four_color_mode=True)
        self.assertEqual(suit, "h")
        self.assertGreater(conf, 0.70)

        # Azul (Ouros - ♦)
        blue_crop = (30, 80, 230)
        suit, conf, _, _ = SuitDetector.classify_crop(blue_crop, four_color_mode=True)
        self.assertEqual(suit, "d")
        self.assertGreater(conf, 0.70)

        # Verde (Paus - ♣)
        green_crop = (30, 180, 50)
        suit, conf, _, _ = SuitDetector.classify_crop(green_crop, four_color_mode=True)
        self.assertEqual(suit, "c")
        self.assertGreater(conf, 0.70)

        # Preto / Slate (Espadas - ♠)
        slate_crop = (25, 30, 35)
        suit, conf, _, _ = SuitDetector.classify_crop(slate_crop, four_color_mode=True)
        self.assertEqual(suit, "s")
        self.assertGreater(conf, 0.70)

    def test_rank_classifier(self):
        """Testa a classificação de ranks com e sem hint de OCR."""
        dummy_crop = (255, 255, 255)
        
        # Teste com hint de 10 -> T
        rank, conf = RankClassifier.classify_crop(dummy_crop, ocr_hint="10")
        self.assertEqual(rank, "T")
        self.assertGreaterEqual(conf, 0.90)

        # Teste com hint A
        rank, conf = RankClassifier.classify_crop(dummy_crop, ocr_hint="A")
        self.assertEqual(rank, "A")
        self.assertGreaterEqual(conf, 0.90)

    def test_roi_scaling(self):
        """Testa o redimensionamento proporcional de ROIs entre geometrias."""
        base_box = (565, 175, 730, 265)
        # Escala 1:1 deve manter idêntico
        scaled_same = scale_roi(base_box, 787, 1470, 787, 1470)
        self.assertEqual(scaled_same, base_box)

        # Escala 2x deve dobrar
        scaled_double = scale_roi(base_box, 787, 1470, 787 * 2, 1470 * 2)
        self.assertEqual(scaled_double, (1130, 350, 1460, 530))

    def test_hand_evaluator_royal_flush(self):
        """Testa a detecção de Royal Flush."""
        board = ["As", "Ks", "Qs", "Js", "Ts"]
        hero = ["2h", "3c"]
        eval_res = PokerHandEvaluator.evaluate(board, hero)
        self.assertEqual(eval_res.score, 10)
        self.assertEqual(eval_res.category, "Royal Flush")

    def test_hand_evaluator_full_house(self):
        """Testa a detecção de Full House."""
        board = ["Ah", "As", "Kd", "2c", "7h"]
        hero = ["Ac", "Kh"]
        eval_res = PokerHandEvaluator.evaluate(board, hero)
        self.assertEqual(eval_res.score, 7)
        self.assertIn("Full House", eval_res.category)

    def test_engine_full_frame_and_duplicates(self):
        """Testa a execução no motor com verificação de 52 cartas."""
        engine = CardRecognitionEngine(four_color_mode=True)
        color_hints = {
            "flop_1": (15, 23, 42),   # s
            "flop_2": (220, 38, 38),  # h
            "flop_3": (37, 99, 235),  # d
            "turn":   (22, 163, 74),  # c
            "river":  (15, 23, 42),   # s
            "hero_1": (220, 38, 38),  # h
            "hero_2": (37, 99, 235),  # d
        }
        ocr_hints = {
            "flop_1": "A", "flop_2": "K", "flop_3": "Q", "turn": "J", "river": "T",
            "hero_1": "A", "hero_2": "A"
        }
        # Board: As, Kh, Qd, Jc, Ts
        # Hero: Ah, Ad (Par de Áses)
        # Total: 7 cartas únicas -> Sequência Real (Royal Straight A-K-Q-J-T) ou Trinca/Dois Pares
        res = engine.read_table_frame(None, ocr_hints=ocr_hints, color_hints=color_hints)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["invariant_passed"])
        self.assertEqual(len(res["cards"]), 7)

        # Leitura com duplicata forçada (dois 'As')
        ocr_dup = dict(ocr_hints)
        ocr_dup["hero_1"] = "A"
        color_dup = dict(color_hints)
        color_dup["hero_1"] = (15, 23, 42) # Também vira 's' -> As duplicado!
        res_dup = engine.read_table_frame(None, ocr_hints=ocr_dup, color_hints=color_dup)
        self.assertEqual(res_dup["status"], "DUPLICATE_CARD_DETECTED")
        self.assertFalse(res_dup["invariant_passed"])
        self.assertIn("As", res_dup["duplicates"])


if __name__ == "__main__":
    unittest.main()
