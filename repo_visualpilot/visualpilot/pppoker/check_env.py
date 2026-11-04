"""VisualPilot - Verificação Prévia de Ambiente (check_init).

Valida os pré-requisitos antes do primeiro clique e antes de iniciar o bot:
1. Versão do Python (>= 3.10)
2. Ambiente virtual (.venv) ativo ou presente
3. Dependências críticas: PyAutoGUI, PyGetWindow, Pillow, Numpy
4. Diretório de logs e arquivo CSV de auditoria diário
5. Janela do PPPoker: presença, detecção se está minimizada ou bloqueada/coberta por outras janelas
6. Captura de miniatura de calibração e teste de integridade do frame para OCR
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from visualpilot.pppoker.lobby_clicker import CSV_HEADERS, AuditLogger
from visualpilot.pppoker.window_visibility_guardian import WindowVisibilityGuardian


def run_preflight_checks(
    logs_dir: Path | str = "logs",
    require_window: bool = False,
    require_visible: bool = False,
    capture_thumbnail: bool = True,
    thumbnail_path: Path | str = "public/preflight_frame.png",
    auto_restore: bool = True,
    auto_focus: bool = True
) -> dict[str, Any]:
    """Executa a esteira completa de validação pré-voo."""
    results: dict[str, Any] = {
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "all_passed": True,
        "critical_errors": [],
        "warnings": [],
        "checks": []
    }

    # 1. Checagem da Versão do Python
    py_ver = sys.version_info
    py_ver_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 10):
        results["checks"].append({
            "name": "Versão do Python",
            "status": "OK",
            "details": f"Python {py_ver_str} (>= 3.10 requerido)"
        })
    else:
        results["all_passed"] = False
        results["critical_errors"].append(f"Python {py_ver_str} é inferior à versão 3.10 recomendada.")
        results["checks"].append({
            "name": "Versão do Python",
            "status": "ERROR",
            "details": f"Python {py_ver_str} incompatível (< 3.10)"
        })

    # 2. Checagem do Ambiente Virtual (.venv)
    in_venv = (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
        or os.getenv("VIRTUAL_ENV") is not None
    )
    venv_folder = Path(".venv")
    if in_venv:
        results["checks"].append({
            "name": "Ambiente Virtual (.venv)",
            "status": "OK",
            "details": f"Ativo em: {sys.prefix}"
        })
    elif venv_folder.is_dir():
        results["checks"].append({
            "name": "Ambiente Virtual (.venv)",
            "status": "WARN",
            "details": "Pasta .venv existe mas não está ativada no shell corrente."
        })
        results["warnings"].append("Ambiente virtual .venv não está ativo neste terminal. Recomenda-se executar activate.bat.")
    else:
        results["checks"].append({
            "name": "Ambiente Virtual (.venv)",
            "status": "WARN",
            "details": "Executando no Python do sistema. Execute 'preparar.cmd' para isolamento."
        })

    # 3. Checagem de PyAutoGUI
    try:
        import pyautogui  # type: ignore
        results["checks"].append({
            "name": "Biblioteca PyAutoGUI",
            "status": "OK",
            "details": f"Instalada com sucesso (v{getattr(pyautogui, '__version__', 'ok')})"
        })
    except Exception as exc:
        results["all_passed"] = False
        results["critical_errors"].append(f"PyAutoGUI não encontrado: {exc}")
        results["checks"].append({
            "name": "Biblioteca PyAutoGUI",
            "status": "ERROR",
            "details": f"Ausente ou com falha de carregamento: {exc}"
        })

    # 4. Checagem de PyGetWindow
    try:
        import pygetwindow as gw  # type: ignore
        results["checks"].append({
            "name": "Biblioteca PyGetWindow",
            "status": "OK",
            "details": f"Instalada com sucesso (v{getattr(gw, '__version__', 'ok')})"
        })
    except Exception as exc:
        results["all_passed"] = False
        results["critical_errors"].append(f"PyGetWindow não encontrado: {exc}")
        results["checks"].append({
            "name": "Biblioteca PyGetWindow",
            "status": "ERROR",
            "details": f"Ausente ou com falha de carregamento: {exc}"
        })

    # 5. Checagem de Pillow (PIL)
    try:
        import PIL  # type: ignore
        results["checks"].append({
            "name": "Biblioteca Pillow (PIL)",
            "status": "OK",
            "details": f"Instalada com sucesso (v{getattr(PIL, '__version__', 'ok')})"
        })
    except Exception as exc:
        results["all_passed"] = False
        results["critical_errors"].append(f"Pillow não encontrado: {exc}")
        results["checks"].append({
            "name": "Biblioteca Pillow",
            "status": "ERROR",
            "details": f"Ausente: {exc}"
        })

    # 6. Checagem do Diretório de Logs e Arquivo CSV de Auditoria
    log_path = Path(logs_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger = AuditLogger(logs_dir=log_path)
    today_csv = logger.get_current_log_path()

    csv_existed = today_csv.exists()
    if not csv_existed:
        with today_csv.open("w", newline="", encoding="utf-8") as f:
            f.write(",".join(CSV_HEADERS) + "\n")
        csv_status = "INITIALIZED"
        csv_details = f"Criado e validado em: {today_csv.resolve()}"
    else:
        csv_status = "EXISTS"
        size_bytes = today_csv.stat().st_size
        csv_details = f"Existente ({size_bytes} bytes) em: {today_csv.resolve()}"

    results["checks"].append({
        "name": "Arquivo de Auditoria CSV",
        "status": "OK",
        "details": f"{today_csv.name} [{csv_status}]: {csv_details}"
    })

    # 7. Checagem Avançada da Janela PPPoker (Presença, Minimização e Bloqueio)
    guardian = WindowVisibilityGuardian(target_keyword="pppoker")
    vis_report = guardian.inspect_and_prepare_window(auto_restore=auto_restore, auto_focus=auto_focus)

    if not vis_report.is_found:
        if require_window or require_visible:
            results["all_passed"] = False
            results["critical_errors"].append(vis_report.message)
        else:
            results["warnings"].append(vis_report.message)
        results["checks"].append({
            "name": "Janela do PPPoker",
            "status": "WARN" if not (require_window or require_visible) else "ERROR",
            "details": vis_report.message
        })
    elif vis_report.is_minimized:
        msg = "Janela do PPPoker detectada, mas está MINIMIZADA. Restaure-a para o OCR capturar frames válidos."
        if require_visible:
            results["all_passed"] = False
            results["critical_errors"].append(msg)
        else:
            results["warnings"].append(msg)
        results["checks"].append({
            "name": "Janela do PPPoker",
            "status": "WARN" if not require_visible else "ERROR",
            "details": f"MINIMIZADA na barra de tarefas! {vis_report.action_taken}"
        })
    elif vis_report.is_occluded:
        msg = f"Janela do PPPoker está BLOQUEADA por outra janela: '{vis_report.blocking_window_title}'. Desobstrua a área."
        if require_visible:
            results["all_passed"] = False
            results["critical_errors"].append(msg)
        else:
            results["warnings"].append(msg)
        results["checks"].append({
            "name": "Janela do PPPoker",
            "status": "WARN" if not require_visible else "ERROR",
            "details": f"BLOQUEADA por '{vis_report.blocking_window_title}' ({vis_report.occluding_windows[0]['overlap_area_pct'] if vis_report.occluding_windows else '?'}% sobreposta)"
        })
    else:
        results["checks"].append({
            "name": "Janela do PPPoker",
            "status": "OK",
            "details": (
                f"Localizada: em ({vis_report.window_rect[0]}, {vis_report.window_rect[1]}) "
                f"{vis_report.window_rect[2]}x{vis_report.window_rect[3]} px | "
                f"1º Plano: {'Sim' if vis_report.is_foreground else 'Não'} | "
                f"Desobstruída: Sim"
            )
        })

    # 8. Captura de Miniatura e Verificação de Calibração (Preflight Frame)
    if capture_thumbnail:
        try:
            from visualpilot.pppoker.preflight_capture import run_preflight_snapshot
            snap_res = run_preflight_snapshot(
                output_png=thumbnail_path,
                output_json=Path(logs_dir) / "preflight_snapshot.json",
                require_visible=require_visible,
                force_mock=False
            )
            calib = snap_res["calibration"]
            frame_int = snap_res.get("frame_integrity", {})
            thumb_ok = snap_res["thumbnail_captured"]
            ocr_valid = frame_int.get("valid_for_ocr", False)

            if thumb_ok and ocr_valid:
                thumb_status = "OK"
                thumb_details = (
                    f"Salva em {thumbnail_path} ({calib['actual_resolution']} px, Calibração: {calib['calibration_score']}%) "
                    f"[Válida para OCR: Sim, Contraste std: {frame_int.get('variance_std', 0):.1f}]"
                )
            elif vis_report.is_minimized or vis_report.is_occluded:
                thumb_status = "WARN" if not require_visible else "ERROR"
                thumb_details = (
                    f"Captura DESCARTADA preventivamente: Janela "
                    f"{'MINIMIZADA' if vis_report.is_minimized else f'BLOQUEADA por {vis_report.blocking_window_title}'}. "
                    "Frame não gerado para evitar OCR com dados falsos."
                )
                if require_visible:
                    results["all_passed"] = False
                    results["critical_errors"].append(thumb_details)
            else:
                thumb_status = "WARN"
                thumb_details = f"Captura com alerta: {frame_int.get('details', 'Sem detalhes')}"

            results["checks"].append({
                "name": "Captura de Frame para OCR",
                "status": thumb_status,
                "details": thumb_details
            })
            results["preflight_snapshot"] = snap_res
        except Exception as exc:
            results["checks"].append({
                "name": "Captura de Frame para OCR",
                "status": "WARN",
                "details": f"Captura indisponível: {exc}"
            })

    results["visibility_report"] = vis_report.to_dict()
    return results


def print_preflight_report(results: dict[str, Any]) -> None:
    print("=" * 68)
    print(" VisualPilot - Verificação Prévia de Ambiente (check_init)")
    print("=" * 68)

    for item in results["checks"]:
        st = item["status"]
        badge = "[ OK ]" if st == "OK" else "[WARN]" if st == "WARN" else "[FALHA]"
        print(f" {badge} {item['name']:<28} -> {item['details']}")

    print("-" * 68)
    vis = results.get("visibility_report", {})
    if vis.get("is_minimized"):
        print(" [!] ALERTA CRÍTICO: Janela do PPPoker está MINIMIZADA!")
        print("     Restaure a janela na barra de tarefas antes de disparar o bot.")
    elif vis.get("is_occluded"):
        print(f" [!] ALERTA DE BLOQUEIO: Janela coberta por '{vis.get('blocking_window_title')}'!")
        print("     Feche ou arraste a janela que está por cima para garantir leitura limpa do OCR.")

    if results["all_passed"]:
        if results["warnings"]:
            print(" >> Status: AMBIENTE PRONTO COM AVISOS (Verifique os itens [WARN] acima)")
        else:
            print(" >> Status: AMBIENTE 100% PRONTO COM FRAME VÁLIDO PARA OCR!")
    else:
        print(" >> Status: ERRO ENCONTRADO! Corrija os problemas antes de iniciar:")
        for err in results["critical_errors"]:
            print(f"    * {err}")
    print("=" * 68)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Verifica ambiente, integridade da janela PPPoker (minimizada/bloqueada) e captura frame válido para OCR."
    )
    parser.add_argument("--logs-dir", type=Path, default=Path("logs"), help="Pasta de logs a verificar/criar.")
    parser.add_argument("--require-window", action="store_true", help="Falha com erro se a janela do PPPoker não estiver aberta.")
    parser.add_argument("--require-visible", "--strict-visibility", dest="require_visible", action="store_true",
                        help="Falha com código de erro se a janela estiver minimizada ou bloqueada por outra janela.")
    parser.add_argument("--no-auto-restore", dest="auto_restore", action="store_false", default=True,
                        help="Não tenta desminimizar a janela automaticamente.")
    parser.add_argument("--no-auto-focus", dest="auto_focus", action="store_false", default=True,
                        help="Não tenta trazer a janela para o primeiro plano se estiver coberta.")
    parser.add_argument("--capture-thumbnail", dest="capture_thumbnail", action="store_true", default=True, help="Captura miniatura do frame do PPPoker.")
    parser.add_argument("--no-thumbnail", dest="capture_thumbnail", action="store_false", help="Desativa a captura de miniatura.")
    parser.add_argument("--thumbnail-path", type=Path, default=Path("public/preflight_frame.png"), help="Caminho do arquivo PNG da miniatura.")
    parser.add_argument("--json", action="store_true", help="Exibe relatório em formato JSON.")
    args = parser.parse_args(argv)

    res = run_preflight_checks(
        logs_dir=args.logs_dir,
        require_window=args.require_window,
        require_visible=args.require_visible,
        capture_thumbnail=args.capture_thumbnail,
        thumbnail_path=args.thumbnail_path,
        auto_restore=args.auto_restore,
        auto_focus=args.auto_focus
    )

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print_preflight_report(res)

    return 0 if res["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
