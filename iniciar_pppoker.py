"""ENTRADA ÚNICA do PPPoker p/ o launcher do Henrique: sobe o EMITTER (protobuf Frida -> estado) + o
AGENTE (decide/clica), auto-detectando a instância PPPoker. --armar faz o agente CLICAR (cursor em
curva, arbitrado). Parada limpa via CTRL_BREAK (KeyboardInterrupt) -> derruba emitter + agente.

Usado pelo iniciar_henrique (launcher único) como o "script" da plataforma PPPoker — assim o launcher
sobe PPPoker e Suprema juntos, e o árbitro de cursor (mutex nomeado) serializa os cliques das duas.
"""
from __future__ import annotations

import os
import sys
import time
import signal
import argparse
import subprocess

REPO = os.path.dirname(os.path.abspath(__file__))
EMITTER = os.path.join(REPO, "research", "ppp_il2cpp", "emitir_seats.py")
AGENT = os.path.join(REPO, "pppoker_agente.py")
LIVE = os.path.join("logs", "estado_mesa.json")
NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)


def _pppoker_pid_hwnd():
    """(pid, hwnd) da 1ª janela PPPoker, ou (None, None). Usa o discover já validado."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        import operar_mesa
        wins = operar_mesa.discover_pppoker().get("windows", [])
        if not wins:
            return None, None
        hwnd = wins[0]["hwnd"]
        pid = wt.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value), int(hwnd)
    except Exception:
        return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sobe EMITTER + AGENTE do PPPoker (entrada do launcher).")
    ap.add_argument("--armar", action="store_true", help="o agente CLICA de verdade (senão DRY).")
    ap.add_argument("--sizing", action="store_true", help="(com --armar) também clica RAISE/BET.")
    ap.add_argument("--emitter-wait", type=float, default=4.0, help="s p/ o emitter anexar antes do agente.")
    args = ap.parse_args(argv)

    pid, hwnd = _pppoker_pid_hwnd()
    if pid is None:
        print("[PPPoker] nenhuma janela PPPoker aberta -> nada a subir.")
        return 1
    print("[PPPoker] instância pid=%s hwnd=%s | %s" % (pid, hwnd, "ARMADO" if args.armar else "DRY"))
    env = dict(os.environ, NVT_PPP_PID=str(pid))
    procs = []
    try:
        # 1) EMITTER (protobuf -> logs/estado_mesa.json + tiles.json)
        procs.append(subprocess.Popen([sys.executable, EMITTER], cwd=REPO, env=env,
                                      creationflags=NEW_GROUP))
        time.sleep(max(0.0, args.emitter_wait))          # deixa anexar e escrever o 1º estado
        # 2) AGENTE (lê o estado, decide, clica se armado)
        cmd = [sys.executable, AGENT, "--live", LIVE, "--hwnd", str(hwnd)]
        if args.armar:
            cmd.append("--armar")
        if args.sizing:
            cmd.append("--sizing")
        agent = subprocess.Popen(cmd, cwd=REPO, env=env, creationflags=NEW_GROUP)
        procs.append(agent)
        while agent.poll() is None:                       # vive enquanto o agente viver
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[PPPoker] parando emitter + agente...")
    finally:
        for p in procs:                                   # parada limpa (CTRL_BREAK -> desanexa Frida)
            try:
                p.send_signal(signal.CTRL_BREAK_EVENT)
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=6)
            except Exception:
                try:
                    p.terminate()
                except Exception:
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
