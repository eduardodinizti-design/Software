"""Pega o slider de aumento: a REDE dispara na vez do heroi, e aí uma rajada RAPIDA (0.4s)
cobre a vez INTEIRA (~18s). O usuario abre o slider em QUALQUER momento da sua vez e segura;
uma foto pega. Depois diff acha o frame do slider. DPI-aware, read-only."""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capturar_na_vez import find_suprema_hwnd, grab

_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass
    import suprema_net
    hwnd = find_suprema_hwnd()
    if not hwnd:
        print("[erro] janela nao encontrada."); return 1
    print("[raise] hwnd=%s; na sua VEZ abra o slider e segure. (espera a vez, 150s)" % hex(hwnd), flush=True)
    st = {"done": False, "n": 0}

    def on_state(table):
        if table.legal_actions() and not st["done"]:
            st["done"] = True
            print("[raise] SUA VEZ detectada -> rajada rapida 18s. ABRA o slider e segure!", flush=True)
            t0 = time.time()
            while time.time() - t0 < 18:
                try:
                    grab(hwnd, os.path.join(_DIR, "rr_%02d.png" % st["n"])); st["n"] += 1
                except Exception:
                    pass
                time.sleep(0.4)
            print("[raise] rajada fim (%d fotos)." % st["n"], flush=True)

    suprema_net.run_live(bb_chips=1, on_state=on_state, seconds=150)
    print("[raise] fim. fotos=%d" % st["n"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
