"""LAUNCHER ÚNICO do HENRIQUE (Eduardo 25/11) — um ponto de entrada p/ jogar VÁRIAS plataformas
(Suprema + PPPoker, extensível a X-Poker) AO MESMO TEMPO sem briga de cursor.

UM botão sobe os agentes das plataformas HABILITADAS, cada um no SEU processo. A serialização do clique
físico é GLOBAL e automática: todos os agentes compartilham o MESMO árbitro de cursor —
  - entre PROCESSOS, pelo mutex nomeado de `click_arbiter` (o mesmo que a Suprema já usa);
  - dentro de cada processo (várias mesas), pelo portão FIFO de `cursor_arbiter`.
Resultado: só UM clique físico por vez; o cursor nunca é arrancado no meio de uma ação. Ver
`cursor_arbiter.py` p/ o desenho e `INTEGRACAO` no fim deste arquivo p/ como cada agente se liga.

Uso:
  python iniciar_henrique.py                      -> abre a GUI (ou cai no modo texto se não houver Tk)
  python iniciar_henrique.py --gui                -> força a GUI
  python iniciar_henrique.py --suprema --pppoker  -> CLI: sobe as duas (DRY — observa, não clica)
  python iniciar_henrique.py --suprema --armar    -> sobe a Suprema ARMADA (clica). Pare com Ctrl+C.
  python iniciar_henrique.py --status             -> lista plataformas conhecidas e sai

DRY por padrão (observa/decide/salva, NÃO clica). Só clica com --armar (CLI) ou o checkbox Armar (GUI).
"""
from __future__ import annotations

import os
import sys
import time
import signal
import argparse
import subprocess

REPO = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(REPO, "logs")

# ---- padrão NVT Suprema.exe (R1 atalho no Desktop, R2 zero console) ----
NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
NO_WINDOW = 0x08000000
DETACHED = 0x00000008
ICON_ICO = os.environ.get("NVT_ICON", r"C:\Users\tacao\NvtVoz\nvttracker\nvt.ico")


def _find_pythonw():
    """pythonw.exe (SEM console) p/ a GUI. Cai p/ python.exe se não achar."""
    if os.name == "nt":
        cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(cand):
            return cand
        import shutil
        return shutil.which("pythonw.exe") or sys.executable
    return sys.executable


def _ensure_desktop_shortcut():
    """R1: cria/atualiza 'NVT Henrique.lnk' na Área de Trabalho -> pythonw + este script --gui, com o
    nosso ícone. Idempotente, SEM console (powershell hidden). Mesmo mecanismo do iniciar_suprema."""
    if os.name != "nt":
        return False
    try:
        target = _find_pythonw()
        args = '"%s" --gui' % os.path.abspath(__file__)
        icon = ICON_ICO if os.path.exists(ICON_ICO) else target

        def q(s):
            return str(s).replace("'", "''")

        ps = (
            "$ws=New-Object -ComObject WScript.Shell;"
            "$d=[Environment]::GetFolderPath('Desktop');"
            "$l=$ws.CreateShortcut((Join-Path $d 'NVT Henrique.lnk'));"
            "$l.TargetPath='%s';$l.Arguments='%s';$l.WorkingDirectory='%s';"
            "$l.IconLocation='%s';$l.WindowStyle=1;"
            "$l.Description='NVT Henrique - launcher unico (Suprema + PPPoker, um cursor)';"
            "$l.Save()"
        ) % (q(target), q(args), q(REPO), q(icon))
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                        "-Command", ps], creationflags=NO_WINDOW,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        return True
    except Exception:
        return False


def _ensure_no_console():
    """R2: ZERO CMD na GUI. Se há console attachado, re-executa sob pythonw.exe DETACHED (sem janela) e
    encerra esta instância. Guard por env p/ não recursar. Só faz sentido no caminho GUI."""
    if os.name != "nt" or os.environ.get("NVT_HENRIQUE_GUI") == "1":
        return
    try:
        import ctypes
        has_console = ctypes.windll.kernel32.GetConsoleWindow() != 0
    except Exception:
        has_console = False
    if not has_console:
        os.environ["NVT_HENRIQUE_GUI"] = "1"
        return
    env = dict(os.environ, NVT_HENRIQUE_GUI="1")
    try:
        subprocess.Popen([_find_pythonw(), os.path.abspath(__file__), "--gui"], cwd=REPO, env=env,
                         creationflags=DETACHED | NO_WINDOW | NEW_GROUP, close_fds=True)
    except Exception:
        os.environ["NVT_HENRIQUE_GUI"] = "1"
        return
    os._exit(0)


# =============================================================================================
# ESPECIFICAÇÃO DAS PLATAFORMAS — cada uma sabe montar o comando do seu agente e seu arquivo de parada.
# Acrescentar X-Poker no futuro = mais uma entrada aqui (o árbitro de cursor já cobre N plataformas).
# =============================================================================================
class PlatformSpec:
    def __init__(self, key, nome, script, *, armar_flag, extra_args=(), stop_file=None,
                 process_group=True):
        self.key = key
        self.nome = nome
        self.script = script              # script do agente, relativo ao REPO
        self.armar_flag = armar_flag      # flag que ARMA o clique (ex.: "--armed" / "--armar")
        self.extra_args = list(extra_args)
        self.stop_file = stop_file        # arquivo-gatilho de parada limpa (ou None)
        self.process_group = process_group

    def build_cmd(self, python_exe, armed):
        cmd = [python_exe, os.path.join(REPO, self.script), *self.extra_args]
        if armed:
            cmd.append(self.armar_flag)
        return cmd


PLATFORMS = {
    "suprema": PlatformSpec(
        "suprema", "Suprema", "suprema_agente.py",
        armar_flag="--armed",
        stop_file=os.path.join(LOGS, "suprema_stop.flag"),
    ),
    "pppoker": PlatformSpec(
        "pppoker", "PPPoker", "iniciar_pppoker.py",      # sobe EMITTER + AGENTE juntos
        armar_flag="--armar",
        extra_args=[],
        stop_file=None,                                  # parada via CTRL_BREAK (derruba emitter+agente)
    ),
    # "xpoker": PlatformSpec("xpoker", "X-Poker", "xpoker_agente.py", armar_flag="--armar", ...),
}


def _python_exe(prefer_windowless=False):
    """Interpretador p/ os subprocessos. pythonw (sem console) p/ GUI; python no CLI (mostra o log)."""
    if prefer_windowless and os.name == "nt":
        cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(cand):
            return cand
    return sys.executable


# =============================================================================================
# NÚCLEO — sobe/derruba os agentes. `spawn`/`clock`/`sleep` são injetáveis p/ teste offline (sem abrir
# processo de verdade). Cada agente sobe no SEU processo; a arbitragem do cursor é compartilhada por
# fora (mutex nomeado), então o núcleo NÃO precisa injetar nada nos subprocessos.
# =============================================================================================
class LauncherCore:
    def __init__(self, *, platforms=None, spawn=None, python_exe=None,
                 clock=time.monotonic, sleep=time.sleep, log=print):
        self._platforms = platforms if platforms is not None else PLATFORMS
        self._spawn = spawn if spawn is not None else self._default_spawn
        self._python = python_exe or _python_exe()
        self._clock = clock
        self._sleep = sleep
        self._log = log
        self._procs = {}                 # key -> handle do processo
        self._armed = {}                 # key -> bool (como foi iniciado)

    # ---- spawn real (Windows: grupo próprio p/ CTRL_BREAK de parada limpa) ----
    def _default_spawn(self, cmd):
        kwargs = {"cwd": REPO}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        return subprocess.Popen(cmd, **kwargs)

    # ---- API ----
    def is_running(self, key):
        p = self._procs.get(key)
        if p is None:
            return False
        poll = getattr(p, "poll", None)
        return poll is None or poll() is None

    def start(self, key, *, armed=False):
        if key not in self._platforms:
            raise KeyError("plataforma desconhecida: %s" % key)
        if self.is_running(key):
            self._log("[HENRIQUE] %s já está rodando -> ignoro." % self._platforms[key].nome)
            return self._procs[key]
        spec = self._platforms[key]
        # limpa um stop-file velho p/ o agente não morrer ao nascer
        if spec.stop_file:
            try:
                os.makedirs(os.path.dirname(spec.stop_file), exist_ok=True)
                if os.path.exists(spec.stop_file):
                    os.remove(spec.stop_file)
            except OSError:
                pass
        cmd = spec.build_cmd(self._python, armed)
        self._log("[HENRIQUE] subindo %s %s: %s"
                  % (spec.nome, "ARMADO (CLICA)" if armed else "DRY (observa)", " ".join(cmd)))
        p = self._spawn(cmd)
        self._procs[key] = p
        self._armed[key] = armed
        return p

    def start_many(self, keys, *, armed=False):
        return {k: self.start(k, armed=armed) for k in keys}

    def stop(self, key, *, grace_s=6.0):
        """Parada LIMPA: cria o stop-file (Suprema desanexa o Frida), manda CTRL_BREAK ao grupo, espera
        `grace_s` e, se ainda vivo, encerra. Nunca deixa hook pendurado."""
        p = self._procs.get(key)
        if p is None:
            return
        spec = self._platforms[key]
        if spec.stop_file:
            try:
                open(spec.stop_file, "w").close()
            except OSError:
                pass
        self._signal_break(p)
        if not self._wait(p, grace_s):
            self._log("[HENRIQUE] %s não saiu em %.0fs -> encerro." % (spec.nome, grace_s))
            for meth in ("terminate", "kill"):
                fn = getattr(p, meth, None)
                if fn:
                    try:
                        fn()
                    except Exception:
                        pass
                    if self._wait(p, 2.0):
                        break
        self._procs.pop(key, None)
        self._armed.pop(key, None)
        self._log("[HENRIQUE] %s parado." % spec.nome)

    def stop_all(self, *, grace_s=6.0):
        for key in list(self._procs.keys()):
            self.stop(key, grace_s=grace_s)

    def status(self):
        return {k: ("rodando" if self.is_running(k) else "parado") for k in self._platforms}

    # ---- helpers ----
    def _signal_break(self, p):
        pid = getattr(p, "pid", None)
        try:
            if os.name == "nt" and pid:
                os.kill(pid, signal.CTRL_BREAK_EVENT)   # grupo próprio -> vira KeyboardInterrupt no agente
            else:
                send = getattr(p, "send_signal", None)
                if send:
                    send(signal.SIGINT)
        except Exception:
            pass

    def _wait(self, p, timeout_s):
        wait = getattr(p, "wait", None)
        if wait is not None:
            try:
                wait(timeout=timeout_s)
                return True
            except TypeError:
                pass
            except Exception:
                return getattr(p, "poll", lambda: 0)() is not None
        deadline = self._clock() + timeout_s
        while self._clock() < deadline:
            if getattr(p, "poll", lambda: 0)() is not None:
                return True
            self._sleep(0.1)
        return getattr(p, "poll", lambda: None)() is not None


# =============================================================================================
# GUI (Tkinter) — checkbox por plataforma (habilitar), checkbox Armar, Iniciar/Parar, status.
# =============================================================================================
def run_gui(core=None):
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as e:                       # sem Tk -> cai no texto
        print("[HENRIQUE] Tkinter indisponível (%s) -> use o modo CLI (--suprema/--pppoker)." % e)
        return 2

    core = core or LauncherCore(python_exe=_python_exe(prefer_windowless=True))
    BG, FG, GOLD, GREEN, RED = "#0e1512", "#eaf2ee", "#d4af37", "#2ecc71", "#e06c5a"
    root = tk.Tk()
    root.title("Henrique — Launcher único")
    root.configure(bg=BG)
    root.geometry("460x360")

    tk.Label(root, text="HENRIQUE", bg=BG, fg=GOLD,
             font=("Segoe UI", 20, "bold")).pack(pady=(14, 0))
    tk.Label(root, text="Um launcher, várias plataformas, um só cursor",
             bg=BG, fg=FG, font=("Segoe UI", 9)).pack()

    enable = {}
    frame = tk.Frame(root, bg=BG)
    frame.pack(pady=12)
    for key, spec in core._platforms.items():
        v = tk.BooleanVar(value=True)
        enable[key] = v
        tk.Checkbutton(frame, text=spec.nome, variable=v, bg=BG, fg=FG, selectcolor="#16241d",
                       activebackground=BG, activeforeground=GOLD,
                       font=("Segoe UI", 12)).pack(anchor="w")

    armed_var = tk.BooleanVar(value=False)
    tk.Checkbutton(root, text="Armar (CLICA de verdade) — sem isto é DRY (observa)",
                   variable=armed_var, bg=BG, fg=RED, selectcolor="#16241d",
                   activebackground=BG, activeforeground=RED,
                   font=("Segoe UI", 10, "bold")).pack()

    status = tk.Label(root, text="", bg=BG, fg=GREEN, font=("Consolas", 9), justify="left")
    status.pack(pady=8)

    def refresh():
        st = core.status()
        status.config(text="\n".join("%-10s %s" % (core._platforms[k].nome, v) for k, v in st.items()))
        root.after(1000, refresh)

    def do_start():
        keys = [k for k, v in enable.items() if v.get()]
        if not keys:
            status.config(text="Marque ao menos uma plataforma.")
            return
        core.start_many(keys, armed=armed_var.get())

    def do_stop():
        core.stop_all()

    btns = tk.Frame(root, bg=BG)
    btns.pack(pady=6)
    tk.Button(btns, text="Iniciar", command=do_start, bg=GREEN, fg="#0e1512",
              font=("Segoe UI", 11, "bold"), width=12).pack(side="left", padx=6)
    tk.Button(btns, text="Parar tudo", command=do_stop, bg=RED, fg="#0e1512",
              font=("Segoe UI", 11, "bold"), width=12).pack(side="left", padx=6)

    def on_close():
        core.stop_all()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    refresh()
    root.mainloop()
    return 0


# =============================================================================================
# CLI
# =============================================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="Launcher único do Henrique (multi-plataforma, um cursor).")
    for key, spec in PLATFORMS.items():
        ap.add_argument("--%s" % key, action="store_true", help="habilita a plataforma %s" % spec.nome)
    ap.add_argument("--armar", action="store_true",
                    help="ARMA o clique em TODAS as plataformas habilitadas (sem isto = DRY).")
    ap.add_argument("--gui", action="store_true", help="abre a GUI (padrão quando não há argumentos).")
    ap.add_argument("--status", action="store_true", help="lista as plataformas conhecidas e sai.")
    args = ap.parse_args(argv)

    if args.status:
        for key, spec in PLATFORMS.items():
            print("%-10s script=%s armar=%s" % (spec.nome, spec.script, spec.armar_flag))
        return 0

    selected = [k for k in PLATFORMS if getattr(args, k)]
    if args.gui or (not selected and not args.status):
        _ensure_no_console()          # R2: nunca CMD ao fundo (re-exec sob pythonw se preciso)
        _ensure_desktop_shortcut()    # R1: atalho na Área de Trabalho (padrão NVT Suprema)
        return run_gui()

    core = LauncherCore()
    core.start_many(selected, armed=args.armar)
    print("[HENRIQUE] %d plataforma(s) no ar (%s). Ctrl+C p/ parada limpa de todas."
          % (len(selected), "ARMADO" if args.armar else "DRY"))
    try:
        while any(core.is_running(k) for k in selected):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[HENRIQUE] parando tudo...")
    finally:
        core.stop_all()
    return 0


# =============================================================================================
# INTEGRACAO — como o agente principal liga CADA agente ao árbitro de cursor (feito FORA deste arquivo;
# os agentes não são editados aqui). Ver cursor_arbiter.py.
#
#   SUPREMA (suprema_agente.py): JÁ arbitrado. O _click_worker envolve C.execute(...) em
#     `with click_lock(): ...` (click_arbiter), que é o MESMO mutex nomeado. Nada a fazer.
#     [Opcional] p/ ganhar também a fila FIFO in-process entre mesas, trocar
#       `from click_arbiter import click_lock, ClickBusy`  ->  usar `cursor_arbiter.cursor_turn`:
#       `with cursor_turn("SUPREMA"): res = C.execute(...)`  (captura CursorBusy no lugar de ClickBusy).
#
#   PPPOKER (pppoker_agente.py): liga injetando o ADAPTER ARBITRADO no build_live_execute, que já
#     aceita `adapter=`. No ponto onde hoje faz `execute = build_live_execute(hwnd, control=control,
#     enable_sizing=args.sizing)`, passar:
#       from cursor_input_win import WindowsCursorInput
#       from cursor_arbiter import make_arbitrated_adapter
#       adapter = make_arbitrated_adapter(WindowsCursorInput(), plataforma="PPPOKER")
#       execute = build_live_execute(hwnd, control=control, enable_sizing=args.sizing, adapter=adapter)
#     Assim todo move_to/click_once/drag do PPPoker (single-click E sizing) passa pelo árbitro global,
#     SEM editar ppp_execute/ppp_sizing.
# =============================================================================================
if __name__ == "__main__":
    raise SystemExit(main())
