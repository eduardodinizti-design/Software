"""
VisualPilot - Window Stream (Passo 3: Capturador sem Tela Cinza)
Captura estritamente o canvas interno da janela vertical do PPPoker via win32gui.GetClientRect e BitBlt (~1-3ms).
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional, Tuple, List
import numpy as np
import cv2

try:
    import win32gui
    import win32ui
    import win32con
    import pygetwindow as gw
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

def capture_pppoker_window() -> Optional[np.ndarray]:
    """Captura apenas a mesa de jogo real pelo handle da janela, evitando tela cinza ou desktop inteiro."""
    if not WIN32_AVAILABLE:
        return None

    try:
        wins = [w for w in gw.getWindowsWithTitle("PPPoker") if w.visible and "debug" not in w.title.lower()]
        
        # Filtra para pegar a janela vertical da mesa (evita janelas de tela inteira ou lobby horizontal)
        target = None
        for w in wins:
            if w.width < 1200 and w.height > w.width:
                target = w
                break
                
        if not target:
            if wins:
                target = min(wins, key=lambda w: w.width * w.height)
            else:
                return None

        hwnd = target._hWnd
        if not win32gui.IsWindow(hwnd):
            return None

        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        w = right - left
        h = bottom - top

        if w <= 0 or h <= 0:
            return None

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bitmap)

        # BitBlt direto da janela (leva de 1 a 3ms)
        save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)

        bmp_info = bitmap.GetInfo()
        bmp_str = bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmp_str, dtype=np.uint8).reshape((bmp_info['bmHeight'], bmp_info['bmWidth'], 4))

        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception:
        return None


if __name__ == "__main__":
    print("[*] Teste do Window Stream iniciado. Pressione 'q' para sair.")
    
    cv2.namedWindow("VisualPilot - Window Stream", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("VisualPilot - Window Stream", 420, 720)

    while True:
        t0 = time.perf_counter()
        frame = capture_pppoker_window()

        if frame is None:
            time.sleep(0.1)
            continue

        dt_ms = (time.perf_counter() - t0) * 1000
        fps = 1000.0 / max(0.1, dt_ms)

        cv2.putText(frame, f"Capture: {dt_ms:.1f}ms | {fps:.1f} FPS", (10, 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow("VisualPilot - Window Stream", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
