"""Testes unitários para o Módulo 4: Automação de Cliques, Tradução de Coordenadas e Auditoria em CSV."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from visualpilot.pppoker.lobby_clicker import (
    AuditLogger,
    WindowIntegrityGuardian,
    HeartbeatMonitor,
    EscalationNotifier,
    mask_webhook_url,
    SystemHaltError,
    calculate_absolute_click,
    click_tournament_card,
    execute_human_click,
    human_bezier_ease,
    generate_bezier_trajectory,
    CoordinateBoundsError,
    WindowNotFoundError,
    WindowDrasticChangeError,
    WindowStateError,
    CSV_HEADERS,
)


class LobbyClickerTests(unittest.TestCase):
    def setUp(self):
        self.mock_window = {
            "title": "PPPoker - Club Lobby",
            "left": 500,
            "top": 150,
            "width": 787,
            "height": 1470,
            "is_active": True
        }
        self.eligible_tournament = {
            "card_index": 2,
            "name": "CORUJAO HYPER PKO10K",
            "buyin": "50",
            "start_time": "10/31 22:00",
            "eligible": True,
            "click_point_local": [404.0, 992.0]
        }
        self.ineligible_tournament = {
            "card_index": 1,
            "name": "FREEZEOUT 30K GTD",
            "buyin": "200",
            "start_time": "10/31 18:00",
            "eligible": False,
            "rejection_reasons": ["buyin_exceeds_limit_50.0"],
            "click_point_local": [404.0, 811.0]
        }

    def test_calculate_absolute_click_exact_size(self):
        abs_x, abs_y, meta = calculate_absolute_click(
            [404.0, 992.0],
            self.mock_window,
            captured_size=(787, 1470),
            apply_jitter=False
        )
        self.assertEqual(abs_x, 500 + 404)
        self.assertEqual(abs_y, 150 + 992)
        self.assertEqual(meta["scale_factors"], [1.0, 1.0])
        self.assertEqual(meta["jitter"], [0.0, 0.0])

    def test_calculate_absolute_click_with_resized_window(self):
        resized_window = {
            "title": "PPPoker",
            "left": 100,
            "top": 80,
            "width": 1000,
            "height": 1800,
            "is_active": True
        }
        abs_x, abs_y, meta = calculate_absolute_click(
            [404.0, 992.0],
            resized_window,
            captured_size=(787, 1470),
            apply_jitter=False
        )
        expected_scale_x = 1000.0 / 787.0
        expected_scale_y = 1800.0 / 1470.0
        expected_x = int(round(100 + (404.0 * expected_scale_x)))
        expected_y = int(round(80 + (992.0 * expected_scale_y)))

        self.assertEqual(abs_x, expected_x)
        self.assertEqual(abs_y, expected_y)
        self.assertAlmostEqual(meta["scale_factors"][0], expected_scale_x, delta=0.001)
        self.assertAlmostEqual(meta["scale_factors"][1], expected_scale_y, delta=0.001)

    def test_out_of_bounds_click_rejected(self):
        with self.assertRaises(CoordinateBoundsError):
            calculate_absolute_click([5000.0, 5000.0], self.mock_window, apply_jitter=False)

    def test_calculate_absolute_click_fails_when_handle_lost(self):
        invalid_win = dict(self.mock_window, has_handle=False)
        with self.assertRaises(WindowStateError) as ctx:
            calculate_absolute_click([404.0, 992.0], invalid_win)
        self.assertIn("alça de janela ativa", str(ctx.exception))

    def test_calculate_absolute_click_fails_when_process_not_alive(self):
        invalid_win = dict(self.mock_window, is_alive=False)
        with self.assertRaises(WindowStateError) as ctx:
            calculate_absolute_click([404.0, 992.0], invalid_win)
        self.assertIn("não está ativo", str(ctx.exception))

    def test_calculate_absolute_click_fails_when_dimensions_collapsed(self):
        invalid_win = dict(self.mock_window, width=0, height=0)
        with self.assertRaises(WindowStateError) as ctx:
            calculate_absolute_click([404.0, 992.0], invalid_win)
        self.assertIn("colapsadas", str(ctx.exception))

    def test_ineligible_tournament_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            with self.assertRaises(ValueError):
                click_tournament_card(self.ineligible_tournament, mock_window=self.mock_window, logger=logger)

            # Confere se o cancelamento foi registrado no CSV
            log_file = logger.get_current_log_path()
            self.assertTrue(log_file.is_file())
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("CLICK_ABORTED", content)
            self.assertIn("FREEZEOUT 30K GTD", content)

    def test_dry_run_execution_simulates_and_logs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            report = click_tournament_card(
                self.eligible_tournament,
                dry_run=True,
                mock_window=self.mock_window,
                logger=logger
            )
            self.assertEqual(report["module"], "phase1_module4")
            self.assertEqual(report["execution"]["status"], "simulated")
            self.assertEqual(report["tournament_target"]["name"], "CORUJAO HYPER PKO10K")
            self.assertEqual(report["execution"]["target_coordinates"], [500 + 404, 150 + 992])

            # Confere CSV
            log_file = logger.get_current_log_path()
            self.assertTrue(log_file.is_file())
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("CLICK_SIMULATED", content)
            self.assertIn("CORUJAO HYPER PKO10K", content)
            self.assertIn("SUCCESS", content)

    def test_audit_logger_csv_format_and_flush(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            record = logger.log_event(
                event_type="CLICK_SUCCESS",
                status="SUCCESS",
                tournament_name="CORUJAO HYPER PKO10K",
                card_index=2,
                buyin_chips="50",
                target_abs_x=904,
                target_abs_y=1142,
                win_box=[500, 150, 787, 1470],
                duration_ms=280.5,
                details="Clique confirmado"
            )
            self.assertEqual(record["status"], "SUCCESS")

            log_file = logger.get_current_log_path()
            with open(log_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row["event_type"], "CLICK_SUCCESS")
                self.assertEqual(row["session_name"], "Sessão Padrão")
                self.assertEqual(row["tournament_name"], "CORUJAO HYPER PKO10K")
                self.assertEqual(row["buyin_chips"], "50")
                self.assertEqual(row["target_abs_x"], "904")
                self.assertEqual(row["target_abs_y"], "1142")

    def test_audit_logger_daily_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            dt_day1 = datetime(2026, 10, 31, 10, 0, 0, tzinfo=timezone.utc)
            dt_day2 = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)

            logger.log_event("CLICK_SUCCESS", "SUCCESS", tournament_name="T1", now=dt_day1)
            logger.log_event("CLICK_SUCCESS", "SUCCESS", tournament_name="T2", now=dt_day2)

            file1 = logger.get_current_log_path(dt_day1)
            file2 = logger.get_current_log_path(dt_day2)

            self.assertTrue(file1.is_file())
            self.assertTrue(file2.is_file())
            self.assertIn("2026-10-31", file1.name)
            self.assertIn("2026-11-01", file2.name)

    def test_window_guardian_detects_drastic_ratio_and_resolution_change(self):
        # 1. Deformação de proporção (ex: janela em landscape 1400x500)
        landscape_window = {"left": 0, "top": 0, "width": 1400, "height": 500}
        with self.assertRaises(WindowDrasticChangeError):
            WindowIntegrityGuardian.inspect_window(landscape_window)

        # 2. Mudança súbita de área entre início e clique (> 45%)
        initial_win = {"width": 800, "height": 1400}  # area = 1.120.000
        shrunk_win = {"left": 0, "top": 0, "width": 400, "height": 700}  # area = 280.000 (25%)
        with self.assertRaises(WindowDrasticChangeError):
            WindowIntegrityGuardian.inspect_window(shrunk_win, initial_win=initial_win)

    def test_click_aborts_and_logs_on_resolution_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            initial_win = {"width": 800, "height": 1400}
            drastic_changed_win = {"left": 0, "top": 0, "width": 400, "height": 600}

            with self.assertRaises(WindowDrasticChangeError):
                click_tournament_card(
                    self.eligible_tournament,
                    mock_window=drastic_changed_win,
                    guardian_check_window=initial_win,
                    logger=logger
                )

            log_file = logger.get_current_log_path()
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("RESOLUTION_CHANGED", content)
            self.assertIn("ABORTED", content)

    def test_heartbeat_monitor_triggers_system_halt_after_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            # Timeout curto de 0.05s para teste determinístico rápido
            watchdog = HeartbeatMonitor(logger=logger, timeout_seconds=0.05, check_interval=0.01)

            # Inicialmente ativo
            self.assertFalse(watchdog.is_halted)
            self.assertTrue(watchdog.check_pulse())

            # Simula passagem de tempo acima de 30 segundos (ou 0.06s no teste)
            import time
            time.sleep(0.06)

            # check_pulse deve detectar inatividade, entrar em halt e gravar no CSV
            healthy = watchdog.check_pulse()
            self.assertFalse(healthy)
            self.assertTrue(watchdog.is_halted)

            with self.assertRaises(SystemHaltError):
                watchdog.assert_healthy()

            log_file = logger.get_current_log_path()
            self.assertTrue(log_file.is_file())
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("SYSTEM_HALT", content)
            self.assertIn("HALT", content)
            self.assertIn("Inatividade detectada", content)

    def test_click_aborts_when_heartbeat_in_system_halt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            watchdog = HeartbeatMonitor(logger=logger, timeout_seconds=0.02)

            import time
            time.sleep(0.03)
            self.assertFalse(watchdog.check_pulse())
            self.assertTrue(watchdog.is_halted)

            with self.assertRaises(SystemHaltError):
                click_tournament_card(
                    self.eligible_tournament,
                    mock_window=self.mock_window,
                    logger=logger,
                    heartbeat=watchdog
                )

            log_file = logger.get_current_log_path()
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("SYSTEM_HALT", content)
            self.assertIn("CLICK_ABORTED", content)
            self.assertIn("ABORTED", content)

    def test_heartbeat_beat_renews_pulse_and_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            watchdog = HeartbeatMonitor(logger=logger, timeout_seconds=0.05)

            import time
            time.sleep(0.03)
            watchdog.beat("mantendo pulso")
            time.sleep(0.03)
            # Como deu beat no meio, o tempo decorrido desde o último beat foi apenas 0.03s (< 0.05s)
            self.assertTrue(watchdog.check_pulse())
            self.assertFalse(watchdog.is_halted)

            # Agora deixa expirar
            time.sleep(0.06)
            self.assertFalse(watchdog.check_pulse())
            self.assertTrue(watchdog.is_halted)

            # Restaura via resume
            watchdog.resume("Operador reiniciou o bot")
            self.assertFalse(watchdog.is_halted)
            self.assertTrue(watchdog.check_pulse())

            log_file = logger.get_current_log_path()
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("SYSTEM_RESUMED", content)

    def test_heartbeat_background_thread_watchdog(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            watchdog = HeartbeatMonitor(
                logger=logger,
                timeout_seconds=0.04,
                check_interval=0.01,
                auto_start=True
            )

            import time
            time.sleep(0.06)

            try:
                self.assertTrue(watchdog.is_halted)
                log_file = logger.get_current_log_path()
                content = log_file.read_text(encoding="utf-8")
                self.assertIn("SYSTEM_HALT", content)
            finally:
                watchdog.stop()

    def test_escalation_notifier_payload_formatting(self):
        notifier = EscalationNotifier()

        # Discord formatting
        discord_url = "https://discord.com/api/webhooks/123456/abcdef"
        payload_disc, prov_disc = notifier.build_payload(
            title="Alerta Crítico",
            details="Congelado há 5 minutos",
            elapsed_seconds=300.0,
            webhook_url=discord_url
        )
        self.assertEqual(prov_disc, "discord")
        self.assertIn("content", payload_disc)
        self.assertIn("embeds", payload_disc)
        self.assertEqual(payload_disc["embeds"][0]["color"], 15158332)

        # Telegram formatting
        tg_url = "https://api.telegram.org/bot12345/sendMessage"
        payload_tg, prov_tg = notifier.build_payload(
            title="Alerta Crítico",
            details="Congelado há 5 minutos",
            elapsed_seconds=300.0,
            webhook_url=tg_url
        )
        self.assertEqual(prov_tg, "telegram")
        self.assertIn("text", payload_tg)
        self.assertEqual(payload_tg["parse_mode"], "Markdown")

        # Generic webhook formatting
        gen_url = "https://hooks.zapier.com/hooks/catch/12345/abc"
        payload_gen, prov_gen = notifier.build_payload(
            title="Alerta Crítico",
            details="Congelado há 5 minutos",
            elapsed_seconds=300.0,
            webhook_url=gen_url
        )
        self.assertEqual(prov_gen, "generic")
        self.assertEqual(payload_gen["event"], "SYSTEM_HALT_ESCALATION")
        self.assertEqual(payload_gen["status"], "ESCALATED")

        # Masking verification
        masked = mask_webhook_url("https://discord.com/api/webhooks/123456789/abcdefghijk")
        self.assertNotIn("abcdefghijk", masked)
        self.assertIn("discord.com", masked)

    def test_heartbeat_escalation_triggers_after_timeout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            escalated_events = []

            watchdog = HeartbeatMonitor(
                logger=logger,
                timeout_seconds=0.03,
                escalation_timeout_seconds=0.06,
                webhook_url="mock://test-escalation",
                on_escalate=lambda res: escalated_events.append(res)
            )

            import time
            time.sleep(0.04)
            # Primeiro check: entrou em SYSTEM_HALT, mas ainda não em escalada (< 0.06s)
            self.assertFalse(watchdog.check_pulse())
            self.assertTrue(watchdog.is_halted)
            self.assertFalse(watchdog.is_escalated)
            self.assertEqual(len(escalated_events), 0)

            # Espera ultrapassar o teto de escalada (0.06s adicionais)
            time.sleep(0.07)
            self.assertFalse(watchdog.check_pulse())
            self.assertTrue(watchdog.is_halted)
            self.assertTrue(watchdog.is_escalated)
            self.assertEqual(len(escalated_events), 1)

            # Verifica CSV
            log_file = logger.get_current_log_path()
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("SYSTEM_HALT", content)
            self.assertIn("ESCALATION_ALERT_SENT", content)
            self.assertIn("ESCALATED", content)

            # Segundo check não deve re-disparar escalada duplicada
            self.assertFalse(watchdog.check_pulse())
            self.assertEqual(len(escalated_events), 1)

    def test_escalation_reset_on_resume(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            watchdog = HeartbeatMonitor(
                logger=logger,
                timeout_seconds=0.02,
                escalation_timeout_seconds=0.04,
                webhook_url="mock://test-escalation"
            )

            import time
            time.sleep(0.03)
            # Entra em SYSTEM_HALT
            self.assertFalse(watchdog.check_pulse())
            self.assertTrue(watchdog.is_halted)
            self.assertFalse(watchdog.is_escalated)

            # Aguarda expirar a escalada (> 0.04s adicionais em halt)
            time.sleep(0.05)
            self.assertFalse(watchdog.check_pulse())
            self.assertTrue(watchdog.is_escalated)

            # Restabelece
            watchdog.resume("Operador voltou ao posto")
            self.assertFalse(watchdog.is_halted)
            self.assertFalse(watchdog.is_escalated)
            self.assertEqual(watchdog.halt_duration, 0.0)

            content = logger.get_current_log_path().read_text(encoding="utf-8")
            self.assertIn("SYSTEM_RESUMED", content)
            self.assertIn("redefinido", content)

    def test_manual_escalation_trigger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)
            watchdog = HeartbeatMonitor(
                logger=logger,
                webhook_url="mock://test-manual"
            )
            res = watchdog.trigger_manual_escalation("Validação manual de rotina")
            self.assertTrue(res["success"])
            self.assertEqual(res["mode"], "simulated")

    def test_click_speed_and_reaction_delay_configuration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir)

            # Teste de velocidade rápida (fast)
            res_fast = click_tournament_card(
                self.eligible_tournament,
                mock_window=self.mock_window,
                dry_run=True,
                logger=logger,
                speed="fast",
                reaction_delay_range=(0.01, 0.02)
            )
            self.assertEqual(res_fast["camouflage"]["speed_profile"], "fast")
            self.assertEqual(res_fast["camouflage"]["move_duration_sec"], 0.16)
            self.assertGreaterEqual(res_fast["camouflage"]["reaction_delay_sec"], 0.01)

            # Teste de velocidade lenta (slow)
            res_slow = click_tournament_card(
                self.eligible_tournament,
                mock_window=self.mock_window,
                dry_run=True,
                logger=logger,
                speed="slow",
                reaction_delay_range=(0.02, 0.04)
            )
            self.assertEqual(res_slow["camouflage"]["speed_profile"], "slow")
            self.assertEqual(res_slow["camouflage"]["move_duration_sec"], 0.65)

            # Verifica gravação no log CSV
            content = logger.get_current_log_path().read_text(encoding="utf-8")
            self.assertIn("rápido", content)
            self.assertIn("lento", content)
            self.assertIn("delay_camuflagem", content)


    def test_auto_recovery_mode_logs_and_handles_missing_exe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from visualpilot.pppoker.lobby_clicker import attempt_window_recovery
            logger = AuditLogger(logs_dir=tmpdir, default_session_name="Sessão Teste Recuperação")

            with self.assertRaises(FileNotFoundError):
                attempt_window_recovery(
                    executable_path="/caminho/inexistente/pppoker.exe",
                    logger=logger,
                    session_name="Sessão Teste Recuperação"
                )

            content = logger.get_current_log_path().read_text(encoding="utf-8")
            self.assertIn("RECOVERY_ATTEMPTED", content)
            self.assertIn("RECOVERY_FAILED", content)
            self.assertIn("Sessão Teste Recuperação", content)

    def test_ab_testing_alternates_and_logs_to_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(logs_dir=tmpdir, default_session_name="Sessão AB Test")

            # Executa 4 cliques alternados
            for i in range(4):
                variant = "A" if i % 2 == 0 else "B"
                var_name = "Furtiva" if variant == "A" else "Agressiva"
                var_speed = "natural" if variant == "A" else "fast"
                var_delay = (0.01, 0.02) if variant == "A" else (0.005, 0.01)

                rep = click_tournament_card(
                    self.eligible_tournament,
                    mock_window=self.mock_window,
                    dry_run=True,
                    logger=logger,
                    speed=var_speed,
                    reaction_delay_range=var_delay,
                    session_name="Sessão AB Test",
                    ab_variant=variant,
                    ab_strategy_name=var_name
                )
                self.assertEqual(rep["camouflage"]["ab_variant"], variant)
                self.assertEqual(rep["camouflage"]["ab_strategy_name"], var_name)

            csv_file = logger.get_current_log_path()
            content = csv_file.read_text(encoding="utf-8")

            # Verifica presença das tags A/B no CSV
            self.assertIn("VARIANTE_A", content)
            self.assertIn("VARIANTE_B", content)
            self.assertIn("Furtiva", content)
            self.assertIn("Agressiva", content)

            with open(csv_file, mode="r", encoding="utf-8-sig") as f:
                reader = list(csv.DictReader(f))
                self.assertEqual(len(reader), 4)
                self.assertTrue(reader[0]["details"].startswith('[TESTE_AB: VARIANTE_A - "Furtiva"]'))
                self.assertTrue(reader[1]["details"].startswith('[TESTE_AB: VARIANTE_B - "Agressiva"]'))
                self.assertTrue(reader[2]["details"].startswith('[TESTE_AB: VARIANTE_A - "Furtiva"]'))
                self.assertTrue(reader[3]["details"].startswith('[TESTE_AB: VARIANTE_B - "Agressiva"]'))

    def test_ab_testing_cli_batch(self):
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            tourneys_path = Path(tmpdir) / "tournaments.json"
            tourneys_path.write_text(json.dumps({"tournaments": [self.eligible_tournament]}), encoding="utf-8")
            logs_dir = Path(tmpdir) / "logs"

            from visualpilot.pppoker.lobby_clicker import main
            code = main([
                "--tournaments", str(tourneys_path),
                "--ab-test",
                "--ab-count", "4",
                "--ab-a-name", "Ultra Furtiva",
                "--ab-a-speed", "slow",
                "--ab-a-delay-min", "0.01",
                "--ab-a-delay-max", "0.02",
                "--ab-b-name", "Hyper Speed",
                "--ab-b-speed", "fast",
                "--ab-b-delay-min", "0.005",
                "--ab-b-delay-max", "0.01",
                "--dry-run",
                "--logs-dir", str(logs_dir),
                "--session-name", "Sessão CLI AB"
            ])
            self.assertEqual(code, 0)
            csv_files = list(logs_dir.glob("*.csv"))
            self.assertTrue(len(csv_files) >= 1)
            content = csv_files[0].read_text(encoding="utf-8")
            self.assertIn("Ultra Furtiva", content)
            self.assertIn("Hyper Speed", content)

    def test_human_bezier_ease_physical_acceleration(self):
        # Limiares de contorno estritos
        self.assertEqual(human_bezier_ease(0.0), 0.0)
        self.assertEqual(human_bezier_ease(1.0), 1.0)
        self.assertEqual(human_bezier_ease(-0.5), 0.0)
        self.assertEqual(human_bezier_ease(1.5), 1.0)

        # Monotonicidade estrita: valores sucessivos não retrocedem
        values = [human_bezier_ease(i / 100.0) for i in range(101)]
        for i in range(len(values) - 1):
            self.assertLessEqual(values[i], values[i + 1])

        # Comportamento fisiológico assimétrico:
        # A 35% do percurso temporal (fase balística), o cursor já avançou aproximadamente 40% da distância
        ease_35 = human_bezier_ease(0.35)
        self.assertAlmostEqual(ease_35, 0.40, delta=0.05)

        # Aceleração inicial rápida vs desaceleração terminal suave
        delta_initial = human_bezier_ease(0.2) - human_bezier_ease(0.0)
        delta_final = human_bezier_ease(1.0) - human_bezier_ease(0.8)
        # O movimento desacelera no final para acomodação fina
        self.assertGreater(delta_initial, 0.0)
        self.assertGreater(delta_final, 0.0)

    def test_generate_bezier_trajectory_with_jitter(self):
        start = (100.0, 200.0)
        end = (500.0, 800.0)
        res = generate_bezier_trajectory(start, end, num_steps=10, jitter_magnitude=2.0)

        self.assertEqual(res["acceleration_curve"], "human_bezier_ease")
        self.assertEqual(len(res["control_points"]), 4)
        self.assertEqual(res["control_points"][0], (100.0, 200.0))
        self.assertEqual(res["control_points"][3], (500.0, 800.0))

        # Waypoint final deve convergir exatamente para o destino final (sem jitter prejudicial)
        last_wp = res["waypoints"][-1]
        self.assertEqual(last_wp, (500.0, 800.0))

        # Waypoints intermediários existem e contêm micro-desvios orgânicos
        self.assertEqual(len(res["waypoints"]), 10)
        # Distância calculada correta: sqrt(400^2 + 600^2) = ~721.1 px
        self.assertAlmostEqual(res["distance"], 721.1, delta=1.0)

    def test_execute_human_click_bezier_dry_run_metadata(self):
        result = execute_human_click(450, 750, move_duration=0.35, press_delay=0.08, dry_run=True, jitter_px=1.5)
        self.assertEqual(result["status"], "simulated")
        self.assertEqual(result["target_coordinates"], [450, 750])
        self.assertEqual(result["acceleration_curve"], "human_bezier_ease")
        self.assertIn("trajectory", result)
        self.assertIn("control_points", result["trajectory"])
        self.assertIn("waypoints", result["trajectory"])
        self.assertEqual(result["trajectory"]["waypoints"][-1], (450.0, 750.0))


if __name__ == "__main__":
    unittest.main()


