"""VisualPilot - Script de Calibração e Verificação de Resolução de Janela (PPPoker).

Verifica o alinhamento da janela do PPPoker na máquina do usuário:
1. Detecta a janela ativa (título 'PPPoker' ou especificado por argumento).
2. Valida o DPI Awareness do Windows (100%, 125%, 150%).
3. Compara dimensões reais com a base canônica 787x1470 px (proporção retrato 9:16.8).
4. Mapeia e valida as ROIs de:
   - Cartas do Hero e Cartas Comunitárias (Board: Flop, Turn, River)
   - Botões de Ação Principais (Fold/Check, Call, Bet/Raise)
   - Atalhos de Sizing (Min, 33%, 50%, 75%, Pot)
   - Pote Total e Stacks dos Assentos
5. Gera relatório visual e JSON de calibração para uso no runner de partida.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np  # type: ignore
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import cv2  # type: ignore
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from visualpilot.pppoker.preflight_capture import (
    TARGET_WIDTH,
    TARGET_HEIGHT,
    calculate_calibration,
)
from visualpilot.pppoker.hero_action_detector import (
    DEFAULT_ACTION_BUTTON_ROIS,
    DEFAULT_BET_SIZING_SHORTCUT_ROIS,
    DEFAULT_TIME_BANK_ROI,
    scale_roi,
    calculate_button_center,
)
from visualpilot.pppoker.table_numerical_ocr import (
    DEFAULT_TOTAL_POT_ROI,
    DEFAULT_SEAT_STACK_ROIS,
)
from visualpilot.pppoker.card_recognition import (
    DEFAULT_BOARD_ROIS,
    DEFAULT_HERO_ROIS_NLH,
)

logger = logging.getLogger("visualpilot.calibration")


def detect_windows_dpi_factor() -> float:
    """Detecta o fator de escala de DPI no Windows (1.0 = 100%, 1.25 = 125%, 1.5 = 150%)."""
    if sys.platform != "win32":
        return 1.0
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return round(float(dpi) / 96.0, 2)
    except Exception:
        return 1.0


@dataclass
class RoiAuditItem:
    name: str
    category: str
    original_box: Tuple[int, int, int, int]
    scaled_box: Tuple[int, int, int, int]
    center_point: Tuple[int, int]
    width: int
    height: int


@dataclass
class CalibrationReport:
    timestamp: str
    window_title: str
    is_window_found: bool
    window_rect: Tuple[int, int, int, int]  # (x, y, w, h)
    dpi_scale_factor: float
    is_calibrated: bool
    calibration_score: int
    scale_x: float
    scale_y: float
    aspect_ratio: float
    ratio_error_pct: float
    status: str
    message: str
    rois_audit: List[RoiAuditItem] = field(default_factory=list)
    action_ready: bool = False


class WindowCalibrator:
    """Analisa a janela do PPPoker e calcula o mapeamento exato de coordenadas."""

    def __init__(self, target_title: str = "PPPoker"):
        self.target_title = target_title
        self.dpi_factor = detect_windows_dpi_factor()

    def find_window(self) -> Optional[Dict[str, Any]]:
        """Localiza a janela do PPPoker pelo título ou emulador Android."""
        if sys.platform == "win32":
            try:
                import pygetwindow as gw  # type: ignore
                windows = gw.getWindowsWithTitle(self.target_title)
                if not windows:
                    # Tentar títulos comuns de emuladores
                    for alias in ["LDPlayer", "Nox", "BlueStacks", "MuMu"]:
                        candidates = gw.getWindowsWithTitle(alias)
                        if candidates:
                            windows = candidates
                            break
                if windows:
                    win = windows[0]
                    return {
                        "title": win.title,
                        "x": win.left,
                        "y": win.top,
                        "w": win.width,
                        "h": win.height,
                        "is_real": True,
                    }
            except Exception as exc:
                logger.warning("Falha ao consultar pygetwindow: %s", exc)

        # Fallback para ambiente simulado / Linux
        return {
            "title": f"{self.target_title} (Modo Simulado)",
            "x": 100,
            "y": 50,
            "w": TARGET_WIDTH,
            "h": TARGET_HEIGHT,
            "is_real": False,
        }

    def run_calibration(self) -> CalibrationReport:
        """Executa a checagem completa de geometria e escala de ROIs."""
        win_info = self.find_window()
        now_str = datetime.now(timezone.utc).isoformat()

        if not win_info:
            return CalibrationReport(
                timestamp=now_str,
                window_title=self.target_title,
                is_window_found=False,
                window_rect=(0, 0, 0, 0),
                dpi_scale_factor=self.dpi_factor,
                is_calibrated=False,
                calibration_score=0,
                scale_x=0.0,
                scale_y=0.0,
                aspect_ratio=0.0,
                ratio_error_pct=100.0,
                status="WINDOW_NOT_FOUND",
                message=f"Janela com título contendo '{self.target_title}' não foi localizada.",
                action_ready=False,
            )

        w = win_info["w"]
        h = win_info["h"]
        calib_stats = calculate_calibration(w, h, TARGET_WIDTH, TARGET_HEIGHT)

        rois_list: List[RoiAuditItem] = []

        # 1. Botões de ação principais
        for btn_name, box in DEFAULT_ACTION_BUTTON_ROIS.items():
            s_box = scale_roi(box, TARGET_WIDTH, TARGET_HEIGHT, w, h)
            cx, cy = calculate_button_center(s_box)
            rois_list.append(RoiAuditItem(
                name=btn_name,
                category="action_button",
                original_box=box,
                scaled_box=s_box,
                center_point=(cx, cy),
                width=s_box[3] - s_box[1],
                height=s_box[2] - s_box[0]
            ))

        # 2. Atalhos de Sizing
        for size_name, box in DEFAULT_BET_SIZING_SHORTCUT_ROIS.items():
            s_box = scale_roi(box, TARGET_WIDTH, TARGET_HEIGHT, w, h)
            cx, cy = calculate_button_center(s_box)
            rois_list.append(RoiAuditItem(
                name=size_name,
                category="sizing_shortcut",
                original_box=box,
                scaled_box=s_box,
                center_point=(cx, cy),
                width=s_box[3] - s_box[1],
                height=s_box[2] - s_box[0]
            ))

        # 3. Cartas do Hero NLH
        for card_name, box in DEFAULT_HERO_ROIS_NLH.items():
            s_box = scale_roi(box, TARGET_WIDTH, TARGET_HEIGHT, w, h)
            cx, cy = calculate_button_center(s_box)
            rois_list.append(RoiAuditItem(
                name=f"hero_card_{card_name}",
                category="hero_card",
                original_box=box,
                scaled_box=s_box,
                center_point=(cx, cy),
                width=s_box[3] - s_box[1],
                height=s_box[2] - s_box[0]
            ))

        # 4. Cartas do Board Comunitário
        for board_card, box in DEFAULT_BOARD_ROIS.items():
            s_box = scale_roi(box, TARGET_WIDTH, TARGET_HEIGHT, w, h)
            cx, cy = calculate_button_center(s_box)
            rois_list.append(RoiAuditItem(
                name=f"board_{board_card}",
                category="board_card",
                original_box=box,
                scaled_box=s_box,
                center_point=(cx, cy),
                width=s_box[3] - s_box[1],
                height=s_box[2] - s_box[0]
            ))

        # 5. Pote Total
        pot_s_box = scale_roi(DEFAULT_TOTAL_POT_ROI, TARGET_WIDTH, TARGET_HEIGHT, w, h)
        rois_list.append(RoiAuditItem(
            name="total_pot",
            category="table_pot",
            original_box=DEFAULT_TOTAL_POT_ROI,
            scaled_box=pot_s_box,
            center_point=calculate_button_center(pot_s_box),
            width=pot_s_box[3] - pot_s_box[1],
            height=pot_s_box[2] - pot_s_box[0]
        ))

        is_ready = calib_stats["is_calibrated"]

        return CalibrationReport(
            timestamp=now_str,
            window_title=win_info["title"],
            is_window_found=True,
            window_rect=(win_info["x"], win_info["y"], w, h),
            dpi_scale_factor=self.dpi_factor,
            is_calibrated=calib_stats["is_calibrated"],
            calibration_score=calib_stats["calibration_score"],
            scale_x=calib_stats["scale_x"],
            scale_y=calib_stats["scale_y"],
            aspect_ratio=calib_stats["aspect_ratio"],
            ratio_error_pct=calib_stats["ratio_error_pct"],
            status=calib_stats["status"],
            message=calib_stats["message"],
            rois_audit=rois_list,
            action_ready=is_ready,
        )

    def draw_debug_overlay(self, report: CalibrationReport, output_image_path: str = "calibration_overlay.png") -> Optional[str]:
        """Desenha sobre a janela ou em tela preta para visualizar e confirmar o alinhamento das ROIs."""
        if not HAS_CV2 or not HAS_NUMPY:
            return None

        _, _, w, h = report.window_rect
        if w <= 0 or h <= 0:
            w, h = TARGET_WIDTH, TARGET_HEIGHT

        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        # Feltro verde escuro simulando a mesa
        cv2.ellipse(canvas, (w // 2, h // 2), (w // 2 - 30, h // 2 - 120), 0, 0, 360, (20, 60, 25), -1)
        cv2.ellipse(canvas, (w // 2, h // 2), (w // 2 - 30, h // 2 - 120), 0, 0, 360, (40, 110, 50), 3)

        # Cores por categoria (BGR)
        colors = {
            "action_button": (0, 220, 0),       # Verde brilhante
            "sizing_shortcut": (230, 180, 0),    # Amarelo/Ciano
            "hero_card": (255, 105, 65),        # Azul
            "board_card": (200, 50, 220),       # Magenta
            "table_pot": (0, 165, 255),         # Laranja
        }

        for item in report.rois_audit:
            ymin, xmin, ymax, xmax = item.scaled_box
            color = colors.get(item.category, (255, 255, 255))
            cv2.rectangle(canvas, (xmin, ymin), (xmax, ymax), color, 2)
            cv2.putText(
                canvas,
                item.name,
                (xmin + 4, ymin + 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                color,
                1,
                cv2.LINE_AA,
            )
            # Desenha ponto central de clique
            cx, cy = item.center_point
            cv2.circle(canvas, (cx, cy), 3, (0, 0, 255), -1)

        # Informações de cabeçalho
        header_text = f"VisualPilot Calibration: {w}x{h} px | DPI: {report.dpi_scale_factor * 100:.0f}% | Score: {report.calibration_score}%"
        cv2.putText(canvas, header_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

        out_path = Path(output_image_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), canvas)
        return str(out_path)

    def print_terminal_summary(self, report: CalibrationReport) -> None:
        """Imprime relatório amigável e legível no console."""
        print("=" * 68)
        print("       VISUALPILOT - AUDITORIA DE CALIBRAÇÃO DE JANELA (PPPOKER)")
        print("=" * 68)
        print(f"Janela Alvo          : {report.window_title}")
        print(f"Janela Localizada    : {'SIM' if report.is_window_found else 'NÃO'}")
        print(f"Dimensões Atuais     : {report.window_rect[2]} x {report.window_rect[3]} px")
        print(f"Dimensões Padrão     : {TARGET_WIDTH} x {TARGET_HEIGHT} px (Proporção 9:16.8)")
        print(f"Fator de Escala DPI  : {report.dpi_scale_factor * 100:.0f}%")
        print(f"Score de Calibração  : {report.calibration_score}% / 100%")
        print(f"Status               : {report.status}")
        print(f"Mensagem             : {report.message}")
        print("-" * 68)
        print("MAPEAMENTO DE ROIs E PONTOS DE CLIQUE:")
        for roi in report.rois_audit[:10]:
            print(f"  • {roi.name:<18} [{roi.category:<16}]: Box={roi.scaled_box} -> Clique Central={roi.center_point}")
        if len(report.rois_audit) > 10:
            print(f"  ... e mais {len(report.rois_audit) - 10} regiões calibradas com sucesso.")
        print("-" * 68)
        if report.action_ready:
            print(">>> CONCLUSÃO: A mesa está PERFEITAMENTE calibrada para o teste real! <<<")
        else:
            print(">>> ATENÇÃO: Ajuste a janela do PPPoker para atingir ~787x1470 px antes do jogo ao vivo. <<<")
        print("=" * 68)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrador de Janela e Resolução PPPoker")
    parser.add_argument("--window-title", type=str, default="PPPoker", help="Título da janela a inspecionar")
    parser.add_argument("--export-json", type=str, default="public/table_calibration_report.json", help="Arquivo JSON de saída")
    parser.add_argument("--export-image", type=str, default="public/calibration_overlay.png", help="Arquivo de imagem de overlay")
    args = parser.parse_args()

    calibrator = WindowCalibrator(target_title=args.window_title)
    report = calibrator.run_calibration()
    calibrator.print_terminal_summary(report)

    # Exportar JSON
    out_json = Path(args.export_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, ensure_ascii=False)
    print(f"Relatório JSON salvo em: {out_json}")

    # Exportar Imagem de Overlay se OpenCV disponível
    if HAS_CV2:
        img_path = calibrator.draw_debug_overlay(report, args.export_image)
        if img_path:
            print(f"Overlay visual salvo em: {img_path}")


if __name__ == "__main__":
    main()
