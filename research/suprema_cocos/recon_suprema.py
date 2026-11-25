"""RECON da SUPREMA (Cocos Creator + V8) — anexa no SupremaPoker.exe, injeta o agente
de captura (caminho de eval JÁ verificado por RE) e o inject_recon.js, e imprime os
eventos que o JS do jogo emite (globals, shape do spp, handlers candidatos, tráfego WS).

Objetivo: UMA sessão ao vivo revela o fluxo da mão (deal/ação/board/winner) no JS do
jogo — o análogo do recon_mao_campos do PPPoker, porém em JS (bem mais fácil que IL2CPP).

Uso:
    python -I recon_suprema.py                 # roda até Ctrl+C; digite comandos __nvt.* p/ iterar
    python -I recon_suprema.py --seconds 180
    # durante a sessão, digite (ENTER) p/ rodar JS no jogo, ex.:
    #   __nvt.shape('spp.net')
    #   __nvt.findHandlers('spp')
    #   __nvt.hookfn('spp','dispatch','spp.dispatch')

Desligamento LIMPO (ver [[nvt-fatal-error-fechar-frida]]): unload ANTES do detach; se o
pai (launcher) morrer, desanexa sozinho. READ-ONLY (observa; não joga).
"""
import argparse
import os
import signal
import sys
import threading
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = int(os.environ.get("NVT_PARENT_PID", "0") or 0)
_STOP = {"flag": False}


def _request_stop(*_a):
    _STOP["flag"] = True


def _parent_gone():
    if not _PARENT:
        return False
    try:
        import psutil
        return not psutil.pid_exists(_PARENT)
    except Exception:
        return False


for _s in ("SIGBREAK", "SIGTERM", "SIGINT"):
    try:
        signal.signal(getattr(signal, _s), _request_stop)
    except Exception:
        pass


def _exports(script):
    """Compatível com várias versões do frida-python."""
    return getattr(script, "exports_sync", None) or script.exports


def _on_message(m, _data):
    if m.get("type") == "send":
        p = m.get("payload") or {}
        if isinstance(p, dict) and "nvt" in p:
            print("[evt]", p["nvt"], flush=True)
        elif isinstance(p, dict) and "nvt_raw" in p:
            print("[raw]", p["nvt_raw"], flush=True)
        else:
            print("[msg]", p, flush=True)
    elif m.get("type") == "error":
        print("[js-erro]", m.get("stack") or m.get("description"), flush=True)


def _stdin_loop(exp):
    """Lê comandos JS do teclado e roda no jogo (iterar o recon ao vivo)."""
    for line in sys.stdin:
        if _STOP["flag"]:
            break
        code = line.strip()
        if not code:
            continue
        try:
            r = exp.eval_string(code)
            print("[eval ->]", r, flush=True)
        except Exception as e:
            print("[eval erro]", e, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=0.0, help="0 = roda até Ctrl+C")
    ap.add_argument("--process", default="SupremaPoker.exe")
    ap.add_argument("--no-stdin", action="store_true", help="não ler comandos do teclado")
    args = ap.parse_args()

    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == args.process.lower()]
    if not procs:
        print(f"[recon] {args.process} não está aberto."); return 1
    pid = procs[0].pid
    session = dev.attach(pid)
    session.on("detached", lambda *a: _STOP.update(flag=True))
    with open(os.path.join(_HERE, "suprema_capture_agent.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())
    script.on("message", _on_message)
    script.load()
    exp = _exports(script)
    ok = exp.ready()
    print(f"[recon] anexado a {args.process} (pid {pid}); agente ready={ok}", flush=True)
    with open(os.path.join(_HERE, "inject_recon.js"), encoding="utf-8") as fh:
        recon = fh.read()
    try:
        exp.eval_string(recon)        # instala __nvt e faz o recon inicial
        print("[recon] inject_recon.js carregado. Observe os [evt]. Entre numa MESA e jogue 1 mão.", flush=True)
    except Exception as e:
        print("[recon] falha ao injetar recon:", e, flush=True)

    if not args.no_stdin and sys.stdin and sys.stdin.isatty():
        threading.Thread(target=_stdin_loop, args=(exp,), daemon=True).start()

    t0 = time.time()
    try:
        while not _STOP["flag"]:
            if args.seconds and (time.time() - t0) >= args.seconds:
                break
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
