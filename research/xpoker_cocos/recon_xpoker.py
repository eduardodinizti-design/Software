"""RECON do X-Poker (Cocos2d-x / GLFW) — anexa no X-Poker.exe e identifica a ENGINE de
script e a entrada p/ rodar script (o análogo do evalString da Suprema). READ-ONLY.

Saída: módulos, pistas de engine (Cocos/Lua/JS), e os exports reveladores
(ScriptEngine/eval/execute/jsb/lua/log) — o ponto de partida p/ a captura de mão.

Uso:
    python -I recon_xpoker.py
    python -I recon_xpoker.py --seconds 60
Depois, no código, usar rpc exportsOf('<modulo>','<regex>') p/ cavar fino.
Desligamento limpo (unload antes do detach). Ver [[nvt-salas-engines]] / [[nvt-fatal-error-fechar-frida]].
"""
import argparse
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
_STOP = {"flag": False}
_PARENT = int(os.environ.get("NVT_PARENT_PID", "0") or 0)


def _stop(*_a):
    _STOP["flag"] = True


for _s in ("SIGBREAK", "SIGTERM", "SIGINT"):
    try:
        signal.signal(getattr(signal, _s), _stop)
    except Exception:
        pass


def _parent_gone():
    if not _PARENT:
        return False
    try:
        import psutil
        return not psutil.pid_exists(_PARENT)
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--process", default="X-Poker.exe")
    ap.add_argument("--aliases", default="X-Poker.exe,XPoker.exe,X_Poker.exe")
    a = ap.parse_args()

    import frida
    dev = frida.get_local_device()
    names = {n.strip().lower() for n in (a.process + "," + a.aliases).split(",") if n.strip()}
    procs = [p for p in dev.enumerate_processes() if p.name.lower() in names]
    if not procs:
        print(f"[recon] X-Poker não está aberto (procurei: {sorted(names)})."); return 1
    pid = procs[0].pid
    session = dev.attach(pid)
    session.on("detached", lambda *x: _STOP.update(flag=True))
    with open(os.path.join(_HERE, "recon_xpoker.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())
    script.on("message", lambda m, d: print("[msg]", json.dumps(m.get("payload"), ensure_ascii=False)[:2000]
                                             if m.get("type") == "send" else (m.get("stack") or m), flush=True))
    script.load()
    exp = getattr(script, "exports_sync", None) or script.exports
    try:
        print("[recon] PISTAS DE ENGINE:", json.dumps(exp.engine_hints(), ensure_ascii=False), flush=True)
        se = exp.script_exports()
        print(f"[recon] {len(se)} export(s) de script/engine reveladores:", flush=True)
        for e in se[:80]:
            print("   ", e["mod"], e["name"], e["addr"], flush=True)
        if not se:
            print("   (nenhum export óbvio — provável engine embutida/sem export; usar assinatura/RVA como na Suprema)", flush=True)
    except Exception as e:
        print("[recon] erro consultando rpc:", e, flush=True)
    t0 = time.time()
    try:
        while not _STOP["flag"] and (time.time() - t0) < a.seconds:
            if _parent_gone():
                break
            time.sleep(0.4)
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
