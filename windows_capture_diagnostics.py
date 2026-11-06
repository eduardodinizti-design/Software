#!/usr/bin/env python3
"""
VisualPilot - Windows Capture Diagnostics (windows_capture_diagnostics.py)
Ferramenta de diagnóstico unificada para inspeção de janelas, validação estrita
de processos (HWND, PID, executável), whitelist/blacklist, inspeção de área cliente
vs bordas, DPI, e salvamento de relatório de diagnóstico e imagem (mesmo em falha).
"""

from __future__ import annotations
import os
import sys
import json
import time
from datetime import datetime
import platform

# Ensure current directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from window_capture_engine import WindowCaptureEngine

def load_version():
    try:
        with open("version.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"version": "2.4.0", "app_name": "VisualPilot"}

def run_diagnostics(target_hwnd: int | None = None, output_dir: str = "logs/diagnostics"):
    os.makedirs(output_dir, exist_ok=True)
    engine = WindowCaptureEngine()
    version_info = load_version()

    print("=" * 60)
    print(f"VisualPilot - Diagnóstico de Captura GDI BitBlt ({datetime.now().isoformat()})")
    print(f"Sistema Operacional: {platform.system()} {platform.release()}")
    print(f"DPI Awareness Ativo: {engine.dpi_status}")
    print("=" * 60)

    # 1. Enumerate and inspect ALL windows for comprehensive diagnostics
    all_inspected_candidates = []
    accepted_candidates = []

    try:
        import win32gui
        import win32process
        import psutil
    except ImportError:
        win32gui = win32process = psutil = None

    if win32gui:
        def enum_diag_handler(hwnd, lparam):
            try:
                is_visible = win32gui.IsWindowVisible(hwnd)
                title = win32gui.GetWindowText(hwnd)
                is_iconic = win32gui.IsIconic(hwnd)
                
                rejection_reason = None
                if not is_visible:
                    rejection_reason = "REJECTED_NON_VISIBLE"
                elif is_iconic:
                    rejection_reason = "REJECTED_MINIMIZED"
                elif engine.title_substring.lower() not in title.lower() or "debug" in title.lower():
                    rejection_reason = "REJECTED_TITLE_MISMATCH"
                else:
                    is_valid, exe, pid = engine._validate_process(hwnd)
                    if not is_valid:
                        if exe in engine.BLACKLIST_EXECUTABLES:
                            rejection_reason = f"REJECTED_BLACKLIST_EXECUTABLE_{exe}"
                        else:
                            rejection_reason = f"REJECTED_INVALID_PROCESS_{exe}"
                    else:
                        try:
                            client_rect = win32gui.GetClientRect(hwnd)
                            w = client_rect[2] - client_rect[0]
                            h = client_rect[3] - client_rect[1]
                            if w <= 50 or h <= 50:
                                rejection_reason = f"REJECTED_SMALL_DIMENSIONS_{w}x{h}"
                            else:
                                screen_origin = win32gui.ClientToScreen(hwnd, (0, 0))
                                candidate_info = {
                                    "hwnd": hwnd,
                                    "pid": pid,
                                    "executable": exe,
                                    "title": title,
                                    "client_rect": client_rect,
                                    "screen_origin": screen_origin,
                                    "status": "ACCEPTED"
                                }
                                accepted_candidates.append(candidate_info)
                                all_inspected_candidates.append(candidate_info)
                                return
                        except Exception as ex:
                            rejection_reason = f"REJECTED_GEOMETRY_ERROR_{type(ex).__name__}"

                all_inspected_candidates.append({
                    "hwnd": hwnd,
                    "title": title,
                    "is_visible": is_visible,
                    "is_iconic": is_iconic,
                    "status": rejection_reason
                })
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum_diag_handler, None)
    else:
        # Mock mode on Linux
        mock_cand = {
            "hwnd": 12345,
            "pid": 100,
            "executable": "pppoker.exe",
            "title": "PPPoker Table (Mock)",
            "client_rect": (0, 0, 500, 800),
            "screen_origin": (0, 0),
            "status": "ACCEPTED"
        }
        accepted_candidates.append(mock_cand)
        all_inspected_candidates.append(mock_cand)

    print(f"\n[INSPEÇÃO] Total de janelas inspecionadas: {len(all_inspected_candidates)}")
    print(f"[INSPEÇÃO] Candidatos válidos aceitos: {len(accepted_candidates)}")
    for cand in all_inspected_candidates:
        print(f"  - HWND: {cand.get('hwnd')} | Título: {cand.get('title')} | Status: {cand.get('status')}")

    # 2. Select target window
    selected_target = None
    if target_hwnd:
        matching = [c for c in accepted_candidates if c["hwnd"] == target_hwnd]
        if matching:
            selected_target = matching[0]
        else:
            print(f"[AVISO] HWND {target_hwnd} solicitado não encontrado nos aceitos.")
    
    if not selected_target:
        if len(accepted_candidates) == 1:
            selected_target = accepted_candidates[0]
            print(f"\n[SELEÇÃO] Alvo único selecionado automaticamente: HWND {selected_target['hwnd']} ({selected_target['executable']})")
        elif len(accepted_candidates) > 1:
            print("\n[SELEÇÃO] Múltiplos alvos válidos encontrados (Janelas Ambíguas):")
            for idx, c in enumerate(accepted_candidates):
                print(f"  [{idx+1}] HWND: {c['hwnd']} | PID: {c['pid']} | Executável: {c['executable']} | Título: {c['title']} | Cliente: {c['client_rect']}")
            # Select first by default if non-interactive, or prompt
            selected_target = accepted_candidates[0]
            print(f"[SELEÇÃO] Selecionando o primeiro candidato por padrão: HWND {selected_target['hwnd']}")
        else:
            print("\n[ERRO] Nenhum candidato válido de PPPoker encontrado.")

    # 3. Perform capture attempt or record failure diagnostics
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    diag_meta = {
        "timestamp": datetime.now().isoformat(),
        "version_info": version_info,
        "platform": platform.platform(),
        "all_inspected_candidates": all_inspected_candidates,
        "accepted_candidates": accepted_candidates,
        "selected_target": selected_target,
        "capture_success": False,
        "error": None,
        "image_path": None
    }

    frame = None
    if selected_target:
        try:
            # Force engine to locate or capture specifically
            frame, capture_meta = engine.capture_frame()
            diag_meta.update(capture_meta)
            if frame is not None:
                diag_meta["capture_success"] = True
                img_filename = f"capture_success_{timestamp_str}.png"
                img_path = os.path.join(output_dir, img_filename)
                
                try:
                    import cv2
                    cv2.imwrite(img_path, frame)
                    diag_meta["image_path"] = img_path
                    print(f"\n[SUCESSO] Frame capturado com sucesso! Dimensões: {frame.shape}")
                    print(f"[SUCESSO] Imagem salva em: {img_path}")
                except Exception as ex:
                    diag_meta["error"] = f"Image Save Error: {str(ex)}"
            else:
                diag_meta["error"] = f"Capture failed with status: {capture_meta.get('status', 'UNKNOWN')}"
                print(f"\n[FALHA DE CAPTURA] Status: {capture_meta.get('status')}")
        except Exception as e:
            diag_meta["error"] = f"Exception during capture: {str(e)}"
            print(f"\n[EXCEÇÃO] Erro ao capturar frame: {e}")
    else:
        diag_meta["error"] = "WINDOW_NOT_FOUND_OR_INVALID"
        print("\n[FALHA] Nenhum alvo selecionado para captura.")

    # 4. Always save diagnostic metadata (even on failure)
    json_filename = f"capture_diagnosis_{timestamp_str}.json"
    json_path = os.path.join(output_dir, json_filename)
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(diag_meta, f, indent=2, ensure_ascii=False)
        print(f"[DIAGNÓSTICO] Relatório completo salvo em: {json_path}")
    except Exception as ex:
        print(f"[ERRO] Não foi possível salvar o JSON de diagnóstico: {ex}")

    print("=" * 60)
    return diag_meta

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VisualPilot Windows Capture Diagnostics")
    parser.add_argument("--hwnd", type=int, help="Target HWND to capture specifically", default=None)
    parser.add_argument("--output", type=str, help="Output directory for diagnostics", default="logs/diagnostics")
    args = parser.parse_args()
    
    run_diagnostics(target_hwnd=args.hwnd, output_dir=args.output)
