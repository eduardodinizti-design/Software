"""Testes unitários para o OCR Numérico da Mesa, Stacks, Pote, Posições e Dealer."""
import unittest
from visualpilot.pppoker.table_numerical_ocr import (
    TableNumericalOcrEngine,
    parse_numeric_amount,
    calculate_positions_6max,
    calculate_pot_odds,
    calculate_spr,
    scale_roi,
    SeatNumericalData
)


class TestTableNumericalOcr(unittest.TestCase):

    def test_parse_numeric_amount(self):
        """Testa a extração precisa de valores numéricos em BBs e fichas."""
        # 14.5 BB
        val, unit = parse_numeric_amount("14.5 BB")
        self.assertEqual(val, 14.5)
        self.assertEqual(unit, "BB")

        # Vírgula decimal: 2,5 BB
        val, unit = parse_numeric_amount("2,5 BB")
        self.assertEqual(val, 2.5)
        self.assertEqual(unit, "BB")

        # Milhar: 1,450
        val, unit = parse_numeric_amount("1,450")
        self.assertEqual(val, 1450.0)
        self.assertEqual(unit, "chips")

        # Multiplicador K: 1.2K
        val, unit = parse_numeric_amount("1.2K")
        self.assertEqual(val, 1200.0)

    def test_calculate_pot_odds(self):
        """Testa o cálculo matemático de Pot Odds."""
        # Pagar 5 BB em um pote de 15 BB -> Pot Odds = 5 / (15 + 5) = 25.0%
        odds = calculate_pot_odds(5.0, 15.0)
        self.assertEqual(odds, 25.0)

        # Sem aposta enfrentada (0 BB) -> 0%
        odds_zero = calculate_pot_odds(0.0, 20.0)
        self.assertEqual(odds_zero, 0.0)

    def test_calculate_spr(self):
        """Testa o cálculo do Stack-to-Pot Ratio (SPR) e classificação."""
        # Stack 40 BB, Pote 10 BB -> SPR = 4.0 (Low)
        spr, cat = calculate_spr(40.0, 10.0)
        self.assertEqual(spr, 4.0)
        self.assertIn("Low", cat)

        # Stack 150 BB, Pote 10 BB -> SPR = 15.0 (Deep)
        spr_deep, cat_deep = calculate_spr(150.0, 10.0)
        self.assertEqual(spr_deep, 15.0)
        self.assertIn("Deep", cat_deep)

    def test_calculate_positions_6max(self):
        """Testa a atribuição determinística de posições relativas (BTN, SB, BB, UTG, MP, CO)."""
        seats = [
            SeatNumericalData(seat_number=i, player_name=f"P{i}", stack_bb=100.0, stack_chips=1000.0, current_bet_bb=0.0)
            for i in range(1, 7)
        ]
        # Se Dealer for Seat 1:
        # Seat 1 = BTN
        # Seat 2 = SB
        # Seat 3 = BB
        # Seat 4 = UTG
        # Seat 5 = MP
        # Seat 6 = CO
        calculate_positions_6max(1, seats)
        self.assertEqual(seats[0].position_label, "BTN")
        self.assertTrue(seats[0].is_dealer)
        self.assertEqual(seats[1].position_label, "SB")
        self.assertEqual(seats[2].position_label, "BB")
        self.assertEqual(seats[3].position_label, "UTG")
        self.assertEqual(seats[4].position_label, "MP")
        self.assertEqual(seats[5].position_label, "CO")

    def test_calculate_positions_heads_up(self):
        """Testa a regra especial de Heads-up (BTN/SB vs BB)."""
        seats = [
            SeatNumericalData(seat_number=1, player_name="P1", stack_bb=100.0, stack_chips=1000.0, current_bet_bb=0.0),
            SeatNumericalData(seat_number=2, player_name="P2", stack_bb=100.0, stack_chips=1000.0, current_bet_bb=0.0)
        ]
        calculate_positions_6max(1, seats)
        self.assertEqual(seats[0].position_label, "BTN/SB")
        self.assertEqual(seats[1].position_label, "BB")

    def test_engine_snapshot_and_export(self):
        """Testa a execução no motor e consistência de dados."""
        engine = TableNumericalOcrEngine()
        snap = engine.process_table_state()
        self.assertEqual(snap.status, "SUCCESS")
        self.assertEqual(len(snap.seats), 6)
        self.assertGreater(snap.total_pot_bb, 0)
        self.assertEqual(snap.hero_seat, 5)

    def test_ocr_temporal_stability_cache(self):
        """Testa o filtro de confiança e estabilização temporal do OCR."""
        from visualpilot.pppoker.table_numerical_ocr import OcrTemporalStabilityCache
        cache = OcrTemporalStabilityCache(min_confidence=0.80, consecutive_required=2)
        
        val, stable = cache.filter_value("pot", 15.0, 0.60)
        self.assertFalse(stable)
        self.assertIsNone(val)

        val, stable = cache.filter_value("pot", 15.0, 0.95)
        self.assertFalse(stable)

        val, stable = cache.filter_value("pot", 15.0, 0.92)
        self.assertTrue(stable)
        self.assertEqual(val, 15.0)


if __name__ == "__main__":
    unittest.main()
