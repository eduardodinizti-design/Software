"""Testes unitários para o Orquestrador de Ciclo Contínuo e Anti-Duplicação."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import time
import unittest

from visualpilot.pppoker.lobby_clicker import AuditLogger, HeartbeatMonitor
from visualpilot.pppoker.tournament_registration import (
    TournamentRegistrationManager,
    InsufficientFundsError,
)
from visualpilot.pppoker.lobby_orchestrator import (
    AntiDuplicationRegistry,
    AntiDupRecord,
    LoopConfig,
    LobbyOrchestrator,
    generate_tournament_key,
    normalize_text,
    clean_name_key,
)


class AntiDuplicationRegistryTests(unittest.TestCase):
    def setUp(self):
        self.t1 = {
            "name": "CORUJAO HYPER PKO10K",
            "buyin": "50",
            "start_time": "23:00",
            "game_format": "MTT"
        }
        self.t2 = {
            "name": "TARDEZINHA PKO 5K GTD",
            "buyin": "10",
            "start_time": "16:30",
            "game_format": "MTT"
        }

    def test_key_generation_deterministic(self):
        k1 = generate_tournament_key(self.t1)
        k2 = generate_tournament_key(self.t1)
        self.assertEqual(k1, k2)
        self.assertIn("CORUJAOHYPERPKO10K", k1)
        self.assertIn("50", k1)
        self.assertIn("2300", k1)

    def test_registration_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_anti_dup.json"
            reg = AntiDuplicationRegistry(persistence_file=file_path, ttl_hours=24.0)

            self.assertFalse(reg.is_registered(self.t1))
            self.assertFalse(reg.is_registered(self.t2))

            # Registra t1
            rec1 = reg.mark_registered(self.t1, session_name="Sessao Teste 01")
            self.assertTrue(reg.is_registered(self.t1))
            self.assertFalse(reg.is_registered(self.t2))
            self.assertEqual(rec1.registration_count, 1)

            # Verifica arquivo salvo
            self.assertTrue(file_path.exists())
            data = json.loads(file_path.read_text(encoding="utf-8"))
            self.assertEqual(data["total_registered"], 1)

            # Recria registry a partir do mesmo arquivo
            reg_loaded = AntiDuplicationRegistry(persistence_file=file_path, ttl_hours=24.0)
            self.assertTrue(reg_loaded.is_registered(self.t1))
            self.assertFalse(reg_loaded.is_registered(self.t2))

    def test_ttl_expiration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_ttl.json"
            # TTL muito curto (0.0001 hora = 0.36 segundos)
            reg = AntiDuplicationRegistry(persistence_file=file_path, ttl_hours=0.0001)

            reg.mark_registered(self.t1)
            self.assertTrue(reg.is_registered(self.t1))

            time.sleep(0.45)
            # Expirou o TTL, deve permitir nova inscrição
            self.assertFalse(reg.is_registered(self.t1))


class LobbyOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.sample_tournaments = [
            {
                "index": 0,
                "name": "TORNEIO BARATO 10K",
                "buyin": "20",
                "start_time": "15:00",
                "game_format": "MTT",
                "status": "ABERTO",
                "eligible": True,
                "click_point_local": [393.5, 342.0]
            },
            {
                "index": 1,
                "name": "TORNEIO MEDIO 50K",
                "buyin": "50",
                "start_time": "18:00",
                "game_format": "MTT",
                "status": "ABERTO",
                "eligible": True,
                "click_point_local": [393.5, 552.0]
            },
            {
                "index": 2,
                "name": "HIGH ROLLER CARO",
                "buyin": "200",  # Acima de 50!
                "start_time": "21:00",
                "game_format": "MTT",
                "status": "ABERTO",
                "eligible": False,
                "click_point_local": [393.5, 762.0]
            }
        ]

    def test_orchestrator_cycle_and_anti_duplication_skipping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            dup_file = Path(tmpdir) / "anti_dup.json"

            logger = AuditLogger(logs_dir=logs_dir)
            anti_dup = AntiDuplicationRegistry(persistence_file=dup_file, ttl_hours=24.0)

            cfg = LoopConfig(
                interval_seconds=0.1,
                jitter_seconds=0.0,
                max_iterations=1,
                max_buyin=50.0,
                dry_run=True,
                anti_dup_file=str(dup_file)
            )

            orch = LobbyOrchestrator(
                config=cfg,
                logger_instance=logger,
                anti_dup=anti_dup
            )

            # CICLO 1: Deve registrar os dois torneios elegíveis (20 e 50 fichas)
            cycle1 = orch.run_cycle(tournaments_input=self.sample_tournaments)
            self.assertEqual(cycle1["status"], "COMPLETED")
            self.assertEqual(cycle1["tournaments_eligible"], 2)
            self.assertEqual(cycle1["registered_count"], 2)
            self.assertEqual(cycle1["skipped_duplicate"], 0)

            # CICLO 2: Com os mesmos cartões, deve detectar ambos no Anti-Dup e ignorá-los!
            cycle2 = orch.run_cycle(tournaments_input=self.sample_tournaments)
            self.assertEqual(cycle2["status"], "COMPLETED")
            self.assertEqual(cycle2["tournaments_eligible"], 2)
            self.assertEqual(cycle2["registered_count"], 0)
            self.assertEqual(cycle2["skipped_duplicate"], 2)

            # Verifica se o log CSV registrou os eventos corretos
            log_file = logger.get_current_log_path()
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("REGISTRATION_SUCCESS", content)
            self.assertIn("TOURNAMENT_SKIPPED_ALREADY_REGISTERED", content)

    def test_orchestrator_loop_with_max_iterations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            dup_file = Path(tmpdir) / "anti_dup.json"

            logger = AuditLogger(logs_dir=logs_dir)
            anti_dup = AntiDuplicationRegistry(persistence_file=dup_file)

            cfg = LoopConfig(
                interval_seconds=0.05,
                jitter_seconds=0.01,
                max_iterations=3,
                max_buyin=50.0,
                dry_run=True,
                anti_dup_file=str(dup_file)
            )

            orch = LobbyOrchestrator(
                config=cfg,
                logger_instance=logger,
                anti_dup=anti_dup
            )

            cycles_received = []
            summary = orch.run_loop(on_cycle_callback=lambda res: cycles_received.append(res["cycle"]))

            self.assertEqual(summary["total_cycles"], 3)
            self.assertEqual(cycles_received, [1, 2, 3])
            self.assertFalse(summary["is_running"])


if __name__ == "__main__":
    unittest.main()
