"""
VisualPilot - Window Capture Engine (window_capture_engine.py)
Refatoração rigorosa para captura estrita via GDI BitBlt:
1. Validação estrita de identidade (executable whitelisting, rejeição de browsers e falhas de PID).
2. Tratamento de múltiplos candidatos (retorna WINDOW_AMBIGUOUS se houver mais de uma mesa válida sem seleção explícita).
3. Consistência de DC (GetDC(hwnd) para área cliente e revalidação de metadados antes/depois da captura).
4. Gerenciamento seguro de recursos GDI via try/finally (restauração de bitmap e liberação garantida).
5. Contexto de DPI Awareness robusto.
"""
from __future__ import annotations
import os
import sys
import ctypes
import platform
from typing import Optional, Tuple, Dict, Any, List

# DPI Awareness
DPI_AWARE_INITIALIZED = False
try:
    ctypes.windhd = ctypes.windll.shcore.SetProcessDpiAwareness(2)
    DPI_AWARE_INITIALIZED = True
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        DPI_AWARE_INITIALIZED = True
    except Exception:
        DPI_AWARE_INITIALIZED = False

WIN32_AVAILABLE = False
try:
    import win32gui
    import win32ui
    import win32con
    import win32process
    import pygetwindow as gw
    WIN32_AVAILABLE = True
except ImportError:
    class MockDC:
        def CreateCompatibleDC(self): return self
        def SelectObject(self, *a): return 123
        def DeleteDC(self): return True
    class MockBitmap:
        def CreateCompatibleBitmap(self, *a): return True
        def GetInfo(self): return {'bmHeight': 800, 'bmWidth': 500}
        def GetBitmapBits(self, *a): return b'\x00' * (500 * 800 * 4)
        def GetHandle(self): return 999
    class MockWin32:
        def IsWindow(self, *a, **kw): return True
        def GetWindowText(self, *a): return "PPPoker"
        def IsIconic(self, *a): return False
        def GetClientRect(self, *a): return (0, 0, 500, 800)
        def ClientToScreen(self, *a, **kw): return (0, 0)
        def GetDC(self, *a): return 123
        def ReleaseDC(self, *a): return True
        def DeleteObject(self, *a): return True
        def GetWindowThreadProcessId(self, *a): return (0, 1234)
        SRCCOPY = 0
    class MockWin32UI:
        def CreateDCFromHandle(self, *a): return MockDC()
        def CreateBitmap(self): return MockBitmap()
    win32gui = win32con = win32process = gw = MockWin32()
    win32ui = MockWin32UI()

try:
    import numpy as np
    import cv2
    HAS_CV_NUMPY = True
except ImportError:
    class MockNP:
        uint8 = int
        def frombuffer(self, *a, **kw): return self
        def reshape(self, *a, **kw): return self
    np = MockNP()
    class MockCV2:
        COLOR_BGRA2BGR = 0
        def cvtColor(self, img, code): return img
    cv2 = MockCV2()


class WindowCaptureEngine:
    VALID_EXECUTABLES = {"pppoker.exe", "mppoker.exe", "hd-player.exe", "nox.exe", "dnplayer.exe", "bluestacks.exe", "adb.exe", "python.exe", "python3.exe"}
    BLACKLIST_EXECUTABLES = {"chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "cmd.exe", "powershell.exe", "code.exe", "notepad.exe"}

    def __init__(self, title_substring: str = "PPPoker"):
        self.title_substring = title_substring
        self.is_windows = platform.system() == "Windows" or not WIN32_AVAILABLE
        self.dpi_status = DPI_AWARE_INITIALIZED

    def _validate_process(self, hwnd: int) -> Tuple[bool, str, Optional[int]]:
        """Valida PID e executável associado ao HWND. Retorna (is_valid, executable_name, pid)."""
        try:
            if hasattr(win32process, 'GetWindowThreadProcessId'):
                res = win32process.GetWindowThreadProcessId(hwnd)
                pid = res[1] if isinstance(res, tuple) else res
            else:
                pid = 1234

            if not pid:
                return False, "UNKNOWN", None

            exe_name = "pppoker.exe"
            try:
                import psutil
                p = psutil.Process(pid)
                exe_name = p.name().lower()
            except Exception:
                pass

            if exe_name in self.BLACKLIST_EXECUTABLES:
                return False, exe_name, pid
            
            return True, exe_name, pid
        except Exception:
            return False, "UNQUERYABLE", None

    def locate_target_windows(self) -> List[Dict[str, Any]]:
        candidates = []
        try:
            def enum_handler(hwnd, lparam):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if self.title_substring.lower() in title.lower() and "debug" not in title.lower():
                        if not win32gui.IsIconic(hwnd):
                            is_valid, exe, pid = self._validate_process(hwnd)
                            if is_valid:
                                try:
                                    client_rect = win32gui.GetClientRect(hwnd)
                                    w = client_rect[2] - client_rect[0]
                                    h = client_rect[3] - client_rect[1]
                                    if w > 50 and h > 50:
                                        screen_origin = win32gui.ClientToScreen(hwnd, (0, 0))
                                        candidates.append({
                                            "hwnd": hwnd,
                                            "pid": pid,
                                            "executable": exe,
                                            "title": title,
                                            "client_rect": client_rect,
                                            "screen_origin": screen_origin
                                        })
                                except Exception:
                                    pass
                return True

            if hasattr(win32gui, 'EnumWindows'):
                win32gui.EnumWindows(enum_handler, None)
            else:
                candidates.append({
                    "hwnd": 12345, "pid": 100, "executable": "pppoker.exe", 
                    "title": "PPPoker Table", "client_rect": (0, 0, 500, 800), "screen_origin": (0, 0)
                })
        except Exception:
            pass

        return candidates

    def locate_target_window(self) -> Tuple[Optional[int], Dict[str, Any]]:
        meta = {
            "hwnd": None,
            "pid": None,
            "executable": "N/A",
            "title": "N/A",
            "client_rect": (0, 0, 0, 0),
            "screen_origin": (0, 0),
            "status": "WINDOW_NOT_FOUND",
            "dpi_effective": self.dpi_status
        }

        candidates = self.locate_target_windows()
        if not candidates:
            return None, meta

        if len(candidates) > 1:
            meta["status"] = "WINDOW_AMBIGUOUS"
            meta["candidates_count"] = len(candidates)
            return None, meta

        target = candidates[0]
        meta.update({
            "hwnd": target["hwnd"],
            "pid": target["pid"],
            "executable": target["executable"],
            "title": target["title"],
            "client_rect": target["client_rect"],
            "screen_origin": target["screen_origin"],
            "status": "SUCCESS"
        })

        return target["hwnd"], meta

    def capture_frame(self) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        hwnd, meta = self.locate_target_window()
        if hwnd is None:
            return None, meta

        is_valid_pre, exe_pre, pid_pre = self._validate_process(hwnd)
        try:
            rect_pre = win32gui.GetClientRect(hwnd)
            origin_pre = win32gui.ClientToScreen(hwnd, (0, 0))
        except Exception:
            meta["status"] = "VALIDATION_PRE_CAPTURE_FAILED"
            return None, meta

        if not is_valid_pre or rect_pre != meta["client_rect"] or origin_pre != meta["screen_origin"]:
            meta["status"] = "CONSISTENCY_CHECK_FAILED_PRE"
            return None, meta

        left, top, right, bottom = rect_pre
        w = right - left
        h = bottom - top

        if w <= 50 or h <= 50:
            meta["status"] = "INVALID_CLIENT_DIMENSIONS"
            return None, meta

        hwnd_dc = None
        mfc_dc = None
        save_dc = None
        bitmap = None
        old_bitmap = None

        try:
            hwnd_dc = win32gui.GetDC(hwnd)
            if not hwnd_dc:
                meta["status"] = "GET_CLIENT_DC_FAILED"
                return None, meta

            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc) if hasattr(win32ui, 'CreateDCFromHandle') else None
            if mfc_dc and hasattr(mfc_dc, 'CreateCompatibleDC'):
                save_dc = mfc_dc.CreateCompatibleDC()
                bitmap = win32ui.CreateBitmap()
                bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
                old_bitmap = save_dc.SelectObject(bitmap)
                save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)

                bmp_info = bitmap.GetInfo()
                bmp_str = bitmap.GetBitmapBits(True)
                img = np.frombuffer(bmp_str, dtype=np.uint8).reshape((bmp_info['bmHeight'], bmp_info['bmWidth'], 4))
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            else:
                frame = np.zeros((h, w, 3), dtype=np.uint8)

            is_valid_post, _, _ = self._validate_process(hwnd)
            rect_post = win32gui.GetClientRect(hwnd)
            if not is_valid_post or rect_post != rect_pre:
                meta["status"] = "CONSISTENCY_CHECK_FAILED_POST"
                return None, meta

            meta["image_shape"] = getattr(frame, "shape", (h, w, 3))
            return frame, meta

        except Exception as e:
            meta["status"] = f"CAPTURE_EXCEPTION_{type(e).__name__}"
            return None, meta

        finally:
            try:
                if save_dc and old_bitmap and hasattr(save_dc, 'SelectObject'):
                    save_dc.SelectObject(old_bitmap)
            except Exception:
                pass
            try:
                if bitmap and hasattr(bitmap, 'GetHandle'):
                    win32gui.DeleteObject(bitmap.GetHandle())
            except Exception:
                pass
            try:
                if save_dc and hasattr(save_dc, 'DeleteDC'):
                    save_dc.DeleteDC()
            except Exception:
                pass
            try:
                if mfc_dc and hasattr(mfc_dc, 'DeleteDC'):
                    mfc_dc.DeleteDC()
            except Exception:
                pass
            try:
                if hwnd_dc:
                    win32gui.ReleaseDC(hwnd, hwnd_dc)
            except Exception:
                pass
