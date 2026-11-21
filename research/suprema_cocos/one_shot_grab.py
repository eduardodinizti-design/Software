"""Grab INSTANTANEO (1 foto) da janela Suprema, DPI-aware. Rodar quando o slider de aumento
estiver ABERTO e segurado. Read-only."""
import ctypes
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capturar_na_vez import find_suprema_hwnd, grab

try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass
h = find_suprema_hwnd()
if not h:
    print("janela nao encontrada"); sys.exit(1)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slider_shot.png")
w, ht = grab(h, p)
print("ok %dx%d -> %s" % (w, ht, p))
