import os
from pathlib import Path
import tempfile
import unittest

from visualpilot.pppoker.window_visibility_guardian import (
    WindowVisibilityGuardian,
    WindowVisibilityReport,
    rect_intersection_area,
    validate_captured_frame_integrity
)


class TestWindowVisibilityGuardian(unittest.TestCase):
    def test_rect_intersection_area(self):
        # Sem sobreposição
        r1 = (0, 0, 100, 100)
        r2 = (200, 200, 50, 50)
        self.assertEqual(rect_intersection_area(r1, r2), 0)

        # Sobreposição total (idênticos)
        r3 = (0, 0, 100, 100)
        self.assertEqual(rect_intersection_area(r1, r3), 10000)

        # Sobreposição parcial (50x50 = 2500)
        r4 = (50, 50, 100, 100)
        self.assertEqual(rect_intersection_area(r1, r4), 2500)

    def test_headless_simulation_clean_window(self):
        guardian = WindowVisibilityGuardian(target_keyword="pppoker")
        report = guardian.inspect_and_prepare_window(auto_restore=True, auto_focus=True)

        self.assertTrue(report.is_found)
        self.assertFalse(report.is_minimized)
        self.assertFalse(report.is_occluded)
        self.assertEqual(report.occlusion_status, "CLEAR")
        self.assertTrue(report.frame_valid_for_ocr)

        d = report.to_dict()
        self.assertEqual(d["window_rect"]["width"], 787)
        self.assertEqual(d["window_rect"]["height"], 1470)

    def test_frame_integrity_validator_black_image(self):
        # Cria imagem preta temporária usando bytes simples se PIL não estiver instalado
        try:
            from PIL import Image
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                temp_path = Path(f.name)
            
            # Imagem preta (desvio padrão 0.0)
            black_img = Image.new("RGB", (200, 200), (0, 0, 0))
            black_img.save(temp_path)

            valid, std_dev, msg = validate_captured_frame_integrity(temp_path, min_variance_std=8.0)
            self.assertFalse(valid)
            self.assertLess(std_dev, 2.0)
            self.assertIn("Frame inválido", msg)

            # Imagem com contraste / xadrez (desvio padrão alto)
            contrast_img = Image.new("RGB", (200, 200), (255, 255, 255))
            for x in range(100):
                for y in range(100):
                    contrast_img.putpixel((x, y), (0, 128, 0))
            contrast_img.save(temp_path)

            valid_ok, std_ok, msg_ok = validate_captured_frame_integrity(temp_path, min_variance_std=8.0)
            self.assertTrue(valid_ok)
            self.assertGreater(std_ok, 10.0)

            if temp_path.exists():
                temp_path.unlink()
        except ImportError:
            # Em ambientes sem PIL instalado, a função retorna True por tolerância
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                temp_path = Path(f.name)
                f.write(b"PNGDATA")
            valid, std_dev, msg = validate_captured_frame_integrity(temp_path)
            self.assertTrue(valid)
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
