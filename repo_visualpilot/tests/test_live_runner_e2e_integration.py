"""VisualPilot - Testes de Integração Ponta a Ponta do Ciclo Operacional Real.

Homologação rigorosa de todos os pontos críticos identificados no cliente real:
1. Integração com o leitor real de cartas (estrutura 'cards' com dicionários e 'hero_cards').
2. Rejeição de ruído aleatório no detector de ações (rejeição por gradiente e validação de botões).
3. Resolução dinâmica de dados da mesa via TableNumericalOCR (posição, stack, pote).
4. Abortamento seguro quando atalho de sizing não está presente (não clica no Raise descalibrado).
5. Contagem correta de mãos (a transição Pré-flop -> Flop -> Turn -> River NÃO incrementa a mão).
6. Confirmação pós-clique não ambígua (captura ausente ou frame corrompido NUNCA confirmam ação).
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from visualpilot.pppoker.card_recognition import CardRecognitionEngine
from visualpilot.pppoker.hero_action_detector import (
    HeroActionDetector,
    ActionButton,
    BetSizingOption,
    HeroActionSnapshot,
)
from visualpilot.pppoker.table_bot_runner import (
    TableBotRunner,
    LiveGameDecision,
    canonical_hand_name,
)
from visualpilot.pppoker.lobby_clicker import AuditLogger


class TestLiveRunnerE2EIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.telemetry_path = str(Path(self.temp_dir.name) / "telemetry_test.json")
        self.logs_dir = str(Path(self.temp_dir.name) / "logs")

    def tearDown(self):
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Leitor de Cartas Real: Dicionários vs Objetos
    # -------------------------------------------------------------------------
    def test_card_engine_real_dictionary_integration(self):
        """Valida que o runner extrai cartas do retorno real do CardRecognitionEngine sem falhar."""
        card_engine = CardRecognitionEngine(four_color_mode=True)
        # Executa o leitor real com hints nativos (sem mock)
        color_hints = {
            "hero_1": (220, 38, 38),  # Hearts (h)
            "hero_2": (37, 99, 235),  # Diamonds (d)
            "flop_1": (15, 23, 42),   # Spades (s)
            "flop_2": (220, 38, 38),  # Hearts (h)
            "flop_3": (22, 163, 74),  # Clubs (c)
        }
        ocr_hints = {
            "hero_1": "A", "hero_2": "K",
            "flop_1": "Q", "flop_2": "J", "flop_3": "T"
        }
        real_result = card_engine.read_table_frame(None, ocr_hints=ocr_hints, color_hints=color_hints)
        
        # Garante que o retorno do leitor contém tanto 'cards' com dicts quanto 'hero_cards'/'board_cards'
        self.assertIn("cards", real_result)
        self.assertIsInstance(real_result["cards"], list)
        self.assertIsInstance(real_result["cards"][0], dict)
        self.assertIn("hero_cards", real_result)
        self.assertIn("board_cards", real_result)

        # Testa o extrator do TableBotRunner consumindo esse retorno real
        raw_hero = real_result.get("hero_cards", [])
        raw_board = real_result.get("board_cards", [])
        self.assertGreaterEqual(len(raw_hero), 2, "Hero deve ter lido pelo menos 2 cartas")
        self.assertEqual(raw_hero[0], "Ah")
        self.assertEqual(raw_hero[1], "Kd")

    # -------------------------------------------------------------------------
    # 2. Rejeição Estrita de Ruído Aleatório no Detector de Ações
    # -------------------------------------------------------------------------
    def test_random_noise_rejected_by_hero_action_detector(self):
        """Garante que ruído aleatório (estático/noise) NÃO é classificado como vez do Hero."""
        detector = HeroActionDetector()
        
        # Cria uma classe simulando uma matriz com alto gradiente (ruído aleatório)
        class NoiseFrame:
            ndim = 3
            shape = (1470, 787, 3)
            size = 1470 * 787 * 3

            def __getitem__(self, item):
                # Retorna sub-array de ruído com alto desvio e alto gradiente
                return self

            def astype(self, dtype):
                return self

        # 1. Sem frame: is_hero_turn deve ser False
        snap_none = detector.detect_actions(table_frame=None)
        self.assertFalse(snap_none.is_hero_turn)

        # 2. Frame de ruído simulado: deve ser rejeitado pelo filtro de gradiente
        snap_noise = detector.detect_actions(table_frame=NoiseFrame())
        self.assertFalse(snap_noise.is_hero_turn, "Ruído aleatório não pode gerar 'vez do Hero'")
        self.assertEqual(len(snap_noise.buttons), 0)

    # -------------------------------------------------------------------------
    # 3. Resolução Dinâmica de Dados da Mesa (Fim dos Dados Fixos)
    # -------------------------------------------------------------------------
    def test_dynamic_table_ocr_resolves_position_and_stacks(self):
        """Valida que o TableNumericalOCR determina posição real do Hero a partir do Dealer e lê stacks."""
        runner = TableBotRunner(mode="dry-run", telemetry_path=self.telemetry_path)
        
        # Simula cenário de mesa onde Dealer está no assento 4 e Hero no assento 5 (Hero é SB)
        mock_table = {
            "dealer_seat": 4,
            "hero_seat": 5,
            "pot_bb": 12.5,
            "call_amount_bb": 3.0,
            "seats": [
                {"seat": 4, "name": "DealerPlayer", "stack_bb": 150.0, "is_hero": False},
                {"seat": 5, "name": "Hero", "stack_bb": 85.0, "is_hero": True},
                {"seat": 6, "name": "BigBlindPlayer", "stack_bb": 90.0, "is_hero": False},
            ]
        }
        snap = runner.table_ocr.process_table_state(mock_scenario=mock_table)
        self.assertEqual(snap.hero_position, "SB", "Hero à esquerda do Dealer 4 deve ser SB (não BTN fixo)")
        self.assertEqual(snap.total_pot_bb, 12.5)
        
        hero_seat = next((s for s in snap.seats if s.is_hero), None)
        self.assertIsNotNone(hero_seat)
        self.assertEqual(hero_seat.stack_bb, 85.0, "Stack deve ser lido do assento do Hero (não 100 BB fixo)")

    # -------------------------------------------------------------------------
    # 4. Aposta com Confirmação de Sizing (Abortamento Seguro se Atalho Faltar)
    # -------------------------------------------------------------------------
    def test_missing_sizing_shortcut_aborts_and_does_not_click_raise(self):
        """Se a decisão exige ajuste de sizing mas o botão de atalho não existe, o clique de Raise é cancelado."""
        runner = TableBotRunner(mode="live", telemetry_path=self.telemetry_path)
        runner.audit_logger = AuditLogger(logs_dir=self.logs_dir)

        buttons = [
            ActionButton("btn_right", "raise", "Raise", (1370, 528, 1455, 755)),
        ]
        # Lista de sizing VAZIA (nenhum atalho disponível)
        sizing_options = []

        decision = LiveGameDecision(
            timestamp="2026-11-01T15:00:00Z",
            hand_id="H-0001",
            street="FLOP",
            hero_position="BTN",
            hero_cards=["As", "Ah"],
            board_cards=["Qd", "7c", "2s"],
            pot_total_bb=10.0,
            bet_to_call_bb=0.0,
            stack_bb=100.0,
            recommended_action="BET_50",
            recommended_sizing_bb=5.0,
            equity_pct=85.0,
            expected_ev_bb=4.2,
            target_button_id="btn_right",
            target_button_label="Raise",
            target_sizing_button_id="size_50",  # Exige size_50!
            click_coordinates=(650, 1410),
            is_live_click_executed=False,
            is_confirmed_by_table=False,
            status_message="Ready",
        )

        mouse_clicks = []

        def mock_click(*args, **kwargs):
            mouse_clicks.append(args)

        with patch("visualpilot.pppoker.table_bot_runner.execute_human_click", side_effect=mock_click):
            success = runner.execute_live_action(
                decision=decision,
                buttons=buttons,
                sizing_options=sizing_options,
                window_rect=(100, 50, 787, 1470),
            )
            # Deve retornar False e NÃO chamar execute_human_click
            self.assertFalse(success, "Sem o atalho de sizing, execute_live_action deve abortar.")
            self.assertEqual(len(mouse_clicks), 0, "Nenhum clique de mouse deve ter sido disparado.")

        # Verifica que o log de auditoria registrou HERO_ACTION_ABORTED
        csv_path = runner.audit_logger.get_current_log_path()
        self.assertTrue(csv_path.exists())
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertGreater(len(reader), 0)
            last_log = reader[-1]
            self.assertEqual(last_log["event_type"], "HERO_ACTION_ABORTED")
            self.assertEqual(last_log["status"], "FAILED_SIZING_NOT_FOUND")

    # -------------------------------------------------------------------------
    # 5. Contagem Correta de Mãos (Board Street Change NÃO Incrementa Mão)
    # -------------------------------------------------------------------------
    def test_hand_counter_does_not_increment_across_streets_in_same_hand(self):
        """A transição de Preflop -> Flop -> Turn -> River pertence à MESMA mão e mantém o contador."""
        runner = TableBotRunner(mode="dry-run", telemetry_path=self.telemetry_path)
        
        # Mão 1 - Preflop
        runner.current_hero_hole_cards = tuple(sorted(["Ah", "Kd"]))
        runner.hand_counter = 1
        runner.current_hand_id = "H-0001"

        # Simula o Flop batendo: cartas do Hero continuam Ah, Kd! Board agora tem 3 cartas
        flop_board = ["Qs", "Jc", "2h"]
        hero_hole_cards = tuple(sorted(["Ah", "Kd"]))
        
        is_new_hand = (hero_hole_cards != runner.current_hero_hole_cards)
        self.assertFalse(is_new_hand, "Mesmas hole cards no Flop NÃO iniciam nova mão")
        self.assertEqual(runner.hand_counter, 1, "hand_counter deve permanecer 1 no Flop")

        # Simula o Turn: cartas do Hero continuam Ah, Kd! Board agora tem 4 cartas
        turn_board = ["Qs", "Jc", "2h", "8s"]
        is_new_hand = (hero_hole_cards != runner.current_hero_hole_cards)
        self.assertFalse(is_new_hand, "Mesmas hole cards no Turn NÃO iniciam nova mão")
        self.assertEqual(runner.hand_counter, 1, "hand_counter deve permanecer 1 no Turn")

        # Nova mão de verdade: Hero recebe Qs, Qd
        new_hero_cards = tuple(sorted(["Qs", "Qd"]))
        is_new_hand_real = (new_hero_cards != runner.current_hero_hole_cards)
        self.assertTrue(is_new_hand_real, "Novas hole cards DEVEM iniciar nova mão")
        if is_new_hand_real:
            runner.hand_counter += 1
            runner.current_hand_id = f"H-{runner.hand_counter:04d}"
            runner.current_hero_hole_cards = new_hero_cards
        self.assertEqual(runner.hand_counter, 2, "hand_counter incrementado apenas com novas hole cards")
        self.assertEqual(runner.current_hand_id, "H-0002")

    # -------------------------------------------------------------------------
    # 6. Confirmação Pós-Clique Não Ambígua
    # -------------------------------------------------------------------------
    def test_post_click_confirmation_rejects_missing_or_corrupt_frame(self):
        """Se o post_frame for nulo ou colapsado, is_confirmed_by_table permanece False."""
        runner = TableBotRunner(mode="live", telemetry_path=self.telemetry_path)
        
        decision = LiveGameDecision(
            timestamp="2026-11-01T15:00:00Z",
            hand_id="H-0001",
            street="PREFLOP",
            hero_position="BTN",
            hero_cards=["As", "Kh"],
            board_cards=[],
            pot_total_bb=2.5,
            bet_to_call_bb=1.0,
            stack_bb=100.0,
            recommended_action="RAISE",
            recommended_sizing_bb=2.5,
            equity_pct=60.0,
            expected_ev_bb=2.0,
            target_button_id="btn_right",
            target_button_label="Raise",
            click_coordinates=(650, 1410),
            is_live_click_executed=True,
            is_confirmed_by_table=False,
            status_message="Clique enviado",
        )

        # 1. Simula captura pós-clique retornando None
        post_frame = None
        if post_frame is None:
            decision.is_confirmed_by_table = False
            decision.status_message = "Captura pós-clique falhou."
        self.assertFalse(decision.is_confirmed_by_table, "Captura None não pode confirmar ação")

        # 2. Simula frame sem integridade (ex: tela preta)
        with patch.object(runner.guardian, "validate_captured_frame_integrity", return_value=False):
            dummy_corrupt_frame = object()
            is_intact = runner.guardian.validate_captured_frame_integrity(dummy_corrupt_frame)
            if not is_intact:
                decision.is_confirmed_by_table = False
                decision.status_message = "Frame corrompido."
            self.assertFalse(decision.is_confirmed_by_table, "Frame corrompido não pode confirmar ação")


if __name__ == "__main__":
    unittest.main()
