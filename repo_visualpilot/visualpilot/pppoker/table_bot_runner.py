"""VisualPilot - Executador Unificado de Mesa em Tempo Real (Table Bot Runner).

Ciclo contínuo de jogo validado com leitura real da mesa:
1. Captura e monitora a janela ativa do PPPoker (ou emulador Android).
2. Valida visibilidade (Z-Order, minimização e oclusão) antes de agir.
3. Extrai as cartas reais do Hero e da mesa, pote e posições via Visão Computacional / OCR.
4. Consulta os Motores GTO (Pré-Flop 169 mãos + Pós-Flop Monte Carlo).
5. Dimensiona e executa a ação exata recomendada (ajustando sizing antes do clique se necessário).
6. Dispara clique biométrico com curva cúbica de Bézier e dispersão Gaussiana em modo --live.
7. Registra os eventos no CSV com parâmetros 100% compatíveis com AuditLogger.
8. Realiza confirmação pós-clique (verifica se os botões sumiram) e comprova continuidade de mãos.
9. Mantém a telemetria web atualizada em tempo real e desativa graciosamente para "STOPPED".
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import os
from pathlib import Path
import random
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


def encode_frame_thumbnail_b64(frame_np, max_dim: int = 420) -> Optional[str]:
    """Converte o frame NumPy da mesa para JPEG comprimido em base64 para transmissão web."""
    if frame_np is None:
        return None
    try:
        from PIL import Image
        import io
        if hasattr(frame_np, 'shape') and len(frame_np.shape) >= 2:
            h, w = frame_np.shape[:2]
            scale = min(1.0, max_dim / max(h, w))
            new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
            img = Image.fromarray(frame_np)
            img = img.resize((new_w, new_h), Image.Resampling.BILINEAR if hasattr(Image, 'Resampling') else Image.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=60)
            return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        pass
    return None


# Garantir que repo_visualpilot esteja no sys.path mesmo em execução direta
_current_file = Path(__file__).resolve()
for _ancestor in [_current_file.parent.parent.parent, _current_file.parent.parent]:
    if (_ancestor / "visualpilot").is_dir() and str(_ancestor) not in sys.path:
        sys.path.insert(0, str(_ancestor))


try:
    from visualpilot.boot_logger import (
        run_preflight_diagnostics,
        log_boot_event,
        TEMP_LOG_FILE,
    )
except Exception:
    def run_preflight_diagnostics(name: str = "bot") -> bool:
        return True
    def log_boot_event(*args, **kwargs) -> None:
        pass
    TEMP_LOG_FILE = Path("/tmp/visualpilot_boot_debug.log")


from visualpilot.pppoker.hero_action_detector import (
    HeroActionDetector,
    HeroActionSnapshot,
    ActionButton,
    BetSizingOption,
    calculate_jittered_click_point,
)
from visualpilot.pppoker.card_recognition import (
    CardRecognitionEngine,
    VALID_RANKS,
    VALID_SUITS,
    DEFAULT_HERO_ROIS_NLH,
    DEFAULT_BOARD_ROIS,
)
from visualpilot.pppoker.preflop_decision_engine import (
    PreflopDecisionEngine,
    ALL_169_HANDS,
    RANK_VALUES,
)
from visualpilot.pppoker.postflop_gto_engine import (
    PostflopGtoEngine,
)
from visualpilot.pppoker.brain_engine import (
    BrainEngine,
)
from visualpilot.pppoker.lobby_clicker import (
    AuditLogger,
    find_pppoker_window,
    execute_human_click,
    calculate_absolute_click,
)
from visualpilot.pppoker.table_numerical_ocr import (
    TableNumericalOcrEngine as TableNumericalOCR,
)
from visualpilot.pppoker.window_visibility_guardian import (
    WindowVisibilityGuardian,
    WindowVisibilityReport,
)
from visualpilot.pppoker.multi_table_tracker import (
    MultiTableTracker,
)

logger = logging.getLogger("visualpilot.table_runner")


def format_card_pt(card_str: str) -> str:
    """Formata carta em notação visual com naipes coloridos (ex: As -> A♠, Kh -> K♥)."""
    if not card_str or len(card_str) != 2:
        return card_str or "??"
    r, s = card_str[0], card_str[1].lower()
    suit_symbols = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
    return f"{r}{suit_symbols.get(s, s)}"


def canonical_hand_name(card1: str, card2: str) -> str:
    """Converte 2 cartas físicas (ex: 'As', 'Kh') para o formato canônico 169 (ex: 'AKo')."""
    if not card1 or not card2 or len(card1) < 2 or len(card2) < 2:
        return "AA"
    r1, s1 = card1[0].upper(), card1[1].lower()
    r2, s2 = card2[0].upper(), card2[1].lower()
    v1 = RANK_VALUES.get(r1, 0)
    v2 = RANK_VALUES.get(r2, 0)

    if v1 == v2:
        return f"{r1}{r2}"
    if v1 < v2:
        r1, r2, s1, s2 = r2, r1, s2, s1

    suffix = "s" if s1 == s2 else "o"
    return f"{r1}{r2}{suffix}"


def capture_window_frame(win_rect: Tuple[int, int, int, int]) -> Optional[Any]:
    """Captura a imagem real da janela na área de trabalho."""
    x, y, w, h = win_rect
    if w < 100 or h < 100:
        return None
    try:
        from PIL import ImageGrab
        import numpy as np
        # Coordenadas absolutas na tela (left, top, right, bottom)
        bbox = (x, y, x + w, y + h)
        img = ImageGrab.grab(bbox=bbox)
        return np.array(img)
    except Exception as exc:
        logger.debug("Captura de tela via ImageGrab indisponível: %s", exc)
        return None


@dataclass
class LiveGameDecision:
    timestamp: str
    hand_id: str
    street: str
    hero_position: str
    hero_cards: List[str]
    board_cards: List[str]
    pot_total_bb: float
    bet_to_call_bb: float
    stack_bb: float
    recommended_action: str
    recommended_sizing_bb: Optional[float] = None
    equity_pct: Optional[float] = None
    expected_ev_bb: float = 0.0
    target_button_id: str = "btn_center"
    target_button_label: str = "Check"
    target_sizing_button_id: Optional[str] = None
    click_coordinates: Tuple[int, int] = (0, 0)
    is_live_click_executed: bool = False
    is_confirmed_by_table: bool = False
    status_message: str = ""


class TableBotRunner:
    """Orquestrador da mesa de poker do PPPoker em tempo real."""

    def __init__(
        self,
        mode: str = "dry-run",
        interval_ms: int = 250,
        table_title: str = "PPPoker",
        max_hands: int = 0,
        telemetry_path: str = "public/live_table_stream.json",
        deck_mode: str = "four_color",
        allow_simulated_fallback: bool = False,
    ):
        self.mode = mode.lower()  # "dry-run", "spectator" ou "live"
        self.interval_sec = max(0.1, interval_ms / 1000.0)
        self.table_title = table_title
        self.max_hands = max_hands
        self.telemetry_path = telemetry_path
        self.deck_mode = deck_mode
        self.allow_simulated_fallback = allow_simulated_fallback

        # Inicialização dos subsistemas de Visão e Inteligência
        self.action_detector = HeroActionDetector()
        self.card_engine = CardRecognitionEngine(four_color_mode=(deck_mode == "four_color"))
        self.preflop_engine = PreflopDecisionEngine()
        self.postflop_engine = PostflopGtoEngine()
        self.brain_engine = BrainEngine()
        self.table_ocr = TableNumericalOCR()
        self.guardian = WindowVisibilityGuardian(target_keyword=table_title)
        self.multi_table_tracker = MultiTableTracker()
        self.audit_logger = AuditLogger(logs_dir="logs")

        # Controles de estado em tempo real
        self.is_running = False
        self.hand_counter = 0
        self.last_action_timestamp = 0.0
        self.current_hand_id = ""
        self.current_hero_hole_cards: Optional[Tuple[str, ...]] = None
        self.last_street_action_acted: Optional[Tuple[str, str, float]] = None
        self.last_hand_signature: Optional[Tuple[str, str, str]] = None
        self.recent_decisions: List[LiveGameDecision] = []
        self.last_snapshot: Optional[HeroActionSnapshot] = None
        self.last_decision: Optional[LiveGameDecision] = None
        self.is_human_takeover_active: bool = False
        self.last_frame_b64: Optional[str] = None
        self.last_win_rect: Optional[Tuple[int, int, int, int]] = None
        self.current_fps: float = 0.0
        self.last_status_message: str = "Aguardando início do loop..."
        self.telemetry_port: int = 8000
        self.telemetry_httpd: Optional[HTTPServer] = None

    def get_live_telemetry_dict(self) -> Dict[str, Any]:
        """Gera payload completo para o monitor web ao vivo."""
        win_w, win_h = 1920, 1080
        if self.last_win_rect:
            win_w, win_h = self.last_win_rect[2], self.last_win_rect[3]

        cards_hero = []
        if self.current_hero_hole_cards:
            cards_hero = list(self.current_hero_hole_cards)
        elif self.last_decision and self.last_decision.hero_cards:
            cards_hero = list(self.last_decision.hero_cards)

        board_c = []
        if self.last_decision and self.last_decision.board_cards:
            board_c = list(self.last_decision.board_cards)

        return {
            "mode": self.mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hand_counter": self.hand_counter,
            "status": "RUNNING" if self.is_running else "STOPPED",
            "fps": round(self.current_fps, 1),
            "table_title": self.table_title,
            "table_resolution": f"{win_w}x{win_h}",
            "window_found": bool(self.last_win_rect),
            "is_hero_turn": bool(self.last_snapshot and self.last_snapshot.is_hero_turn),
            "is_human_takeover": self.is_human_takeover_active,
            "hero_cards": cards_hero,
            "board_cards": board_c,
            "pot_bb": self.last_snapshot.pot_total_bb if self.last_snapshot else (self.last_decision.pot_total_bb if self.last_decision else 0.0),
            "hero_position": self.last_decision.hero_position if self.last_decision else "BTN",
            "recommended_action": self.last_decision.recommended_action if self.last_decision else "AGUARDANDO_ROBÔ",
            "recommended_sizing_bb": self.last_decision.recommended_sizing_bb if self.last_decision else 0.0,
            "equity_pct": self.last_decision.equity_pct if self.last_decision else 0.0,
            "ev_bb": self.last_decision.expected_ev_bb if self.last_decision else 0.0,
            "target_button_label": self.last_decision.target_button_label if self.last_decision else "",
            "snapshot": asdict(self.last_snapshot) if self.last_snapshot else None,
            "latest_decision": asdict(self.last_decision) if self.last_decision else None,
            "recent_decisions_count": len(self.recent_decisions),
            "last_frame_b64": self.last_frame_b64,
            "last_status_message": self.last_status_message,
        }

    def start_background_telemetry_server(self) -> None:
        """Inicia servidor HTTP nativo em segundo plano com suporte a CORS na porta 8000."""
        runner_self = self

        class EmbeddedHandler(BaseHTTPRequestHandler):
            def _cors(self, ctype="application/json"):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

            def do_OPTIONS(self):
                self._cors()
                self.wfile.write(b"")

            def do_GET(self):
                p = self.path.split("?")[0].rstrip("/")
                if p in ("", "/api", "/api/status", "/api/telemetry", "/api/telemetry/status"):
                    self._cors()
                    self.wfile.write(json.dumps(runner_self.get_live_telemetry_dict(), ensure_ascii=False).encode("utf-8"))
                    return
                if p == "/api/telemetry/frame":
                    b64_f = runner_self.last_frame_b64
                    if b64_f:
                        try:
                            raw = base64.b64decode(b64_f)
                            self._cors("image/jpeg")
                            self.wfile.write(raw)
                            return
                        except Exception:
                            pass
                    self.send_response(404)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(b'{"error":"Sem frame capturado"}')
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self):
                p = self.path.split("?")[0].rstrip("/")
                if p == "/api/takeover/pause":
                    Path("logs/takeover_paused.flag").touch(exist_ok=True)
                    self._cors()
                    self.wfile.write(b'{"status":"PAUSED"}')
                    return
                if p == "/api/takeover/resume":
                    Path("logs/takeover_paused.flag").unlink(missing_ok=True)
                    self._cors()
                    self.wfile.write(b'{"status":"RESUMED"}')
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, *args):
                pass

        for port in [8000, 8080, 8088]:
            try:
                self.telemetry_httpd = HTTPServer(("0.0.0.0", port), EmbeddedHandler)
                self.telemetry_port = port
                t = threading.Thread(target=self.telemetry_httpd.serve_forever, daemon=True)
                t.start()
                logger.info("Servidor de telemetria HTTP iniciado na porta %d", port)
                break
            except Exception:
                continue

    def stop(self) -> None:
        """Encerra a execução do loop graciosamente e atualiza telemetria."""
        self.is_running = False
        self.export_telemetry_snapshot(self.last_snapshot, self.last_decision, force_status="STOPPED")

    def check_human_takeover_status(self) -> bool:
        """
        Verifica se o operador humano assumiu o controle manual das mesas (pausando o robô).
        Pode ser acionado por:
        1. Arquivo flag: logs/takeover_paused.flag
        2. Arquivo de estado: logs/bot_control_state.json (com is_human_takeover=True ou is_paused=True)
        """
        # Checa flag direto
        for flag_path in [Path("logs/takeover_paused.flag"), Path("takeover_paused.flag")]:
            if flag_path.exists():
                return True
        # Checa json de estado
        for json_path in [Path("logs/bot_control_state.json"), Path("bot_control_state.json")]:
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("is_human_takeover") or data.get("is_paused"):
                            return True
                except Exception:
                    pass
        return False

    def resolve_window_geometry(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Localiza e valida a janela real do PPPoker através do guardião e MultiTableTracker,
        retornando exclusivamente a área cliente (client_rect) em coordenadas de tela.
        Bloqueia identificação desconhecida, ambiguidade, geometria inválida, minimização e oclusão.
        """
        try:
            # Varre e rastreia mesas ativas via MultiTableTracker
            tracked_tables = self.multi_table_tracker.scan_windows()
            vis = self.guardian.inspect_and_prepare_window(auto_restore=False, auto_focus=False)
            if not vis.is_found or vis.occlusion_status in ("WINDOW_NOT_FOUND", "WINDOW_AMBIGUOUS", "WINDOW_MINIMIZED", "INVALID_GEOMETRY"):
                logger.debug("Janela indisponível para captura. Status: %s - %s", vis.occlusion_status, vis.message)
                return None

            cx, cy, cw, ch = vis.client_rect
            if cw <= 100 or ch <= 100:
                logger.debug("Área cliente inválida (%dx%d)", cw, ch)
                return None

            return (cx, cy, cw, ch)
        except Exception as exc:
            if self.allow_simulated_fallback:
                return (100, 50, 787, 1470)
            logger.debug("Erro ao resolver geometria cliente da janela: %s", exc)
            return None

    def query_decision(
        self,
        hero_cards: List[str],
        board_cards: List[str],
        hero_pos: str,
        pot_bb: float,
        bet_to_call_bb: float,
        stack_bb: float,
        buttons: List[ActionButton],
        sizing_options: Optional[List[BetSizingOption]] = None,
    ) -> Tuple[str, Optional[float], float, float, str, str, Optional[str]]:
        """
        Calcula a melhor ação pokerística ponderada por GTO e pelo Cérebro.
        Retorna: (action_name, sizing_bb, equity_pct, expected_ev_bb, button_id, button_label, sizing_button_id)
        """
        street = "PREFLOP" if len(board_cards) == 0 else "FLOP" if len(board_cards) == 3 else "TURN" if len(board_cards) == 4 else "RIVER"

        # Mapeamento dos botões detectados
        btn_dict = {b.button_id: b for b in buttons}
        fold_btn = btn_dict.get("btn_left") or ActionButton("btn_left", "fold", "Fold", (1370, 48, 1455, 275))
        check_call_btn = btn_dict.get("btn_center") or ActionButton("btn_center", "call", "Call", (1370, 288, 1455, 515))
        bet_raise_btn = btn_dict.get("btn_right") or ActionButton("btn_right", "raise", "Raise", (1370, 528, 1455, 755))

        # Localiza o melhor botão de atalho de dimensionamento
        sizing_dict = {s.sizing_id: s for s in (sizing_options or [])}

        if street == "PREFLOP":
            c_name = canonical_hand_name(hero_cards[0], hero_cards[1]) if len(hero_cards) >= 2 else "AKo"
            spot = "RFI" if bet_to_call_bb <= 1.0 else "VS_RFI"
            matrix = self.preflop_engine.get_range_matrix(hero_pos, spot, stack_bb=stack_bb)
            strat = matrix.get(c_name)

            if not strat:
                return "FOLD", 0.0, 35.0, -0.2, fold_btn.button_id, fold_btn.label, None

            action = strat.action
            sizing = strat.sizing_bb
            ev = strat.ev_bb
            equity = 52.0

            if action in ("RAISE", "ALL_IN"):
                # Procura atalho que melhor se aproxime do valor
                sizing_btn_id = None
                if sizing:
                    if sizing <= 2.5 and "size_min" in sizing_dict:
                        sizing_btn_id = "size_min"
                    elif sizing <= 3.5 and "size_33" in sizing_dict:
                        sizing_btn_id = "size_33"
                return action, sizing, equity, ev, bet_raise_btn.button_id, bet_raise_btn.label, sizing_btn_id
            elif action == "CALL":
                return "CALL", sizing, equity, ev, check_call_btn.button_id, check_call_btn.label, None
            else:
                return "FOLD", 0.0, equity, 0.0, fold_btn.button_id, fold_btn.label, None

        else:
            # Pós-Flop: Usar simulador Monte Carlo com cartas reais
            try:
                sim = self.postflop_engine.calculate_equity(
                    hero_cards=hero_cards[:2],
                    board_cards=board_cards,
                    villain_range="LINEAR_3BET",
                    pot_bb=pot_bb,
                    stack_bb=stack_bb,
                    trials=300
                )
                equity = sim.hero_equity_pct
            except Exception as exc:
                logger.error("Falha no cálculo de equidade Monte Carlo pós-flop: %s. Salvaguarda defensiva acionada.", exc)
                equity = 0.0
                if bet_to_call_bb <= 0.1:
                    return "CHECK", 0.0, 0.0, 0.0, check_call_btn.button_id, "Check (Salvaguarda Falha)", None
                else:
                    return "FOLD", 0.0, 0.0, 0.0, fold_btn.button_id, "Fold (Salvaguarda Falha)", None

            if equity >= 65.0:
                # Value Bet / Raise
                sizing = round(pot_bb * 0.50, 1)
                ev = round(pot_bb * 0.35, 2)
                sizing_btn_id = "size_50" if "size_50" in sizing_dict else None
                return "BET_50", sizing, equity, ev, bet_raise_btn.button_id, f"Bet 50% ({sizing} BB)", sizing_btn_id
            elif equity >= 45.0:
                # Check / Call
                if bet_to_call_bb <= 0.1:
                    return "CHECK", 0.0, equity, 0.2, check_call_btn.button_id, "Check", None
                else:
                    return "CALL", bet_to_call_bb, equity, 0.5, check_call_btn.button_id, f"Call {bet_to_call_bb} BB", None
            else:
                # Check ou Fold
                if bet_to_call_bb <= 0.1:
                    return "CHECK", 0.0, equity, 0.0, check_call_btn.button_id, "Check", None
                else:
                    return "FOLD", 0.0, equity, 0.0, fold_btn.button_id, "Fold", None

    def execute_live_action(
        self,
        decision: LiveGameDecision,
        buttons: List[ActionButton],
        sizing_options: Any = None,
        window_rect: Optional[Tuple[int, int, int, int]] = None,
    ) -> bool:
        """Dispara o clique físico com camuflagem biométrica e registra auditoria completa."""
        if self.mode != "live":
            logger.info("[DRY-RUN] Clique suprimido por segurança.")
            return False

        if isinstance(sizing_options, tuple) and window_rect is None:
            window_rect = sizing_options
            sizing_options = None
        if sizing_options is None:
            sizing_options = []

        # Localizar botão principal alvo
        target_btn = next((b for b in buttons if b.button_id == decision.target_button_id), None)
        if not target_btn:
            logger.warning("Botão alvo %s não encontrado nos botões ativos.", decision.target_button_id)
            return False

        # Recalibra dinamicamente as dimensões da janela diretamente da API PyGetWindow
        # NUNCA usa coordenadas antigas ou padrão se a janela não for encontrada no instante exato do clique!
        fresh_geo = self.resolve_window_geometry()
        if fresh_geo is None or fresh_geo[2] <= 0 or fresh_geo[3] <= 0:
            logger.critical("ABORTADO: Janela do PPPoker não localizada ou minimizada! Coordenadas invalidadas para proteger contra cliques fora da janela.")
            self.audit_logger.log_event(
                event_type="HERO_ACTION_ABORTED",
                status="WINDOW_NOT_FOUND",
                tournament_name=f"Live Table - Hand {decision.hand_id}",
                target_abs_x="",
                target_abs_y="",
                win_box=[0, 0, 0, 0],
                details="Janela alvo não encontrada no momento do clique. Coordenadas antigas descartadas para segurança.",
                session_name="Mesa Live",
            )
            return False

        window_rect = fresh_geo
        win_x, win_y, win_w, win_h = window_rect
        win_dict = {"left": win_x, "top": win_y, "width": win_w, "height": win_h}

        try:
            # 1. Se houver necessidade de ajustar o sizing antes do Raise, clica no atalho primeiro
            if decision.target_sizing_button_id:
                sizing_btn = next(
                    (s for s in sizing_options if (getattr(s, "sizing_id", getattr(s, "shortcut_id", None)) == decision.target_sizing_button_id)),
                    None
                )
                if not sizing_btn or not sizing_btn.box or sizing_btn.box == (0, 0, 0, 0):
                    logger.error(
                        "ABORTADO: Decisão de Raise requer o atalho '%s', mas o botão não está disponível. Clique cancelado por segurança.",
                        decision.target_sizing_button_id
                    )
                    self.audit_logger.log_event(
                        event_type="HERO_ACTION_ABORTED",
                        status="FAILED_SIZING_NOT_FOUND",
                        tournament_name=f"Live Table - Hand {decision.hand_id}",
                        target_abs_x="",
                        target_abs_y="",
                        win_box=list(window_rect),
                        details=(
                            f"Atalho de dimensionamento '{decision.target_sizing_button_id}' ausente. "
                            f"Clique no botão de Raise bloqueado para evitar aposta no valor incorreto."
                        ),
                        session_name="Mesa Live",
                    )
                    return False

                s_pt = calculate_jittered_click_point(sizing_btn.box, sigma=3.0)
                abs_s_x, abs_s_y, _ = calculate_absolute_click(
                    click_point_local=s_pt,
                    window_rect=win_dict,
                    captured_size=(787, 1470),
                    apply_jitter=False,
                )
                execute_human_click(
                    x=abs_s_x,
                    y=abs_s_y,
                    move_duration=round(random.uniform(0.18, 0.28), 3),
                    press_delay=round(random.uniform(0.05, 0.09), 3),
                    dry_run=False,
                )
                time.sleep(random.uniform(0.08, 0.14))

            # 1.8. Verificação de Segurança de Sizing no Botão (Bet Sizing Safety Gate)
            if decision.recommended_action in ("BET_50", "RAISE", "ALL_IN") and decision.recommended_sizing_bb is not None:
                import re
                btn_numbers = re.findall(r"\d+(?:[.,]\d+)?", target_btn.label.replace(",", "."))
                if btn_numbers:
                    btn_val = float(btn_numbers[0])
                    diff = abs(btn_val - decision.recommended_sizing_bb)
                    rel_diff = diff / max(0.1, decision.recommended_sizing_bb)
                    if diff > 0.5 and rel_diff > 0.18:
                        logger.critical(
                            "ABORTADO POR SEGURANÇA: Sizing no botão ('%s' -> %.1f BB) difere do recomendado (%.1f BB). Clique cancelado.",
                            target_btn.label, btn_val, decision.recommended_sizing_bb
                        )
                        self.audit_logger.log_event(
                            event_type="HERO_ACTION_ABORTED",
                            status="FAILED_SIZING_MISMATCH",
                            tournament_name=f"Live Table - Hand {decision.hand_id}",
                            target_abs_x="",
                            target_abs_y="",
                            win_box=list(window_rect),
                            details=f"Sizing recomendado ({decision.recommended_sizing_bb} BB) difere do valor no botão ({btn_val} BB / '{target_btn.label}'). Clique bloqueado preventivamente.",
                            session_name="Mesa Live",
                        )
                        return False

            # 2. Clica no botão principal da ação (Fold / Call / Raise) usando SUA PRÓPRIA CAIXA
            jittered_point = calculate_jittered_click_point(target_btn.box, sigma=3.5)
            abs_x, abs_y, _ = calculate_absolute_click(
                click_point_local=jittered_point,
                window_rect=win_dict,
                captured_size=(787, 1470),
                apply_jitter=False,
            )

            click_duration_ms = random.uniform(320.0, 540.0)
            execute_human_click(
                x=abs_x,
                y=abs_y,
                move_duration=round(random.uniform(0.24, 0.38), 3),
                press_delay=round(random.uniform(0.06, 0.11), 3),
                dry_run=False,
            )

            # 3. Registro inviolável no CSV de Auditoria com parâmetros compatíveis com AuditLogger
            canonical_hand = canonical_hand_name(decision.hero_cards[0], decision.hero_cards[1]) if len(decision.hero_cards) >= 2 else "AKo"
            self.audit_logger.log_event(
                event_type="HERO_ACTION_CLICK",
                status="SUCCESS",
                tournament_name=f"Live Table - Hand {decision.hand_id}",
                card_index=canonical_hand,
                buyin_chips=str(decision.pot_total_bb),
                target_abs_x=str(abs_x),
                target_abs_y=str(abs_y),
                win_box=list(window_rect),
                duration_ms=round(click_duration_ms, 1),
                details=(
                    f"Ação={decision.recommended_action} | Sizing={decision.recommended_sizing_bb or 0} BB | "
                    f"Botão={target_btn.button_id} ('{target_btn.label}') | Pos={decision.hero_position} | "
                    f"Equidade={decision.equity_pct:.1f}% | EV={decision.expected_ev_bb:+.2f} BB"
                ),
                session_name="Mesa Live",
            )
            return True
        except Exception as exc:
            logger.error("Falha ao executar clique em modo live: %s", exc)
            return False

    def export_telemetry_snapshot(
        self,
        snapshot: Optional[HeroActionSnapshot],
        latest_decision: Optional[LiveGameDecision],
        force_status: Optional[str] = None
    ) -> None:
        """Exporta telemetria atualizada para a interface web em tempo real."""
        data = self.get_live_telemetry_dict()
        if force_status:
            data["status"] = force_status
        for target in [Path("logs/telemetry.json"), Path(self.telemetry_path)]:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            except Exception:
                pass

    def run_table_loop(self) -> None:
        """Ciclo contínuo de observação, análise e decisão com leitura de mesa real."""
        self.is_running = True
        logger.info("Iniciando TableBotRunner no modo [%s] (Intervalo: %.2fs)", self.mode.upper(), self.interval_sec)
        
        # Inicia servidor HTTP em background para permitir transmissão web em tempo real
        self.start_background_telemetry_server()

        print("=" * 70)
        print(f"   VISUALPILOT - RUNNER UNIFICADO DE MESA [{self.mode.upper()}]")
        print("=" * 70)
        print(f"• Alvo da Janela     : {self.table_title}")
        print(f"• Modo de Operação   : {self.mode.upper()} ({'Sem cliques físicos' if self.mode in ('dry-run', 'spectator') else 'Cliques Reais Ativos!'})")
        print(f"• Frequência de Loop : {self.interval_sec * 1000:.0f} ms")
        print(f"• Transmissão Web    : http://localhost:{self.telemetry_port}/api/telemetry")
        print(f"• Pressione Ctrl+C para encerrar com segurança.")
        print("-" * 70)

        loop_cycles = 0
        start_time = time.time()
        last_heartbeat_time = 0.0

        try:
            while self.is_running:
                loop_cycles += 1
                now = time.time()

                # 1. Localizar janela do PPPoker (rejeita se minimizada ou bloqueada)
                win_rect = self.resolve_window_geometry()
                self.last_win_rect = win_rect

                if not win_rect:
                    self.last_status_message = "Procurando janela 'PPPoker' no Windows..."
                    if now - last_heartbeat_time >= 1.5:
                        last_heartbeat_time = now
                        ts = datetime.now().strftime("%H:%M:%S")
                        print(f"[{ts}] [PROCURANDO MESA] Janela '{self.table_title}' não localizada. Abra o PPPoker na tela...")
                        self.export_telemetry_snapshot(None, self.last_decision)
                    time.sleep(self.interval_sec)
                    continue

                # 1.5. Verificação de Intervenção Humana (Human Takeover / Pausa Manual)
                if self.check_human_takeover_status():
                    if not self.is_human_takeover_active:
                        self.is_human_takeover_active = True
                        logger.info("[HUMAN TAKEOVER] Operador assumiu controle manual da mesa. Cliques suspensos.")
                        print("\n" + "=" * 70)
                        print("  🕹️  [CONTROLE MANUAL ATIVO] O OPERADOR ASSUMIU O CONTROLE DAS MESAS!")
                        print("  • O robô está PAUSADO. Nenhum clique será executado pelo mouse.")
                        print("  • Você tem controle total das decisões no PPPoker.")
                        print("  • Para devolver o controle ao robô, clique em 'Retomar Bot' no painel")
                        print("    ou remova o arquivo logs/takeover_paused.flag.")
                        print("=" * 70 + "\n")
                    time.sleep(0.4)
                    continue
                else:
                    if self.is_human_takeover_active:
                        self.is_human_takeover_active = False
                        logger.info("[HUMAN TAKEOVER] Controle devolvido ao bot. Operação autônoma reativada.")
                        print("\n" + "=" * 70)
                        print("  🤖 [AUTÔNOMO RETOMADO] O ROBÔ VOLTOU A OPERAR SOZINHO!")
                        print("  • Reavaliando mesa com segurança em 1.5 segundos...")
                        print("=" * 70 + "\n")
                        time.sleep(1.5)

                # 2. Captura o frame real da janela
                frame = capture_window_frame(win_rect)
                if frame is not None:
                    self.last_frame_b64 = encode_frame_thumbnail_b64(frame)

                # 3. Inspeciona ações e se é a vez do Hero no frame real
                action_snap = self.action_detector.detect_actions(table_frame=frame)
                self.last_snapshot = action_snap

                # 3.5. Batimento cardíaco visual no terminal a cada ~1.5 segundos
                if now - last_heartbeat_time >= 1.5:
                    last_heartbeat_time = now
                    fps = loop_cycles / max(0.1, (now - start_time))
                    self.current_fps = fps
                    ts = datetime.now().strftime("%H:%M:%S")
                    w, h = win_rect[2], win_rect[3]
                    if action_snap.is_hero_turn:
                        status_desc = "SUA VEZ (Hero Turn)! Calculando decisões GTO..."
                        print(f"[{ts}] [SUA VEZ] Janela '{self.table_title}' ({w}x{h}) | Frame #{loop_cycles} ({fps:.1f} FPS) | {status_desc}")
                    else:
                        status_desc = "Aguardando sua vez de agir (Hero Turn)..."
                        print(f"[{ts}] [MONITORANDO] Janela '{self.table_title}' ({w}x{h}) | Frame #{loop_cycles} ({fps:.1f} FPS) | {status_desc}")
                    self.last_status_message = status_desc
                    self.export_telemetry_snapshot(action_snap, self.last_decision)

                if action_snap.is_hero_turn:
                    # 4. Lê cartas reais da mesa via Visão Computacional
                    card_read_result = self.card_engine.read_table_frame(table_frame=frame)
                    raw_hero_cards: List[str] = []
                    raw_board_cards: List[str] = []

                    # Suporta formato direto list of str ou lista 'cards' com dicts/objetos
                    if "hero_cards" in card_read_result and isinstance(card_read_result["hero_cards"], list):
                        raw_hero_cards = [c for c in card_read_result["hero_cards"] if isinstance(c, str) and len(c) >= 2]
                    if "board_cards" in card_read_result and isinstance(card_read_result["board_cards"], list):
                        raw_board_cards = [c for c in card_read_result["board_cards"] if isinstance(c, str) and len(c) >= 2]

                    if not raw_hero_cards and "cards" in card_read_result:
                        for c in card_read_result["cards"]:
                            c_str = c.get("card_str") if isinstance(c, dict) else getattr(c, "card_str", "")
                            is_h = c.get("is_hero") if isinstance(c, dict) else getattr(c, "is_hero", False)
                            conf = c.get("confidence", 0) if isinstance(c, dict) else getattr(c, "confidence", 0)
                            if c_str and len(c_str) >= 2 and conf >= 0.4:
                                if is_h:
                                    raw_hero_cards.append(c_str)
                                else:
                                    raw_board_cards.append(c_str)

                    # 4.2 Lê estado numérico da mesa (Pote, Stacks, Posições relativas ao Dealer)
                    table_snap = self.table_ocr.process_table_state(table_frame=frame)
                    hero_pos = table_snap.hero_position or "BTN"
                    hero_seat_data = next((s for s in table_snap.seats if s.is_hero), None)
                    detected_stack = hero_seat_data.stack_bb if hero_seat_data else 0.0
                    detected_pot = action_snap.pot_total_bb if action_snap.pot_total_bb > 0 else table_snap.total_pot_bb
                    detected_bet_to_call = action_snap.current_bet_to_call_bb if action_snap.current_bet_to_call_bb > 0 else table_snap.call_amount_bb

                    if not self.allow_simulated_fallback:
                        # Modo estrito: Rejeita execução se não houver leitura real
                        if len(raw_hero_cards) < 2:
                            logger.debug("Vez do Hero detectada, mas cartas ainda não estão nítidas. Aguardando frame límpido.")
                            time.sleep(0.15)
                            continue
                        if detected_pot <= 0.0 or detected_stack <= 0.0:
                            logger.debug("Pote ou Stack do Hero não identificados no OCR. Aguardando leitura válida.")
                            time.sleep(0.15)
                            continue

                        hero_cards = raw_hero_cards
                        board_cards = raw_board_cards
                        pot_bb = detected_pot
                        bet_to_call = detected_bet_to_call
                        stack_bb = detected_stack
                    else:
                        hero_cards = raw_hero_cards if len(raw_hero_cards) >= 2 else ["As", "Kh"]
                        board_cards = raw_board_cards
                        pot_bb = detected_pot if detected_pot > 0 else 18.0
                        bet_to_call = detected_bet_to_call if detected_bet_to_call > 0 else 2.5
                        stack_bb = detected_stack if detected_stack > 0 else 100.0

                    # 5. Comprovação de nova mão:
                    sorted_hole_cards = tuple(sorted(hero_cards))
                    if sorted_hole_cards != self.current_hero_hole_cards:
                        self.hand_counter += 1
                        self.current_hand_id = f"H-{self.hand_counter:04d}"
                        self.current_hero_hole_cards = sorted_hole_cards
                        self.last_street_action_acted = None
                        logger.info("Nova mão iniciada: %s com cartas %s", self.current_hand_id, sorted_hole_cards)

                    current_street = "PREFLOP" if not board_cards else "FLOP" if len(board_cards) == 3 else "TURN" if len(board_cards) == 4 else "RIVER"
                    action_signature = (self.current_hand_id, current_street, bet_to_call)

                    # Se já agimos nesta mesma street e a aposta não mudou, evita repetição imediata
                    if action_signature == self.last_street_action_acted:
                        time.sleep(0.15)
                        continue

                    self.last_action_timestamp = time.time()

                    # 6. Consultar decisão GTO com cartas reais e dimensionamento exato
                    act_name, sizing, eq, ev, btn_id, btn_label, sizing_btn_id = self.query_decision(
                        hero_cards=hero_cards,
                        board_cards=board_cards,
                        hero_pos=hero_pos,
                        pot_bb=pot_bb,
                        bet_to_call_bb=bet_to_call,
                        stack_bb=stack_bb,
                        buttons=action_snap.buttons,
                        sizing_options=action_snap.sizing_options,
                    )

                    target_btn_obj = next((b for b in action_snap.buttons if b.button_id == btn_id), None)
                    target_box = target_btn_obj.box if target_btn_obj else (1370, 528, 1455, 755)
                    jittered_pt = calculate_jittered_click_point(target_box, sigma=3.5)

                    decision = LiveGameDecision(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        hand_id=self.current_hand_id,
                        street=current_street,
                        hero_position=hero_pos,
                        hero_cards=hero_cards,
                        board_cards=board_cards,
                        pot_total_bb=pot_bb,
                        bet_to_call_bb=bet_to_call,
                        stack_bb=stack_bb,
                        recommended_action=act_name,
                        recommended_sizing_bb=sizing,
                        equity_pct=eq,
                        expected_ev_bb=ev,
                        target_button_id=btn_id,
                        target_button_label=btn_label,
                        target_sizing_button_id=sizing_btn_id,
                        click_coordinates=jittered_pt,
                        is_live_click_executed=False,
                        is_confirmed_by_table=False,
                        status_message=f"Decisão calculada ({act_name})",
                    )
                    self.last_decision = decision
                    self.last_street_action_acted = action_signature

                    # 7. Execução Física do Clique em modo LIVE
                    if self.mode == "live":
                        executed = self.execute_live_action(
                            decision=decision,
                            buttons=action_snap.buttons,
                            sizing_options=action_snap.sizing_options,
                            window_rect=win_rect,
                        )
                        decision.is_live_click_executed = executed

                        # 8. Confirmação Visual Pós-Clique
                        time.sleep(0.25)
                        post_frame = capture_window_frame(win_rect)
                        if post_frame is None:
                            decision.is_confirmed_by_table = False
                            decision.status_message = "Clique despachado, aguardando atualização da mesa."
                        else:
                            is_frame_intact = self.guardian.validate_captured_frame_integrity(post_frame)
                            if not is_frame_intact:
                                decision.is_confirmed_by_table = False
                                decision.status_message = "Frame pós-clique em transição. Confirmação suspensa."
                            else:
                                post_snap = self.action_detector.detect_actions(table_frame=post_frame)
                                if not post_snap.is_hero_turn:
                                    decision.is_confirmed_by_table = True
                                    decision.status_message = "Ação executada com sucesso e confirmada pela mesa."
                                else:
                                    decision.is_confirmed_by_table = False
                                    decision.status_message = "Clique despachado, aguardando servidor do PPPoker."

                        print("\n" + "=" * 70)
                        print(f"  ⚡ [MODO AO VIVO - CLIQUE EXECUTADO] Mão {decision.hand_id} | Pos: {hero_pos}")
                        print(f"  • Cartas Hero : {[format_card_pt(c) for c in hero_cards]} | Bordo: {[format_card_pt(c) for c in board_cards]}")
                        print(f"  • Ação GTO    : {act_name} {f'({sizing} BB)' if sizing else ''} -> Botão: {btn_label}")
                        print(f"  • Equidade/EV : {eq:.1f}% / {ev:+.2f} BB | Pote: {pot_bb:.1f} BB")
                        print(f"  • Confirmação : {'SIM (Confirmado pela mesa)' if decision.is_confirmed_by_table else 'PENDENTE'}")
                        print("=" * 70 + "\n")
                    else:
                        print("\n" + "=" * 70)
                        print(f"  🛡️ [MODO FANTASMA - ESPECTADOR] Mão {decision.hand_id} | Pos: {hero_pos}")
                        print(f"  • Cartas Hero : {[format_card_pt(c) for c in hero_cards]} | Bordo: {[format_card_pt(c) for c in board_cards]}")
                        print(f"  • Ação Sugerida: {act_name} {f'({sizing} BB)' if sizing else ''} -> Botão: {btn_label}")
                        print(f"  • Equidade/EV  : {eq:.1f}% / {ev:+.2f} BB | Pote: {pot_bb:.1f} BB")
                        print("  • Clique Físico: SUPRIMIDO (Zero Cliques - 100% Seguro)")
                        print("=" * 70 + "\n")
                        # Emite bipe sonoro de alerta no terminal
                        try:
                            if sys.platform == "win32":
                                import winsound
                                winsound.Beep(1200, 200)
                            else:
                                sys.stdout.write("\a")
                                sys.stdout.flush()
                        except Exception:
                            pass

                    self.recent_decisions.append(decision)
                    self.export_telemetry_snapshot(action_snap, decision)

                    if self.max_hands > 0 and self.hand_counter >= self.max_hands:
                        print(f"Limite de {self.max_hands} mãos atingido. Concluindo sessão.")
                        break

                time.sleep(self.interval_sec)

        except KeyboardInterrupt:
            print("\nSessão interrompida pelo usuário (Ctrl+C).")
        finally:
            self.stop()
            print("=" * 70)
            print(f"Resumo da Execução: {self.hand_counter} mãos monitoradas.")
            print(f"Status Final: STOPPED | Modo: {self.mode.upper()}")
            print(f"Telemetria finalizada em: {self.telemetry_path}")
            print("=" * 70)


def run_table_bot(dry_run: bool = True, table_title: str = "PPPoker", interval_ms: int = 250) -> None:
    """Função de entrada exportada para invocação direta pelo launcher.py."""
    mode = "spectator" if dry_run else "live"
    runner = TableBotRunner(mode=mode, table_title=table_title, interval_ms=interval_ms)
    runner.run_table_loop()



def main() -> None:
    parser = argparse.ArgumentParser(description="VisualPilot - Runner de Mesa em Tempo Real & Modo Fantasma (PPPoker)")
    parser.add_argument(
        "--mode",
        choices=["dry-run", "spectator", "live"],
        default="spectator",
        help="Modo de execução: 'spectator'/'dry-run' (apenas observa e calcula) ou 'live' (executa cliques reais)",
    )
    parser.add_argument(
        "--spectator",
        dest="is_spectator",
        action="store_true",
        help="Ativa o Modo Fantasma de Segurança: 100% sem cliques, apenas monitora e exibe decisões",
    )
    parser.add_argument(
        "--dry-run",
        dest="is_dry_run",
        action="store_true",
        help="Equivalente a --spectator (Modo Fantasma de Segurança)",
    )
    parser.add_argument(
        "--live",
        dest="is_live",
        action="store_true",
        help="Arma o bot para executar cliques físicos reais na janela do PPPoker",
    )
    parser.add_argument(
        "--sound",
        action="store_true",
        help="Emite alerta sonoro no terminal sempre que for a vez do Hero",
    )
    parser.add_argument("--interval-ms", type=int, default=250, help="Intervalo do loop em milissegundos")
    parser.add_argument("--table-title", type=str, default="PPPoker", help="Título da janela a monitorar")
    parser.add_argument("--max-hands", type=int, default=0, help="Número máximo de mãos a executar antes de parar (0 = infinito)")
    parser.add_argument("--telemetry-path", type=str, default="public/live_table_stream.json", help="Arquivo JSON de saída")
    parser.add_argument("--allow-simulated-fallback", action="store_true", help="Permite fallback simulado caso o cliente real não esteja aberto")
    args = parser.parse_args()

    # Executa pré-voo de ambiente e registra no log temporário
    log_boot_event("BOT", f"Iniciando TableBotRunner | Modo: {args.mode} | Live: {args.is_live}")
    preflight_ok = run_preflight_diagnostics("table_bot_runner")
    if not preflight_ok:
        err_msg = (
            "\n" + "=" * 65 + "\n"
            " [FALHA DE PRÉ-VOO]: O bot não pode iniciar sem as dependências!\n"
            " Execute no terminal CMD:\n"
            "     corrigir_instalacao.bat\n"
            " ou:\n"
            "     pip install -r requirements.txt\n"
            f" Log completo em: {TEMP_LOG_FILE}\n"
            + "=" * 65 + "\n"
        )
        print(err_msg, file=sys.stderr)
        log_boot_event("BOT", "Falha de pré-voo em table_bot_runner", details=err_msg, status="FAIL")
        if sys.stdin and sys.stdin.isatty():
            input("\nPressione ENTER para fechar...")
        sys.exit(1)

    mode = "live" if args.is_live else "spectator" if (args.is_spectator or args.is_dry_run) else args.mode
    try:
        runner = TableBotRunner(
            mode=mode,
            interval_ms=args.interval_ms,
            table_title=args.table_title,
            max_hands=args.max_hands,
            telemetry_path=args.telemetry_path,
            allow_simulated_fallback=args.allow_simulated_fallback,
        )
        runner.run_table_loop()
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        log_boot_event("FATAL", "Exceção não tratada em table_bot_runner", details=tb, status="FAIL")
        print(f"\n[ERRO CRÍTICO EM TABLE_BOT_RUNNER]:\n{tb}", file=sys.stderr)
        if sys.stdin and sys.stdin.isatty():
            input("\nPressione ENTER para fechar...")
        raise


if __name__ == "__main__":
    main()

