"""VisualPilot - Guardião de Visibilidade, Minimização e Bloqueio de Janelas.

Inspeciona o estado da janela do PPPoker no desktop Windows antes de qualquer captura:
1. Contrato consistente de consulta de processo com restype/argtypes Win32 e fechamento de handles em finally.
2. Identidade positiva obrigatória antes de pontuação (exige pppoker.exe ou emuladores autorizados).
3. Geometria da área cliente exata (GetClientRect + ClientToScreen).
4. Diagnósticos precisos: WINDOW_NOT_FOUND, PROCESS_ACCESS_DENIED, INVALID_IDENTITY, WINDOW_AMBIGUOUS, WINDOW_MINIMIZED, WINDOW_OCCLUDED, INVALID_GEOMETRY, BACKGROUND_CLEAR, CLEAR.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("visualpilot.window_visibility")


@dataclass
class WindowVisibilityReport:
    timestamp_iso: str
    target_title_keyword: str
    is_found: bool
    is_minimized: bool
    is_foreground: bool
    is_occluded: bool
    occlusion_status: str  # "CLEAR", "WINDOW_NOT_FOUND", "PROCESS_ACCESS_DENIED", "INVALID_IDENTITY", "WINDOW_AMBIGUOUS", "WINDOW_MINIMIZED", "WINDOW_OCCLUDED", "INVALID_GEOMETRY", "BACKGROUND_CLEAR"
    blocking_window_title: Optional[str] = None
    occluding_windows: List[Dict[str, Any]] = field(default_factory=list)
    window_rect: Tuple[int, int, int, int] = (0, 0, 0, 0)
    client_rect: Tuple[int, int, int, int] = (0, 0, 0, 0)
    process_info: Dict[str, Any] = field(default_factory=dict)
    frame_valid_for_ocr: bool = False
    frame_variance_std: float = 0.0
    action_taken: str = "NONE"
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_iso": self.timestamp_iso,
            "target_title_keyword": self.target_title_keyword,
            "is_found": self.is_found,
            "is_minimized": self.is_minimized,
            "is_foreground": self.is_foreground,
            "is_occluded": self.is_occluded,
            "occlusion_status": self.occlusion_status,
            "blocking_window_title": self.blocking_window_title,
            "occluding_windows": self.occluding_windows,
            "window_rect": {
                "left": self.window_rect[0],
                "top": self.window_rect[1],
                "width": self.window_rect[2],
                "height": self.window_rect[3]
            },
            "client_rect": {
                "left": self.client_rect[0],
                "top": self.client_rect[1],
                "width": self.client_rect[2],
                "height": self.client_rect[3]
            },
            "process_info": self.process_info,
            "frame_valid_for_ocr": self.frame_valid_for_ocr,
            "frame_variance_std": round(self.frame_variance_std, 2),
            "action_taken": self.action_taken,
            "message": self.message
        }


def rect_intersection_area(
    r1: Tuple[int, int, int, int],
    r2: Tuple[int, int, int, int]
) -> int:
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2
    r1_right, r1_bottom = x1 + w1, y1 + h1
    r2_right, r2_bottom = x2 + w2, y2 + h2

    inter_left = max(x1, x2)
    inter_top = max(y1, y2)
    inter_right = min(r1_right, r2_right)
    inter_bottom = min(r1_bottom, r2_bottom)

    if inter_right > inter_left and inter_bottom > inter_top:
        return (inter_right - inter_left) * (inter_bottom - inter_top)
    return 0


def validate_captured_frame_integrity(frame_or_path: Any, min_variance_std: float = 8.0) -> bool:
    """Função utilitária em nível de módulo para validação de integridade de frame."""
    try:
        import numpy as np
        if frame_or_path is None:
            return False
        if isinstance(frame_or_path, np.ndarray):
            if frame_or_path.size == 0:
                return False
            return float(np.std(frame_or_path)) >= min_variance_std
    except Exception:
        pass
    return True


def get_process_info_for_hwnd(hwnd: int) -> Dict[str, Any]:
    """Consulta segura de processo com contrato estrito e fechamento de handles em finally."""
    if sys.platform != "win32":
        return {
            "pid": 0,
            "executable": "simulation.exe",
            "executable_path": "simulation.exe",
            "is_valid": True,
            "is_forbidden": False,
            "error": None
        }

    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    k32 = ctypes.windll.kernel32

    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD

    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE

    k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL

    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return {
            "pid": 0,
            "executable": "",
            "executable_path": "",
            "is_valid": False,
            "is_forbidden": False,
            "error": "PID nulo obtido via GetWindowThreadProcessId"
        }

    h_proc = None
    try:
        h_proc = k32.OpenProcess(0x1000, False, pid.value) # PROCESS_QUERY_LIMITED_INFORMATION
        if not h_proc:
            err_code = k32.GetLastError()
            return {
                "pid": int(pid.value),
                "executable": "",
                "executable_path": "",
                "is_valid": False,
                "is_forbidden": False,
                "error": f"PROCESS_ACCESS_DENIED (OpenProcess falhou com código {err_code})"
            }

        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        success = k32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size))
        if not success:
            err_code = k32.GetLastError()
            return {
                "pid": int(pid.value),
                "executable": "",
                "executable_path": "",
                "is_valid": False,
                "is_forbidden": False,
                "error": f"QueryFullProcessImageNameW falhou (código {err_code})"
            }

        exe_path = buf.value
        exe_name = Path(exe_path).name.lower() if exe_path else ""

        forbidden = {"chrome.exe", "msedge.exe", "firefox.exe", "explorer.exe", "cmd.exe", "powershell.exe", "code.exe", "devenv.exe"}
        authorized = {"pppoker.exe", "ppclient.exe"}

        is_forbidden = exe_name in forbidden
        is_authorized = exe_name in authorized

        is_valid = is_authorized and not is_forbidden
        error_msg = None if is_valid else (f"INVALID_IDENTITY: Processo não autorizado '{exe_name}'" if not is_forbidden else f"PROCESS_FORBIDDEN: Navegador/Sistema '{exe_name}'")

        return {
            "pid": int(pid.value),
            "executable_path": exe_path,
            "executable": exe_name,
            "is_valid": is_valid,
            "is_forbidden": is_forbidden,
            "error": error_msg
        }
    except Exception as exc:
        return {
            "pid": int(pid.value),
            "executable": "",
            "executable_path": "",
            "is_valid": False,
            "is_forbidden": False,
            "error": f"EXC_PROCESS_QUERY: {exc}"
        }
    finally:
        if h_proc:
            try:
                k32.CloseHandle(h_proc)
            except Exception:
                pass


class WindowVisibilityGuardian:
    """Guardião com identificação positiva obrigatória antes de pontuação."""

    def __init__(self, target_keyword: str = "pppoker"):
        self.target_keyword = target_keyword.lower()

    def inspect_and_prepare_window(
        self,
        auto_restore: bool = False,
        auto_focus: bool = False,
        max_overlap_tolerance_pct: float = 5.0
    ) -> WindowVisibilityReport:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if sys.platform != "win32":
            return WindowVisibilityReport(
                timestamp_iso=now_iso,
                target_title_keyword=self.target_keyword,
                is_found=True,
                is_minimized=False,
                is_foreground=True,
                is_occluded=False,
                occlusion_status="CLEAR",
                blocking_window_title=None,
                occluding_windows=[],
                window_rect=(100, 50, 787, 1470),
                client_rect=(100, 50, 787, 1470),
                process_info={"pid": 1234, "executable": "pppoker.exe", "is_valid": True, "is_forbidden": False, "error": None},
                frame_valid_for_ocr=True,
                frame_variance_std=45.2,
                action_taken="SIMULATED_HEADLESS",
                message="Ambiente não-Windows (simulado)."
            )

        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32

        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        u.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.IsIconic.argtypes = [wintypes.HWND]
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]

        z_order_windows: List[Dict[str, Any]] = []

        @callback_type
        def enum_windows_proc(hwnd, _):
            if not u.IsWindowVisible(hwnd):
                return True
            length = u.GetWindowTextLengthW(hwnd)
            title_buf = ctypes.create_unicode_buffer(length + 1)
            u.GetWindowTextW(hwnd, title_buf, length + 1)
            title = title_buf.value

            is_iconic = bool(u.IsIconic(hwnd))

            rect = wintypes.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            if w > 10000 or h > 10000 or w < 50 or h < 50:
                return True

            pinfo = get_process_info_for_hwnd(hwnd)
            t_lower = title.lower()
            has_table_kw = any(k in t_lower for k in ["mtt", "nlh", "plo", "pko", "sat", "sng", "spin", "freeze", "stack", "4-max", "6-max", "hold'em", "omaha", "mesa", "table"])
            z_order_windows.append({
                "hwnd": int(hwnd),
                "title": title,
                "is_iconic": is_iconic,
                "process_info": pinfo,
                "box": (int(rect.left), int(rect.top), int(w), int(h))
            })
            return True

        u.EnumWindows(enum_windows_proc, 0)

        candidate_list = []
        for idx, win in enumerate(z_order_windows):
            if not win["process_info"].get("is_valid", False) or win["process_info"].get("is_forbidden", False):
                continue
            title = win["title"] or ""
            t_lower = title.lower()

            sc = 0.0
            has_table_kw = any(k in t_lower for k in ["mtt", "nlh", "plo", "pko", "sat", "sng", "spin", "freeze", "stack", "4-max", "6-max", "hold'em", "omaha", "mesa", "table", "v228", "poker"])
            is_pppoker_app = ("pppoker" in t_lower) or ("v228" in t_lower)

            if has_table_kw:
                sc += 600.0
            elif is_pppoker_app:
                sc += 400.0
            else:
                sc += 200.0 # Processo já é autorizado (pppoker.exe / emulador), logo pontua com segurança

            w, h = win["box"][2], win["box"][3]
            ratio = w / float(max(1, h))
            if 0.25 <= ratio <= 4.0:
                sc += 100.0

            if not win["is_iconic"]:
                sc += 50.0

            candidate_list.append((sc, idx, win))

        if not candidate_list:
            return WindowVisibilityReport(
                timestamp_iso=now_iso,
                target_title_keyword=self.target_keyword,
                is_found=False,
                is_minimized=False,
                is_foreground=False,
                is_occluded=False,
                occlusion_status="WINDOW_NOT_FOUND",
                message="Nenhum processo autorizado do PPPoker foi encontrado (WINDOW_NOT_FOUND)."
            )

        candidate_list.sort(key=lambda x: x[0], reverse=True)
        if len(candidate_list) > 1 and (candidate_list[0][0] - candidate_list[1][0] < 15.0):
            titles_amb = [c[2]["title"] for c in candidate_list[:3]]
            return WindowVisibilityReport(
                timestamp_iso=now_iso,
                target_title_keyword=self.target_keyword,
                is_found=True,
                is_minimized=False,
                is_foreground=False,
                is_occluded=False,
                occlusion_status="WINDOW_AMBIGUOUS",
                message=f"Múltiplas janelas candidatas com pontuação equivalente (WINDOW_AMBIGUOUS): {titles_amb}."
            )

        target = candidate_list[0][2]
        hwnd = target["hwnd"]
        is_iconic = target["is_iconic"]
        target_z_index = candidate_list[0][1]

        if is_iconic:
            return WindowVisibilityReport(
                timestamp_iso=now_iso,
                target_title_keyword=self.target_keyword,
                is_found=True,
                is_minimized=True,
                is_foreground=False,
                is_occluded=True,
                occlusion_status="WINDOW_MINIMIZED",
                message=f"A janela '{target['title']}' está minimizada (WINDOW_MINIMIZED)."
            )

        # Obter área cliente precisa
        client_rect = wintypes.RECT()
        if not u.GetClientRect(hwnd, ctypes.byref(client_rect)):
            raise OSError("GetClientRect failed")
        pt_tl = wintypes.POINT(client_rect.left, client_rect.top)
        pt_br = wintypes.POINT(client_rect.right, client_rect.bottom)
        if not u.ClientToScreen(hwnd, ctypes.byref(pt_tl)):
            raise OSError("ClientToScreen(top-left) failed")
        if not u.ClientToScreen(hwnd, ctypes.byref(pt_br)):
            raise OSError("ClientToScreen(bottom-right) failed")
        client_w = pt_br.x - pt_tl.x
        client_h = pt_br.y - pt_tl.y
        client_box = (int(pt_tl.x), int(pt_tl.y), int(client_w), int(client_h))

        if client_w <= 100 or client_h <= 100:
            return WindowVisibilityReport(
                timestamp_iso=now_iso,
                target_title_keyword=self.target_keyword,
                is_found=True,
                is_minimized=False,
                is_foreground=False,
                is_occluded=False,
                occlusion_status="INVALID_GEOMETRY",
                message=f"Área cliente com geometria inválida ({client_w}x{client_h} px) [INVALID_GEOMETRY]."
            )

        # Verificação de Oclusão (Z-Order) antes de declarar CLEAR ou BACKGROUND_CLEAR
        foreground_hwnd = int(u.GetForegroundWindow())
        is_foreground = (foreground_hwnd == hwnd)

        occluded = False
        blocking_title = None
        if not is_foreground:
            # Verifica se alguma janela visível acima está sobrepondo a área cliente
            for win in z_order_windows[:target_z_index]:
                if win["hwnd"] == hwnd or win["is_iconic"]:
                    continue
                overlap = rect_intersection_area(client_box, win["box"])
                if overlap > 0:
                    overlap_pct = (overlap / float(client_w * client_h)) * 100.0
                    if overlap_pct >= max_overlap_tolerance_pct:
                        occluded = True
                        blocking_title = win["title"] or f"PID {win['process_info']['pid']}"
                        break

        status = "CLEAR"
        if occluded:
            status = "WINDOW_OCCLUDED"
        elif not is_foreground:
            status = "BACKGROUND_CLEAR"

        return WindowVisibilityReport(
            timestamp_iso=now_iso,
            target_title_keyword=self.target_keyword,
            is_found=True,
            is_minimized=False,
            is_foreground=is_foreground,
            is_occluded=occluded,
            occlusion_status=status,
            blocking_window_title=blocking_title,
            window_rect=target["box"],
            client_rect=client_box,
            process_info=target["process_info"],
            frame_valid_for_ocr=not occluded,
            action_taken="NONE",
            message=f"Janela '{target['title']}' validada (HWND: {hwnd}, PID: {target['process_info']['pid']}, Exe: {target['process_info']['executable']}). Status: {status}."
        )

    def validate_captured_frame_integrity(self, frame_or_path: Any, min_variance_std: float = 8.0) -> bool:
        if frame_or_path is None:
            return False
        try:
            import numpy as np
            if isinstance(frame_or_path, np.ndarray):
                if frame_or_path.size == 0:
                    return False
                return float(np.std(frame_or_path)) >= min_variance_std
        except Exception:
            pass
        return True
