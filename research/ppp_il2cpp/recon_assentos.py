"""Runner do recon_assentos.js — lista classes de UI de mesa/assento do PPPoker e seus campos
(RectTransform/roomid/seatid). READ-ONLY. python -I recon_assentos.py [segundos]."""
import json
import os
import signal
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
_STOP = {"flag": False}
for _s in ("SIGBREAK", "SIGTERM", "SIGINT"):
    try:
        signal.signal(getattr(signal, _s), lambda *a: _STOP.update(flag=True))
    except Exception:
        pass


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "pppoker.exe"]
    if not procs:
        print("[recon] PPPoker fechado."); return 1
    session = dev.attach(procs[0].pid)
    session.on("detached", lambda *a: _STOP.update(flag=True))
    with open(os.path.join(_HERE, "recon_assentos.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())

    def on_msg(m, _d):
        if m.get("type") == "send":
            p = m["payload"]
            if "done" in p:
                print(f"[recon] {p['done']} classes casadas."); return
            print(f"\n[{p['img']}] {p['cls']}")
            for f in p["fields"]:
                print("   ", f)
        elif m.get("type") == "error":
            print("[js-erro]", m.get("stack") or m.get("description"))

    script.on("message", on_msg)
    script.load()
    print(f"[recon] anexado (pid {procs[0].pid}); {_SECS:.0f}s.", flush=True)
    t0 = time.time()
    try:
        while not _STOP["flag"] and (time.time() - t0) < _SECS:
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            script.unload()
        except Exception:
            pass
        try:
            session.detach()
        except Exception:
            pass
    print("[recon] fim.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
