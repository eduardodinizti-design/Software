"""Captura a tela da Suprema EXATAMENTE quando e a vez do heroi (prompt ativo), usando a
REDE como gatilho. Assim os botoes de acao (Fold/Check/Call/Raise/All-in + slider/presets)
aparecem no frame. Read-only; so observa e salva PNG. Ver SUPREMA_PROTOCOL.md."""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

_DIR = os.path.dirname(os.path.abspath(__file__))


def find_suprema_hwnd():
    u = ctypes.windll.user32
    import subprocess
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == "supremapoker.exe":
            pids.add(int(parts[1]))
    best = [None, 0]
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(h, _):
        pid = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(h) and not u.IsIconic(h):
            r = wt.RECT(); u.GetClientRect(h, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            if area > best[1]:
                best[0], best[1] = h, area
        return True
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return best[0]


def grab(hwnd, path):
    """Captura EXATA da janela (DPI-aware: coords fisicas). ImageGrab(bbox) na tela pega o
    overlay GL dos botoes. Requer a janela visivel/nao obstruida."""
    from PIL import ImageGrab
    u = ctypes.windll.user32
    r = wt.RECT(); u.GetWindowRect(hwnd, ctypes.byref(r))
    bbox = (r.left, r.top, r.right, r.bottom)
    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    img.save(path)
    return img.width, img.height


def main():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_V2
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    import suprema_net
    hwnd = find_suprema_hwnd()
    if not hwnd:
        print("[erro] janela da Suprema nao encontrada (visivel?)."); return 1
    print("[capturar_na_vez] hwnd=%s; esperando a SUA VEZ (90s). Jogue." % hex(hwnd), flush=True)
    state = {"shots": 0, "armed": False}

    def on_state(table):
        legal = table.legal_actions()
        turn = bool(legal)
        if turn and not state["armed"] and state["shots"] < 4:
            state["armed"] = True
            state["shots"] += 1
            time.sleep(0.6)             # deixa o cliente RENDERIZAR a barra de botoes
            path = os.path.join(_DIR, "suprema_vez_%d.png" % state["shots"])
            try:
                w, h = grab(hwnd, path)
                hero = (table.players.get(table.hero_seat) or {}).get('cards') if table.hero_seat else None
                print("[SHOT %d] vez=%s hero=%s -> %s (%dx%d)" % (
                    state["shots"], sorted(legal), hero, path, w, h), flush=True)
            except Exception as e:
                print("[shot erro]", e, flush=True)
        if not turn:
            state["armed"] = False      # rearma p/ a proxima vez

    suprema_net.run_live(bb_chips=1, on_state=on_state, seconds=150)
    print("[capturar_na_vez] fim. shots=%d" % state["shots"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
