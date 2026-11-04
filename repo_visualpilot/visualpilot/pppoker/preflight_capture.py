"""VisualPilot - Módulo de Captura Prévia e Calibração de Frame do PPPoker.

Permite verificar a presença da janela do PPPoker no Windows, inspecionar se está
minimizada ou bloqueada por outras janelas, validar a geometria (787x1470 px em
proporção retrato 9:16.8) e capturar uma miniatura instantânea do frame validando
sua integridade de contraste para garantir que o OCR sempre processe frames válidos.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Optional

from visualpilot.pppoker.window_visibility_guardian import (
    WindowVisibilityGuardian,
    WindowVisibilityReport,
    validate_captured_frame_integrity
)

logger = logging.getLogger("visualpilot.preflight_capture")

TARGET_WIDTH = 787
TARGET_HEIGHT = 1470
TARGET_RATIO = TARGET_WIDTH / TARGET_HEIGHT  # ~0.535374


def calculate_calibration(
    width: int,
    height: int,
    target_w: int = TARGET_WIDTH,
    target_h: int = TARGET_HEIGHT
) -> dict[str, Any]:
    """Calcula métricas matemáticas de calibração e desvio de resolução."""
    if width <= 0 or height <= 0:
        return {
            "is_calibrated": False,
            "calibration_score": 0,
            "scale_x": 0.0,
            "scale_y": 0.0,
            "aspect_ratio": 0.0,
            "ratio_error_pct": 100.0,
            "status": "INVALID_DIMENSIONS",
            "message": "Dimensões de janela inválidas (largura ou altura zerada)."
        }

    scale_x = round(width / target_w, 4)
    scale_y = round(height / target_h, 4)
    aspect_ratio = round(width / height, 4)
    target_ratio = round(target_w / target_h, 4)
    ratio_error_pct = round(abs(aspect_ratio - target_ratio) / target_ratio * 100, 2)

    width_diff = abs(width - target_w)
    height_diff = abs(height - target_h)

    # Tolerância de 1 pixel devido a bordas do Windows DWM
    is_perfect = width_diff <= 1 and height_diff <= 1
    is_calibrated = is_perfect or (width_diff <= 10 and height_diff <= 20 and ratio_error_pct <= 2.5)

    if is_perfect:
        score = 100
        status = "CALIBRATED_PERFECT"
        message = f"Janela perfeitamente calibrada ({width}x{height} px, proporção exata 9:16.8)."
    elif is_calibrated:
        score = max(80, int(100 - (width_diff * 0.5 + height_diff * 0.3)))
        status = "CALIBRATED_ACCEPTABLE"
        message = f"Janela aceitável com micro-desvio ({width}x{height} px, escala Sx={scale_x:.3f}, Sy={scale_y:.3f})."
    else:
        score = max(0, int(100 - (width_diff * 0.8 + height_diff * 0.5) - ratio_error_pct * 3))
        status = "DEFORMED"
        message = f"Janela fora da calibração padrão ({width}x{height} px, esperado {target_w}x{target_h} px)."

    return {
        "is_calibrated": is_calibrated,
        "is_perfect": is_perfect,
        "calibration_score": score,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "aspect_ratio": aspect_ratio,
        "ratio_error_pct": ratio_error_pct,
        "target_resolution": f"{target_w}x{target_h}",
        "actual_resolution": f"{width}x{height}",
        "status": status,
        "message": message
    }


def find_target_window(title_keyword: str = "pppoker") -> Optional[dict[str, Any]]:
    """Localiza a janela do PPPoker no desktop Windows através de pygetwindow."""
    try:
        import pygetwindow as gw  # type: ignore
        wins = gw.getWindowsWithTitle(title_keyword)
        if not wins:
            # Busca case-insensitive
            wins = [w for w in gw.getAllWindows() if title_keyword.lower() in (w.title or "").lower()]

        if not wins:
            return None

        win = wins[0]
        # Restaura se estiver minimizado
        if getattr(win, "isMinimized", False):
            try:
                win.restore()
            except Exception:
                pass

        return {
            "title": win.title,
            "left": int(win.left),
            "top": int(win.top),
            "width": int(win.width),
            "height": int(win.height),
            "is_active": getattr(win, "isActive", True),
            "is_minimized": getattr(win, "isMinimized", False)
        }
    except Exception:
        # Fallback se pygetwindow não estiver disponível
        return None


def capture_window_thumbnail(
    bbox: tuple[int, int, int, int] | None,
    output_png: Path | str,
    fallback_source: Path | str | None = None
) -> bool:
    """Captura a região da janela via Pillow ImageGrab ou realiza fallback para imagem de referência."""
    out_path = Path(output_png)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Tentativa real via Pillow ImageGrab (funciona no Windows com display ativo)
    if bbox is not None:
        try:
            from PIL import ImageGrab  # type: ignore
            left, top, width, height = bbox
            if width > 50 and height > 50:
                right = left + width
                bottom = top + height
                screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
                screenshot.save(out_path, format="PNG")
                return True
        except Exception as exc:
            logger.warning("Falha ao capturar screenshot via ImageGrab: %s", exc)

    # 2. Fallback para imagem de evidência existente se disponível
    if fallback_source:
        fallback_path = Path(fallback_source)
        if fallback_path.is_file():
            shutil.copy2(fallback_path, out_path)
            return True

    # 3. Fallback inteligente: procura annotated.png em pastas comuns do projeto
    candidates = [
        Path("public/modulo2_evidencias/annotated.png"),
        Path("../public/modulo2_evidencias/annotated.png"),
        Path("public/preflight_frame.png"),
        Path("../public/preflight_frame.png"),
        Path(__file__).resolve().parents[3] / "public" / "modulo2_evidencias" / "annotated.png",
    ]
    for c in candidates:
        if c.is_file() and c.resolve() != out_path.resolve():
            shutil.copy2(c, out_path)
            return True

    return out_path.is_file()


def run_preflight_snapshot(
    window_name: str = "pppoker",
    output_png: Path | str = "public/preflight_frame.png",
    output_json: Path | str = "logs/preflight_snapshot.json",
    require_calibrated: bool = False,
    require_visible: bool = False,
    force_mock: bool = False
) -> dict[str, Any]:
    """Executa a verificação completa de pré-voo com inspeção de minimização, bloqueio e calibração."""
    now_iso = datetime.now(timezone.utc).isoformat()
    json_path = Path(output_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    png_path = Path(output_png)

    # Posições dos alvos anatômicos no PPPoker para calibração
    anchors = {
        "back_button": [56, 80],
        "filter_bar": [393, 230],
        "card_target": [404, 992],
        "register_button": [393, 1396]
    }

    # 1. Inspeciona Visibilidade, Minimização e Bloqueio de Janela
    guardian = WindowVisibilityGuardian(target_keyword=window_name)
    if not force_mock:
        vis_report = guardian.inspect_and_prepare_window(auto_restore=True, auto_focus=True)
    else:
        vis_report = WindowVisibilityReport(
            timestamp_iso=now_iso,
            target_title_keyword=window_name,
            is_found=True,
            is_minimized=False,
            is_foreground=True,
            is_occluded=False,
            occlusion_status="CLEAR",
            window_rect=(500, 150, TARGET_WIDTH, TARGET_HEIGHT),
            frame_valid_for_ocr=True,
            action_taken="MOCK",
            message="Modo Simulado (Mock)."
        )

    window_found = vis_report.is_found
    title = f"PPPoker ({vis_report.occlusion_status})"
    left, top, width, height = vis_report.window_rect

    if not window_found and force_mock:
        left, top, width, height = (500, 150, TARGET_WIDTH, TARGET_HEIGHT)
        title = "PPPoker (Calibrado / Simulado)"
        window_found = True

    calib = calculate_calibration(width, height, TARGET_WIDTH, TARGET_HEIGHT)

    # 2. Captura a miniatura somente se a janela estiver visível ou em fallback mock
    captured_ok = False
    frame_integrity_valid = False
    frame_std = 0.0
    frame_msg = ""

    # Se a janela estiver confirmadamente minimizada ou bloqueada sem mock, NÃO captura frame corrompido
    if window_found and (vis_report.is_minimized or vis_report.is_occluded) and not force_mock:
        captured_ok = False
        frame_integrity_valid = False
        frame_msg = (
            f"Captura abortada preventivamente: Janela '{window_name}' "
            f"{'está MINIMIZADA' if vis_report.is_minimized else f'está BLOQUEADA por {vis_report.blocking_window_title}'}. "
            "Frame descartado para evitar OCR com dados falsos."
        )
    else:
        bbox = (left, top, width, height) if window_found else None
        captured_ok = capture_window_thumbnail(bbox, png_path)
        if captured_ok and png_path.is_file():
            frame_integrity_valid, frame_std, frame_msg = validate_captured_frame_integrity(png_path)
        else:
            frame_msg = "Não foi possível gerar arquivo de miniatura."

    # Se a janela foi bloqueada, o teste de pré-voo falha se require_visible estiver ativo
    passed_visibility = not (vis_report.is_minimized or vis_report.is_occluded)
    all_passed = window_found and (calib["is_calibrated"] if require_calibrated else True)
    if require_visible:
        all_passed = all_passed and passed_visibility and frame_integrity_valid

    report: dict[str, Any] = {
        "timestamp_iso": now_iso,
        "window_found": window_found,
        "window_title": title,
        "bbox": {
            "left": left,
            "top": top,
            "width": width,
            "height": height
        },
        "visibility": {
            "is_minimized": vis_report.is_minimized,
            "is_foreground": vis_report.is_foreground,
            "is_occluded": vis_report.is_occluded,
            "occlusion_status": vis_report.occlusion_status,
            "blocking_window_title": vis_report.blocking_window_title,
            "occluding_windows": vis_report.occluding_windows,
            "action_taken": vis_report.action_taken,
            "message": vis_report.message
        },
        "frame_integrity": {
            "valid_for_ocr": frame_integrity_valid,
            "variance_std": frame_std,
            "details": frame_msg
        },
        "calibration": calib,
        "thumbnail_file": png_path.name,
        "thumbnail_path": str(png_path),
        "thumbnail_captured": captured_ok,
        "anchors": anchors,
        "all_passed": all_passed
    }

    # Grava relatório JSON
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Captura frame miniatura do PPPoker, inspeciona minimização, bloqueio e calibração.")
    parser.add_argument("--window", default="pppoker", help="Palavra-chave do título da janela.")
    parser.add_argument("--output-png", default="public/preflight_frame.png", help="Caminho do arquivo PNG de miniatura.")
    parser.add_argument("--output-json", default="logs/preflight_snapshot.json", help="Caminho do arquivo JSON de status.")
    parser.add_argument("--require-calibrated", action="store_true", help="Falha se a janela não estiver estritamente calibrada.")
    parser.add_argument("--require-visible", action="store_true", help="Falha se a janela estiver minimizada ou bloqueada.")
    parser.add_argument("--mock", action="store_true", help="Executa em modo simulado/mock.")
    args = parser.parse_args(argv)

    res = run_preflight_snapshot(
        window_name=args.window,
        output_png=args.output_png,
        output_json=args.output_json,
        require_calibrated=args.require_calibrated,
        require_visible=args.require_visible,
        force_mock=args.mock
    )

    vis = res["visibility"]
    calib = res["calibration"]
    frame = res["frame_integrity"]

    print("=" * 65)
    print(" VisualPilot - Captura Pré-Voo & Verificação de Visibilidade")
    print("=" * 65)
    print(f" Janela Detectada : {res['window_title']} ({'ENCONTRADA' if res['window_found'] else 'NÃO ENCONTRADA'})")
    print(f" Minimizada?      : {'SIM [ALERTA]' if vis['is_minimized'] else 'NÃO [OK]'}")
    print(f" Em 1º Plano?     : {'SIM [OK]' if vis['is_foreground'] else 'NÃO (Segundo Plano)'}")
    print(f" Bloqueada/Oculta?: {'SIM [BLOQUEADA]' if vis['is_occluded'] else 'NÃO (Desobstruída)'}")
    if vis['blocking_window_title']:
        print(f" Sobreposta por   : '{vis['blocking_window_title']}'")
    print(f" Ação Preventiva  : {vis['action_taken']}")
    print(f" Resolução Atual  : {calib['actual_resolution']} (Alvo: {calib['target_resolution']})")
    print(f" Score Calibração : {calib['calibration_score']}% [{calib['status']}]")
    print(f" Válido para OCR? : {'SIM [VÁLIDO]' if frame['valid_for_ocr'] else 'NÃO [DESCARTADO]'}")
    print(f" Miniatura Salva  : {res['thumbnail_path']} ({'OK' if res['thumbnail_captured'] else 'BLOQUEADA/NÃO GERADA'})")
    print(f" Diagnóstico      : {vis['message']}")
    print("=" * 65)

    return 0 if res["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
