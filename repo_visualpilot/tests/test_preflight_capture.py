"""Testes unitários para o utilitário de captura pré-voo e calibração de frame (preflight_capture)."""
import json
from pathlib import Path
import tempfile
import unittest

from visualpilot.pppoker.preflight_capture import (
    calculate_calibration,
    capture_window_thumbnail,
    run_preflight_snapshot,
    main as cli_main,
    TARGET_WIDTH,
    TARGET_HEIGHT,
)


class PreflightCaptureTests(unittest.TestCase):
    def test_calculate_calibration_perfect_target(self):
        calib = calculate_calibration(TARGET_WIDTH, TARGET_HEIGHT)
        self.assertTrue(calib["is_calibrated"])
        self.assertTrue(calib["is_perfect"])
        self.assertEqual(calib["calibration_score"], 100)
        self.assertEqual(calib["scale_x"], 1.0)
        self.assertEqual(calib["scale_y"], 1.0)
        self.assertEqual(calib["status"], "CALIBRATED_PERFECT")
        self.assertEqual(calib["actual_resolution"], "787x1470")

    def test_calculate_calibration_acceptable_micro_deviation(self):
        # 1 pixel de desvio por borda do Windows Aero/DWM
        calib = calculate_calibration(788, 1471)
        self.assertTrue(calib["is_calibrated"])
        self.assertGreaterEqual(calib["calibration_score"], 95)
        self.assertIn("CALIBRATED", calib["status"])

    def test_calculate_calibration_deformed_aspect_ratio(self):
        # Janela esticada ou modo paisagem
        calib = calculate_calibration(1400, 450)
        self.assertFalse(calib["is_calibrated"])
        self.assertFalse(calib["is_perfect"])
        self.assertEqual(calib["status"], "DEFORMED")
        self.assertLess(calib["calibration_score"], 50)
        self.assertGreater(calib["ratio_error_pct"], 10.0)

    def test_calculate_calibration_zero_or_negative(self):
        calib_zero = calculate_calibration(0, 0)
        self.assertFalse(calib_zero["is_calibrated"])
        self.assertEqual(calib_zero["calibration_score"], 0)
        self.assertEqual(calib_zero["status"], "INVALID_DIMENSIONS")

    def test_capture_window_thumbnail_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / "source.png"
            src_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest")
            dest_file = Path(tmpdir) / "dest_thumb.png"

            ok = capture_window_thumbnail(
                bbox=None,
                output_png=dest_file,
                fallback_source=src_file
            )
            self.assertTrue(ok)
            self.assertTrue(dest_file.is_file())
            self.assertEqual(dest_file.read_bytes(), src_file.read_bytes())

    def test_run_preflight_snapshot_generates_json_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_png = Path(tmpdir) / "thumb.png"
            out_json = Path(tmpdir) / "snapshot.json"

            # Cria dummy png para o fallback
            dummy = Path(tmpdir) / "dummy.png"
            dummy.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdummy")

            res = run_preflight_snapshot(
                window_name="pppoker",
                output_png=out_png,
                output_json=out_json,
                force_mock=True
            )

            self.assertTrue(out_json.is_file())
            saved_data = json.loads(out_json.read_text(encoding="utf-8"))

            self.assertIn("timestamp_iso", saved_data)
            self.assertIn("bbox", saved_data)
            self.assertIn("calibration", saved_data)
            self.assertIn("anchors", saved_data)
            self.assertEqual(saved_data["bbox"]["width"], TARGET_WIDTH)
            self.assertEqual(saved_data["bbox"]["height"], TARGET_HEIGHT)
            self.assertEqual(saved_data["calibration"]["calibration_score"], 100)
            self.assertIn("back_button", saved_data["anchors"])
            self.assertIn("register_button", saved_data["anchors"])

    def test_cli_main_mock_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_png = str(Path(tmpdir) / "cli_thumb.png")
            out_json = str(Path(tmpdir) / "cli_snapshot.json")

            ret = cli_main(["--mock", "--output-png", out_png, "--output-json", out_json])
            self.assertEqual(ret, 0)
            self.assertTrue(Path(out_json).is_file())


if __name__ == "__main__":
    unittest.main()
