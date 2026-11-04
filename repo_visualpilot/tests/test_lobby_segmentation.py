"""Testes unitários para o Módulo 2: Segmentação de cartões do lobby PPPoker."""
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from visualpilot.pppoker.lobby_segmentation import (
    locate_lobby_window,
    segment_tournament_cards,
    annotate_segmented_lobby,
    save_segmentation_artifacts,
    process_lobby_image,
)

ROOT = Path(__file__).resolve().parents[1]
REAL_LOBBY_PATH = ROOT / "tests" / "fixtures" / "lobby_real" / "lobby.png"


class LobbySegmentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REAL_LOBBY_PATH.is_file():
            raise FileNotFoundError(f"Fixture do lobby real ausente: {REAL_LOBBY_PATH}")
        cls.image = cv2.imread(str(REAL_LOBBY_PATH))
        if cls.image is None:
            raise ValueError(f"Não foi possível abrir: {REAL_LOBBY_PATH}")

    def test_real_lobby_detects_all_five_cards(self):
        cards = segment_tournament_cards(self.image)
        self.assertEqual(len(cards), 5, f"Esperado 5 cartões, encontrados {len(cards)}")
        self.assertTrue(all(c["complete"] for c in cards), "Todos os 5 cartões devem ser completos")

        # Verifica dimensões e proporções
        for card in cards:
            x, y, w, h = card["local_box"]
            self.assertEqual(w, 748)
            self.assertGreaterEqual(h, 166)
            self.assertLessEqual(h, 172)
            self.assertIsNone(card["clip_reason"])
            self.assertEqual(card["visibility_ratio"], 1.0)
            self.assertEqual(len(card["sub_regions"]), 4)
            for rname in ("name", "buyin_prize", "start_time", "status"):
                self.assertIn(rname, card["sub_regions"])
                rx, ry, rw, rh = card["sub_regions"][rname]["local_box"]
                self.assertGreater(rw, 0)
                self.assertGreater(rh, 0)

        # O terceiro cartão (índice 2) é o CORUJAO
        corujao = cards[2]
        cx, cy = corujao["click_point_local"]
        # Centro de referência histórico medido em (405, 992)
        self.assertAlmostEqual(cx, 404.0, delta=2.0)
        self.assertAlmostEqual(cy, 992.0, delta=2.0)

    def test_clipped_top_card_identified(self):
        # Simula rolagem com corte no topo: corta a imagem no meio do primeiro cartão (y=600)
        scrolled_top = self.image[600:, :].copy()
        cards = segment_tournament_cards(scrolled_top)
        self.assertGreaterEqual(len(cards), 4)

        # O primeiro segmento visível é o restante do Diamante (cortado no topo)
        first_card = cards[0]
        self.assertFalse(first_card["complete"])
        self.assertEqual(first_card["clip_reason"], "clipped_top")
        self.assertLess(first_card["visibility_ratio"], 1.0)

        # Os cartões seguintes devem ser completos
        for card in cards[1:]:
            self.assertTrue(card["complete"])

    def test_clipped_bottom_card_identified(self):
        # Simula rolagem com corte no rodapé: corta a imagem no meio do último cartão (y=1350)
        scrolled_bottom = self.image[:1350, :].copy()
        cards = segment_tournament_cards(scrolled_bottom)
        self.assertGreaterEqual(len(cards), 5)

        # O último cartão é o Omaha-2 cortado no rodapé
        last_card = cards[-1]
        self.assertFalse(last_card["complete"])
        self.assertEqual(last_card["clip_reason"], "clipped_bottom")
        self.assertLess(last_card["visibility_ratio"], 1.0)

        # Os primeiros 4 cartões permanecem completos
        for card in cards[:-1]:
            self.assertTrue(card["complete"])

    def test_scaled_resolution_invariance(self):
        # Redimensiona a imagem para simular escala de 1.25x (como monitor com DPI scaling)
        scaled = cv2.resize(self.image, None, fx=1.25, fy=1.25, interpolation=cv2.INTER_CUBIC)
        cards = segment_tournament_cards(scaled)
        self.assertEqual(len(cards), 5)
        self.assertTrue(all(c["complete"] for c in cards))

        # Largura esperada em 1.25x: ~935px
        for card in cards:
            w, h = card["local_box"][2], card["local_box"][3]
            self.assertAlmostEqual(w, 748 * 1.25, delta=10)
            self.assertAlmostEqual(h, 168 * 1.25, delta=10)

    def test_origin_translation_for_desktop_coordinates(self):
        origin = (1920, 100)
        cards = segment_tournament_cards(self.image, origin=origin)
        self.assertEqual(len(cards), 5)

        for card in cards:
            lx, ly, lw, lh = card["local_box"]
            ax, ay, aw, ah = card["absolute_box"]
            self.assertEqual(ax, lx + origin[0])
            self.assertEqual(ay, ly + origin[1])
            self.assertEqual(aw, lw)
            self.assertEqual(ah, lh)

            cx_l, cy_l = card["click_point_local"]
            cx_a, cy_a = card["click_point_absolute"]
            self.assertAlmostEqual(cx_a, cx_l + origin[0], delta=0.1)
            self.assertAlmostEqual(cy_a, cy_l + origin[1], delta=0.1)

    def test_locate_lobby_window_direct_and_native(self):
        # 1. Imagem direta de lobby (proporção retrato)
        result_direct = locate_lobby_window(self.image)
        self.assertEqual(result_direct["status"], "found")
        self.assertEqual(result_direct["method"], "direct_window_image")
        self.assertEqual(result_direct["origin"], [0, 0])

        # 2. Janela simulada no desktop
        desktop = np.full((2160, 3840, 3), 40, dtype=np.uint8)
        desktop[150:150 + self.image.shape[0], 500:500 + self.image.shape[1]] = self.image
        windows = [{"title": "PPPoker - Club Lobby", "box": [500, 150, self.image.shape[1], self.image.shape[0]]}]
        result_win = locate_lobby_window(desktop, windows=windows)
        self.assertEqual(result_win["status"], "found")
        self.assertEqual(result_win["method"], "native_window_title")
        self.assertEqual(result_win["origin"], [500, 150])

    def test_save_artifacts_creates_all_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = process_lobby_image(REAL_LOBBY_PATH, tmpdir, origin=(500, 150))
            out_path = Path(tmpdir)

            self.assertEqual(report["total_cards_found"], 5)
            self.assertEqual(report["complete_cards"], 5)
            self.assertEqual(report["clipped_cards"], 0)

            # Arquivos gerados
            self.assertTrue((out_path / "annotated.png").is_file())
            self.assertTrue((out_path / "segments.json").is_file())
            for i in range(5):
                self.assertTrue((out_path / f"card_{i:02d}.png").is_file())

            # Valida JSON salvo
            saved = json.loads((out_path / "segments.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["module"], "phase1_module2")
            self.assertEqual(len(saved["cards"]), 5)

    def test_invalid_input_rejected(self):
        for bad in (None, np.zeros((0, 0, 3), dtype=np.uint8), np.zeros((100, 100), dtype=np.uint8)):
            with self.assertRaises(ValueError):
                segment_tournament_cards(bad)


if __name__ == "__main__":
    unittest.main()
