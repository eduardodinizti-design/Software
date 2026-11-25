"""Runner do recon_mao_campos.js (READ-ONLY): anexa no PPPoker e imprime o dump
RECURSIVO dos campos de EnterRoomRSP / WinnerRSP / SeatStatusBRC / DealerInfoRSP /
ShowHandRSP (assento->conta+stack, pote/ganhador, botão, cartas de vilão). Objetivo:
UMA sessão ao vivo revela TODOS os nomes de campo que faltam p/ fechar a captura.

Uso:
    python -I recon_mao_campos.py            # observa 120s (jogue 1 mão até showdown)
    python -I recon_mao_campos.py 300        # observa por 300s

Desligamento LIMPO (ver [[nvt-fatal-error-fechar-frida]]): unload ANTES do detach, e se
o processo-pai (launcher) morrer, desanexa sozinho — nunca deixa o host Frida ser morto
no osso (= PPPoker fatal error).
"""
import os
import signal
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
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


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "pppoker.exe"]
    if not procs:
        print("[recon] PPPoker nao esta aberto."); return 1
    pid = procs[0].pid
    session = dev.attach(pid)
    with open(os.path.join(HERE, "recon_mao_campos.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())
    session.on("detached", lambda *a: _STOP.update(flag=True))
    script.set_log_handler(lambda level, text: print(text, flush=True))
    script.on("message", lambda m, d: print("[msg]", m.get("payload") or m, flush=True))
    script.load()
    print(f"[recon] anexado ao PPPoker (pid {pid}). Observando {SECONDS:.0f}s. "
          f"Jogue UMA mao ate o showdown. Ctrl+C p/ sair.", flush=True)
    t0 = time.time()
    try:
        while not _STOP["flag"] and (time.time() - t0) < SECONDS:
            if _parent_gone():
                break
            time.sleep(0.4)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            script.unload()       # reverte os hooks com a conexao viva -> sem crash
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
