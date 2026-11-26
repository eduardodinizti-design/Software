"""Produtor de logs/tiles.json (binding multi-mesa DATA-DRIVEN, PPPoker v228). READ-ONLY.

Anexa no PPPoker (NVT_PPP_PID fixa o processo) e, em loop, chama readTiles2() do ler_tiles.js —
FloatingWindowController._tableId@52 (= roomid, confirmado = gameid do estado_mesa) + _rectTransform@64
(cantos de MUNDO). Grava {roomid: [wx0,wy0,wx1,wy1]} dos tiles VÁLIDOS (tableId>0 e rect). O grab usa
a ORDEM (world-x) p/ casar roomid<->recorte por posição — sem projeção de tela. Desanexa limpo.

Uso:  NVT_PPP_PID=<pid> python research/ppp_il2cpp/emitir_tiles.py
"""
import json
import os
import signal
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import frida

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(REPO, "logs", "tiles.json")
_stop = {"flag": False}


def _request_stop(*_a):
    _stop["flag"] = True


for _s in ("SIGBREAK", "SIGTERM", "SIGINT"):
    try:
        signal.signal(getattr(signal, _s), _request_stop)
    except Exception:
        pass


def valid_tiles(payload):
    """{tableId,rect} cru -> {roomid(str): [x0,y0,x1,y1]} só os válidos (id>0 e rect com 4 nums)."""
    out = {}
    for t in (payload or {}).get("tiles") or []:
        tid, rect = t.get("tableId"), t.get("rect")
        if isinstance(tid, int) and tid > 0 and isinstance(rect, list) and len(rect) == 4:
            out[str(tid)] = [float(v) for v in rect]
    return out


def _write(obj):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, OUT)


def main():
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "pppoker.exe"]
    if not procs:
        print("[tiles] PPPoker fechado."); return
    want = int(os.environ.get("NVT_PPP_PID", "0") or 0)
    target = next((p for p in procs if p.pid == want), None) if want else None
    if want and target is None:
        print("[tiles] NVT_PPP_PID=%d não está aberto -> aborta." % want); return
    target = target or procs[0]
    s = dev.attach(target.pid)
    sc = s.create_script(open(os.path.join(HERE, "ler_tiles.js"), encoding="utf-8").read())
    sc.on("message", lambda m, d: None)
    s.on("detached", lambda *a: _request_stop())
    sc.load()
    time.sleep(1.5)
    print("[tiles] anexado (pid %d). Gravando %s a cada 2s. Ctrl+C p/ sair." % (target.pid, OUT), flush=True)
    last = None
    while not _stop["flag"]:
        try:
            r = sc.exports_sync.readtiles2()
            tiles = valid_tiles(r)
            if tiles != last:
                _write(tiles)
                print("[tiles] %d mesa(s): %s" % (len(tiles), sorted(tiles.keys())), flush=True)
                last = tiles
        except Exception as e:
            print("[tiles] erro:", e, flush=True)
        time.sleep(2.0)
    try:
        sc.unload(); s.detach()
    except Exception:
        pass
    print("[tiles] detach limpo.", flush=True)


if __name__ == "__main__":
    main()
