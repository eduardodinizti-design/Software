"""
VisualPilot - window_stream.py (Capturador Rigoroso sem Tela Cinza ou Multi-Monitor)
Filtra estritamente a janela vertical do PPPoker, evitando coordenadas negativas ou desktop estendido.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional, Tuple
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
    """Captura exclusivamente a janela vertical da mesa do PPPoker, evitando multi-monitores e tela cinza."""
    if not WIN32_AVAILABLE:
        return None

    try:
        # Encontrar janelas visíveis contendo "PPPoker" ou "MPPoker"
        wins = [w for w in gw.getWindowsWithTitle("PPPoker") if w.visible and "debug" not in w.title.lower()]
        if not wins:
            wins = [w for w in gw.getWindowsWithTitle("MPPoker") if w.visible and "debug" not in w.title.lower()]

        if not wins:
            return None

        # Filtrar estritamente para encontrar a janela vertical da mesa (width < 1000 e height > width)
        target = None
        for w in wins:
            if 200 < w.width < 1000 and w.height > w.width and w.left >= 0 and w.top >= 0:
                target = w
                break

        # Fallback se nenhuma estritamente vertical for encontrada
        if not target:
            valid_wins = [w for w in wins if w.width > 150 and w.height > 150 and w.left >= 0 and w.top >= 0]
            if not valid_wins:
                return None
            target = min(valid_wins, key=lambda w: w.width * w.height)

        hwnd = target._hWnd
        if not win32gui.IsWindow(hwnd):
            return None

        # Obter área cliente exata da janela
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        w = right - left
        h = bottom - top

        if w <= 100 or h <= 100 or w > 1200:
            return None

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bitmap)

        # BitBlt direto da janela (1 a 3ms)
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
