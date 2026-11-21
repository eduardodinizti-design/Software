"""Runner do discrim_mesa.js — observa ActionBRC/RoundStart/Dealer/HandCard nas DUAS mesas
e imprime this/args[2]/args[3]/gameid p/ achar o discriminador de mesa. READ-ONLY.
Uso: python -I discrim_mesa.py [segundos]. Desligamento limpo (unload antes do detach)."""
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
_SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
_STOP = {"flag": False}


def _stop(*_a):
    _STOP["flag"] = True


for _s in ("SIGBREAK", "SIGTERM", "SIGINT"):
    try:
        signal.signal(getattr(signal, _s), _stop)
    except Exception:
        pass


def _fmt(p):
    e = p.get("payload") if isinstance(p, dict) else None
    return e


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "pppoker.exe"]
    if not procs:
        print("[discrim] PPPoker não está aberto."); return 1
    pid = procs[0].pid
    session = dev.attach(pid)
    session.on("detached", lambda *a: _STOP.update(flag=True))
    with open(os.path.join(_HERE, "discrim_mesa.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())

    def on_msg(m, _d):
        if m.get("type") == "send":
            e = m.get("payload")
            # linha compacta: handler, classe, this, a2(int/cls), gameid/stage/seat
            a2 = e.get("a2", {})
            extra = {k: e[k] for k in ("stage", "curBlind", "seat", "atype", "chips", "dealer", "gameid", "c1", "c2") if k in e}
            print(f"{e.get('h'):<16} {e.get('cn'):<16} this={e.get('this')} "
                  f"a2int={a2.get('int')} a2cls={a2.get('cls')} {json.dumps(extra, ensure_ascii=False)}", flush=True)
        elif m.get("type") == "error":
            print("[js-erro]", m.get("stack") or m.get("description"), flush=True)

    script.on("message", on_msg)
    script.load()
    print(f"[discrim] anexado (pid {pid}); observando {_SECONDS:.0f}s. Jogue as DUAS mesas.", flush=True)
    t0 = time.time()
    try:
        while not _STOP["flag"] and (time.time() - t0) < _SECONDS:
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
    print("[discrim] fim.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
