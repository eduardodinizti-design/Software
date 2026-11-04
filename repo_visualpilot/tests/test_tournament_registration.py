"""Testes unitários para o Módulo 5: Confirmação de Inscrição & Navegação Pós-Clique."""
import json
from pathlib import Path
import tempfile
import unittest

from visualpilot.pppoker.lobby_clicker import AuditLogger, HeartbeatMonitor
from visualpilot.pppoker.tournament_registration import (
    TournamentRegistrationManager,
    ScreenTransitionTimeoutError,
    DEFAULT_REGISTRATION_ROIS,
)


class TournamentRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tournament_mock = {
            "card_index": 2,
            "name": "CORUJAO HYPER PKO10K",
            "buyin": "50",
            "eligible": True,
            "click_point_local": [404.0, 992.0]
        }

    def test_full_registration_cycle_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            manager = TournamentRegistrationManager(logger=logger, dry_run=True)

            report = manager.run_full_registration(self.tournament_mock)

            self.assertEqual(report["status"], "REGISTERED")
            self.assertEqual(len(report["steps"]), 5)

            step_names = [s["step_name"] for s in report["steps"]]
            self.assertEqual(step_names, [
                "WAIT_DETAIL_SCREEN",
                "CLICK_REGISTER_BUTTON",
                "CONFIRM_BUYIN_MODAL",
                "VERIFY_REGISTRATION_STATUS",
                "RETURN_TO_LOBBY"
            ])

            # Verifica CSV de auditoria
            log_file = logger.get_current_log_path()
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("SCREEN_TRANSITION_OK", content)
            self.assertIn("REGISTER_BUTTON_CLICKED", content)
            self.assertIn("BUYIN_CONFIRMED", content)
            self.assertIn("STATUS_VERIFIED_REGISTERED", content)
            self.assertIn("RETURNED_TO_LOBBY", content)
            self.assertIn("REGISTRATION_SUCCESS", content)

    def test_skip_return_to_lobby_option(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            manager = TournamentRegistrationManager(logger=logger, dry_run=True)

            report = manager.run_full_registration(self.tournament_mock, skip_return_to_lobby=True)
            self.assertEqual(len(report["steps"]), 4)
            step_names = [s["step_name"] for s in report["steps"]]
            self.assertNotIn("RETURN_TO_LOBBY", step_names)

    def test_heartbeat_system_halt_aborts_registration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            watchdog = HeartbeatMonitor(logger=logger, timeout_seconds=0.02)

            import time
            time.sleep(0.04)
            watchdog.check_pulse()
            self.assertTrue(watchdog.is_halted)

            manager = TournamentRegistrationManager(logger=logger, heartbeat=watchdog, dry_run=True)

            from visualpilot.pppoker.lobby_clicker import SystemHaltError
            with self.assertRaises(SystemHaltError):
                manager.run_full_registration(self.tournament_mock)


if __name__ == "__main__":
    unittest.main()
