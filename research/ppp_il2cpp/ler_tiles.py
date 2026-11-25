"""Testa ler_tiles.js: lê o retângulo do tile de cada mesa (TableUIPanel) e converte p/
coords de TELA do Windows (soma o client da janela, inverte o Y do Unity). READ-ONLY."""
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
_HERE = os.path.dirname(os.path.abspath(__file__))


def _fmt(r):
    return f"(x={r[0]:.0f} y={r[1]:.0f} w={r[2]:.0f} h={r[3]:.0f})" if r else "None"


def _fmtpt(p):
    return f"({p[0]:.0f},{p[1]:.0f})" if p else "None"


def client_origin_and_height():
    """Origem (tela) do CLIENT da janela do PPPoker + altura do client (p/ inverter o Y)."""
    u = ctypes.windll.user32
    import psutil
    pids = {p.pid for p in psutil.process_iter(["name"]) if "pppoker" in (p.info["name"] or "").lower()}
    best = [None, 0]
    EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _l):
        pid = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(h):
            r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
            a = (r.right - r.left) * (r.bottom - r.top)
            if a > best[1]:
                best[0] = h; best[1] = a
        return True
    u.EnumWindows(EP(cb), 0)
    if not best[0]:
        return None
    rc = wintypes.RECT(); u.GetClientRect(best[0], ctypes.byref(rc))
    pt = wintypes.POINT(0, 0); u.ClientToScreen(best[0], ctypes.byref(pt))
    return {"x": pt.x, "y": pt.y, "w": rc.right, "h": rc.bottom}


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "pppoker.exe"]
    if not procs:
        print("[tiles] PPPoker fechado."); return 1
    session = dev.attach(procs[0].pid)
    with open(os.path.join(_HERE, "ler_tiles.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())
    co = client_origin_and_height()

    shown = {"done": False}

    def to_screen(rect, rw, rh):
        """Rect Unity [x0,y0,x1,y1] (render, Y p/ cima) -> (x,y,w,h) em pixels de tela (client)."""
        if not rect or not co or not rw or not rh:
            return None
        sxk, syk = co["w"] / rw, co["h"] / rh
        x0, y0, x1, y1 = rect
        X = co["x"] + x0 * sxk
        Y = co["y"] + (co["h"] - y1 * syk)      # inverte Y
        return (X, Y, (x1 - x0) * sxk, (y1 - y0) * syk)

    def on_msg(m, _d):
        if m.get("type") == "error":
            print("[js-erro]", m.get("stack") or m.get("description"), flush=True); return
        if m.get("type") != "send":
            return
        res = m.get("payload")
        if not isinstance(res, dict) or shown["done"]:
            return
        def pt(p, rw, rh):
            if not p or not co or not rw or not rh:
                return None
            return (co["x"] + p[0] * (co["w"] / rw), co["y"] + (co["h"] - p[1] * (co["h"] / rh)))

        rw, rh = res.get("screenW"), res.get("screenH")
        print(f"[tiles] render {rw}x{rh} · client {co}", flush=True)
        if res.get("dump"):
            for cls, flds in res["dump"].items():
                if flds:
                    print(f"   == {cls} campos ==")
                    for fld in flds:
                        print("     ", fld, flush=True)
        for i, p in enumerate(res.get("pages", [])):
            print(f"   PAGE[{i}] roomid={p.get('roomid')} rootpos={_fmtpt(pt(p.get('rootpos'), rw, rh))} "
                  f"framepos={_fmtpt(pt(p.get('framepos'), rw, rh))}", flush=True)
        def cam_screen(pr):
            # pixelRect [x,y,w,h] em pixels de render (Y p/ cima) -> (x,y,w,h) de tela (client)
            if not pr or not co or not rw or not rh:
                return None
            sxk, syk = co["w"] / rw, co["h"] / rh
            x, y, w, h = pr
            return (co["x"] + x * sxk, co["y"] + (co["h"] - (y + h) * syk), w * sxk, h * syk)

        print("   == CAMERAS (viewport na tela) ==")
        for cm in res.get("cams", []):
            sr = cam_screen(cm.get("rect"))
            print(f"     cam '{cm.get('name')}' depth={cm.get('depth')} viewport={_fmt(sr)}", flush=True)
        shown["done"] = True   # imprime 1 vez

    script.on("message", on_msg)
    print("[tiles] client da janela:", co, flush=True)
    script.load()
    try:
        time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 20.0)
    finally:
        try:
            script.unload()
        except Exception:
            pass
        try:
            session.detach()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
