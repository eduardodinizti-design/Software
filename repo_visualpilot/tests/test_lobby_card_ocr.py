"""Testes unitários para o Módulo 3: OCR por Cartão do Lobby PPPoker."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from visualpilot.pppoker.lobby_card_ocr import (
    extract_buyin,
    extract_start_time,
    extract_tournament_name,
    parse_card_lines,
    process_cards_ocr,
)

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS_FIXTURE = ROOT.parent / "public" / "modulo2_evidencias" / "segments.json"
CARDS_DIR_FIXTURE = ROOT.parent / "public" / "modulo2_evidencias"


class LobbyCardOCRTests(unittest.TestCase):
    def test_buyin_parsing_cases(self):
        # 1. Valor simples
        val, parts, _ = extract_buyin(["Buy-in: 50"])
        self.assertEqual(val, Decimal("50"))
        self.assertEqual(parts, [Decimal("50")])

        # 2. Valor com prefixo duplicado (2 200)
        val, parts, _ = extract_buyin(["Buy-in: 2 200"])
        self.assertEqual(val, Decimal("200"))

        # 3. Parcelas somadas com +
        val, parts, _ = extract_buyin(["Buy-in: 28.34 + 14.16 + 7.50"])
        self.assertEqual(val, Decimal("50.00"))
        self.assertEqual(len(parts), 3)

        # 4. Total com detalhamento em parênteses
        val, parts, _ = extract_buyin(["Buy-in: 50 (28.34+14.16+7.5)"])
        self.assertEqual(val, Decimal("50"))

        # 5. Premiação isolada nunca é interpretada como buy-in
        val, _, _ = extract_buyin(["Premiacao: 10,000", "Garantido: 50,000"])
        self.assertIsNone(val)

    def test_start_time_extraction(self):
        # Formatos válidos
        self.assertEqual(extract_start_time(["Horariodeinicio: 10/31 22:00"]), "10/31 22:00")
        self.assertEqual(extract_start_time(["Inicio: 5/2 14:30"]), "05/02 14:30")
        self.assertEqual(extract_start_time(["10/31 18:00"]), "10/31 18:00")

        # Formatos inválidos (ex: contagem de mesa 0/6 ou horas inexistentes)
        self.assertIsNone(extract_start_time(["0/6 01:00:00", "Blinds: 1/2"]))
        self.assertIsNone(extract_start_time(["13/45 25:99"]))

    def test_tournament_name_extraction(self):
        lines = ["CORUJAOHYPERPKO10K", "Buy-in: 50", "PKO 10min", "PPST NLH", "Horariodeinicio: 10/31 22:00"]
        name = extract_tournament_name(lines)
        self.assertIn("CORUJAO", name)

    def test_parse_corujao_card_is_eligible(self):
        lines = ["CORUJAOHYPERPKO10K", "Buy-in: 50", "PKO 10min", "PPST NLH", "Horariodeinicio: 10/31 22:00"]
        card = parse_card_lines(lines, max_buyin=50.0)
        self.assertTrue(card["eligible"])
        self.assertEqual(card["buyin"], "50")
        self.assertEqual(card["start_time"], "10/31 22:00")
        self.assertEqual(card["status"], "open")
        self.assertEqual(card["game_format"], "MTT PKO")
        self.assertEqual(card["rejection_reasons"], [])

    def test_parse_freezeout_exceeds_budget(self):
        lines = ["EARLY", "FREEZEOUT30KGTD", "Buy-in: 2 200", "30 20min", "PPST NLH", "Horariodeinicio: 10/31 18:00"]
        card = parse_card_lines(lines, max_buyin=50.0)
        self.assertFalse(card["eligible"])
        self.assertEqual(card["buyin"], "200")
        self.assertIn("buyin_exceeds_limit_50.0", card["rejection_reasons"])

    def test_parse_diamante_unreadable_buyin_rejected(self):
        lines = ["Premiacao: 10,000", "TORNEIO", "DIAMANTE 59 3min", "Horariodeinicio: 10/31 16:00"]
        card = parse_card_lines(lines, max_buyin=50.0)
        self.assertFalse(card["eligible"])
        self.assertIsNone(card["buyin"])
        self.assertIn("buyin_not_found_or_unreadable", card["rejection_reasons"])

    def test_parse_cash_game_rejected(self):
        lines = ["JACKPOT OMAHA-6", "Blinds: 1/2", "0/6 01:00:00", "PL06", "PF"]
        card = parse_card_lines(lines, max_buyin=50.0)
        self.assertFalse(card["eligible"])
        self.assertEqual(card["game_format"], "Cash Game (Blinds)")
        self.assertIn("cash_game_not_mtt", card["rejection_reasons"])

    def test_full_pipeline_on_real_fixture(self):
        if not SEGMENTS_FIXTURE.is_file():
            self.skipTest("Fixture segments.json ausente.")
        with tempfile.TemporaryDirectory() as tmpdir:
            report = process_cards_ocr(SEGMENTS_FIXTURE, CARDS_DIR_FIXTURE, tmpdir, max_buyin=50.0)
            self.assertEqual(report["total_cards_processed"], 5)
            # Apenas o Corujão deve ser elegível (buy-in 50, MTT, data válida)
            self.assertEqual(report["eligible_for_registration"], 1)

            tournaments = report["tournaments"]
            corujao = next(t for t in tournaments if "CORUJAO" in t["name"])
            self.assertTrue(corujao["eligible"])
            self.assertEqual(corujao["buyin"], "50")
            self.assertEqual(corujao["start_time"], "10/31 22:00")
            self.assertEqual(corujao["click_point_local"], [404.0, 992.0])

            # Arquivo gerado
            self.assertTrue((Path(tmpdir) / "tournaments.json").is_file())


if __name__ == "__main__":
    unittest.main()
