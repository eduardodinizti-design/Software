"""LAUNCHER WIZARD da SUPREMA (observacional) — "clicou, rodou", NÍVEL PROFISSIONAL.

REGRAS (LEI de Eduardo — valem p/ qualquer update deste arquivo):
  R1) ATALHO NO DESKTOP: a 1ª execução cria/atualiza "NVT Suprema.lnk" na Área de
      Trabalho (aponta p/ pythonw + este script, com o nosso ícone). Inicia-se pelo atalho.
  R2) ZERO CONSOLE / WIZARD: NENHUMA tela de CMD ao fundo (nem piscar). A interface é uma
      JANELA GRÁFICA com a NOSSA ARTE (logo NVT) que mostra o progresso e tem botão Parar.
      Conseguido re-executando sob pythonw.exe DETACHED e abrindo um painel tkinter.

Com a Suprema aberta numa mesa, sobe numa ÚNICA instância de hook (respeita a trava
anti-injeção-dupla) tudo que faz a mesa virar dados + HUD no NVT:
  1) CAPTURADOR (capturar_suprema_net.py, 1 hook Frida READ-ONLY): --base -> .txt Hand2Note
     (sala 'SupremaPoker') p/ o watcher; --hud-dir -> snapshot por assento p/ o HUD;
     --advise -> CONSELHO (dry-run). DADOS + BANCO + HUD + CONSELHO com UM só attach.
  2) WATCHER (nvt-watch): ingere os .txt -> banco. Só com membro autorizado e se já não roda.
  3) HUD OVERLAY da Suprema (--layout suprema --live-only): HUD nos 9 assentos da janela do
     cliente, lendo o snapshot isolado (_live_suprema). --live-only = NUNCA inventa mesa do
     banco (sem mesa ao vivo = nenhuma caixa; mata o bug das "mesas-fantasma" sobre o lobby).

Tudo OBSERVACIONAL (lê e mostra; NÃO clica/joga). Fechar o Wizard (ou Parar) desanexa o
Frida LIMPO (CTRL_BREAK ao capturador) p/ não travar o cliente.
"""
import os
import sys
import time
import glob
import signal
import shutil
import ctypes
import subprocess
from datetime import datetime

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

# raiz do pacote nvttracker (watcher/overlay rodam a partir dela): env ou padrão da máquina
TRACKER_ROOT = os.environ.get("NVT_TRACKER_ROOT", r"C:\Users\tacao\NvtVoz\nvttracker")

# NOSSA ARTE (R2): ícone p/ atalho+janela, logo p/ o cabeçalho do Wizard
ICON_ICO = os.path.join(TRACKER_ROOT, "nvt.ico")
LOGO_PNG = r"C:\Meus Projetos\Aplicativos\Logótipo NVT Poker Team transparente.png"
if not os.path.exists(ICON_ICO):
    ICON_ICO = r"C:\Meus Projetos\Aplicativos\NVT-Mesas-src\assets\nvt.ico"

# paleta da identidade NVT (verde feltro + ouro)
BG, CARD, GOLD, GREEN, FG, MUTED, RED = (
    "#0e1512", "#16241d", "#d4af37", "#2ecc71", "#eaf2ee", "#8aa29a", "#e06c5a")

# flags de CONFIGURAÇÃO da HUD (o overlay lê a cada ciclo; mesmos caminhos do hud_overlay)
_NVTDIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "NvtTracker")
_HIDE_HERO_FILE = os.path.join(_NVTDIR, "hud_hide_hero.flag")   # existe = oculta a caixa do herói
_ALPHA_FILE = os.path.join(_NVTDIR, "hud_alpha.flag")           # opacidade 0.20–1.0 (slider)
_LOCK_FILE = os.path.join(_NVTDIR, "hud_locked.flag")           # existe = HUD fixa (não arrasta; segue a mesa)


def _read_alpha_pct():
    try:
        with open(_ALPHA_FILE, encoding="utf-8") as f:
            return max(20, min(100, int(round(float(f.read().strip()) * 100))))
    except Exception:
        return 95

NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
NO_WINDOW = 0x08000000
DETACHED = 0x00000008


# ───────────────────────── helpers de ambiente ─────────────────────────
def _live_base():
    base = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                        "NvtTracker", "live")
    os.makedirs(base, exist_ok=True)
    return base


def _find_python():
    """Python real do sistema (tem frida/psutil/psycopg/tkinter). Prefere python.exe p/ filhos."""
    exe = sys.executable
    if exe and "nvt tracker" not in exe.lower() and not getattr(sys, "frozen", False):
        if os.path.basename(exe).lower() == "pythonw.exe":
            cand = os.path.join(os.path.dirname(exe), "python.exe")
            if os.path.exists(cand):
                return cand
        return exe
    for n in ("python.exe", "python3.exe"):
        p = shutil.which(n)
        if p and "nvt tracker" not in p.lower():
            return p
    for pat in (os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python3*\python.exe"),
                r"C:\Program Files\Python3*\python.exe"):
        g = sorted(glob.glob(pat))
        if g:
            return g[-1]
    return exe or "python"


def _find_pythonw():
    """pythonw.exe (SEM console) p/ o próprio Wizard. Cai p/ python.exe se não achar."""
    py = _find_python()
    b = os.path.basename(py).lower()
    if b.startswith("python") and b.endswith(".exe"):
        cand = os.path.join(os.path.dirname(py), "pythonw.exe")
        if os.path.exists(cand):
            return cand
    return shutil.which("pythonw.exe") or py


def _suprema_running():
    try:
        import psutil
        return any("supremapoker" in (p.info.get("name") or "").lower()
                   for p in psutil.process_iter(["name"]))
    except Exception:
        return False


def _proc_has(substr):
    try:
        import psutil
        for p in psutil.process_iter(["cmdline"]):
            if substr in " ".join(p.info.get("cmdline") or []):
                return True
    except Exception:
        pass
    return False


def _resolve_dsn():
    if os.environ.get("NVT_DATABASE_URL"):
        return os.environ["NVT_DATABASE_URL"]
    try:
        sys.path.insert(0, TRACKER_ROOT)
        from nvttracker.viz.hud import resolve_dsn
        return resolve_dsn(None)
    except Exception:
        return ""


def _live_member(dsn):
    m = os.environ.get("NVT_LIVE_MEMBER")
    if m:
        return m
    if not dsn:
        return ""
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=8) as c:
            r = c.execute("SELECT member_id FROM nvt_members WHERE db_user=current_user LIMIT 1").fetchone()
            return r[0] if r else ""
    except Exception:
        return ""


def _cleanup_stale():
    """Libera a trava de hook único: encerra hooks ÓRFÃOS da Suprema (capturar/assistir/validar)
    e um overlay suprema anterior. Host Frida recebe CTRL_BREAK -> detach LIMPO. Nunca o cliente."""
    me = os.getpid()
    hook_scripts = ("capturar_suprema_net", "assistir_suprema", "validar_suprema")
    overlay_mark = "_live_suprema"
    brk = getattr(signal, "CTRL_BREAK_EVENT", None)
    killed = []
    try:
        import psutil
    except Exception:
        return killed
    for p in list(psutil.process_iter(["pid", "cmdline"])):
        try:
            if p.info["pid"] == me:
                continue
            cmd = " ".join(p.info.get("cmdline") or [])
            if not cmd:
                continue
            is_hook = any(s in cmd for s in hook_scripts)
            is_overlay = ("hud_overlay" in cmd and overlay_mark in cmd)
            if not (is_hook or is_overlay):
                continue
            if is_hook and brk is not None:
                try:
                    os.kill(p.info["pid"], brk)
                except Exception:
                    p.terminate()
            else:
                p.terminate()
            killed.append(p.info["pid"])
        except Exception:
            continue
    if killed:
        time.sleep(2.0)
        for pid in killed:
            try:
                psutil.Process(pid).kill()
            except Exception:
                pass
    return killed


# ───────────────────────── R1: atalho no desktop ─────────────────────────
def _ensure_desktop_shortcut():
    """Cria/atualiza 'NVT Suprema.lnk' na Área de Trabalho -> pythonw + este script, com o
    nosso ícone. Idempotente e SEM console (powershell hidden, janela 0)."""
    try:
        pyw = _find_pythonw()
        script = os.path.abspath(__file__)
        icon = ICON_ICO if os.path.exists(ICON_ICO) else pyw

        def q(s):
            return str(s).replace("'", "''")

        ps = (
            "$ws=New-Object -ComObject WScript.Shell;"
            "$d=[Environment]::GetFolderPath('Desktop');"
            "$l=$ws.CreateShortcut((Join-Path $d 'NVT Suprema.lnk'));"
            "$l.TargetPath='%s';"
            "$l.Arguments='\"%s\"';"
            "$l.WorkingDirectory='%s';"
            "$l.IconLocation='%s';"
            "$l.WindowStyle=1;"
            "$l.Description='NVT Suprema - dados + banco + HUD';"
            "$l.Save()"
        ) % (q(pyw), q(script), q(REPO), q(icon))
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
            creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=25)
        return True
    except Exception:
        return False


# ───────────────────────── R2: garantir SEM console ─────────────────────────
def _ensure_no_console():
    """ZERO CMD: se há console attachado (python.exe/duplo-clique), re-executa sob pythonw.exe
    DETACHED + sem janela e encerra a instância com console. Guard por env p/ não recursar."""
    if os.environ.get("NVT_SUPREMA_GUI") == "1":
        return
    try:
        has_console = ctypes.windll.kernel32.GetConsoleWindow() != 0
    except Exception:
        has_console = False
    if not has_console:
        os.environ["NVT_SUPREMA_GUI"] = "1"   # já sem console (pythonw): segue p/ o Wizard
        return
    pyw = _find_pythonw()
    env = dict(os.environ, NVT_SUPREMA_GUI="1")
    try:
        subprocess.Popen([pyw, os.path.abspath(__file__)], cwd=REPO, env=env,
                         creationflags=DETACHED | NO_WINDOW | NEW_GROUP, close_fds=True)
    except Exception:
        os.environ["NVT_SUPREMA_GUI"] = "1"   # re-exec falhou: degrada e segue aqui mesmo
        return
    os._exit(0)   # mata o processo com console; o shell do usuário volta na hora


# ───────────────────────── o Wizard (janela com nossa arte) ─────────────────────────
class Wizard:
    STEPS = [
        ("suprema", "Suprema Poker"),
        ("limpeza", "Preparando sessão"),
        ("captura", "Captura  (dados · banco · HUD · conselho)"),
        ("watcher", "Ingestão no banco"),
        ("hud", "HUD nos assentos"),
    ]

    def __init__(self):
        import tkinter as tk
        self.tk = tk
        self.procs = []
        self.logs = []
        self.rows = {}
        self.root = tk.Tk()
        self.root.title("NVT Suprema")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        try:
            if os.path.exists(ICON_ICO):
                self.root.iconbitmap(ICON_ICO)
        except Exception:
            pass
        self._build()
        self._center(520, 600)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.after(80, self._bringup)

    def _center(self, w, h):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))

    def _build(self):
        tk = self.tk
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=22, pady=(20, 8))
        self._logo = None
        try:
            img = tk.PhotoImage(file=LOGO_PNG)
            while img.width() > 190:
                img = img.subsample(2, 2)
            self._logo = img
            tk.Label(head, image=img, bg=BG).pack()
        except Exception:
            tk.Label(head, text="NVT", font=("Segoe UI Black", 34, "bold"),
                     fg=GOLD, bg=BG).pack()
        tk.Label(head, text="SUPREMA", font=("Segoe UI", 20, "bold"),
                 fg=FG, bg=BG).pack(pady=(4, 0))
        tk.Label(head, text="dados · banco · HUD · conselho — em 1 hook (observacional)",
                 font=("Segoe UI", 9), fg=MUTED, bg=BG).pack(pady=(2, 0))

        card = tk.Frame(self.root, bg=CARD)
        card.pack(fill="both", expand=True, padx=22, pady=12)
        for key, label in self.STEPS:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=16, pady=7)
            dot = tk.Label(row, text="•", font=("Segoe UI", 14, "bold"),
                           fg=MUTED, bg=CARD, width=2)
            dot.pack(side="left")
            name = tk.Label(row, text=label, font=("Segoe UI", 11),
                            fg=FG, bg=CARD, anchor="w")
            name.pack(side="left")
            info = tk.Label(row, text="aguarde…", font=("Segoe UI", 9),
                            fg=MUTED, bg=CARD, anchor="e")
            info.pack(side="right")
            self.rows[key] = (dot, info)

        # ── CONFIGURAÇÃO da HUD (lida pelo overlay ao vivo) ──
        cfg = tk.Frame(self.root, bg=BG)
        cfg.pack(fill="x", padx=24, pady=(2, 2))
        tk.Label(cfg, text="CONFIGURAÇÃO DA HUD", font=("Segoe UI", 8, "bold"),
                 fg=MUTED, bg=BG, anchor="w").pack(fill="x")
        self.lock_hud = tk.BooleanVar(value=os.path.exists(_LOCK_FILE))
        tk.Checkbutton(cfg, text="Fixar HUD (trava a posição; segue a mesa ao mover)",
                       variable=self.lock_hud, command=self._toggle_lock,
                       bg=BG, fg=FG, selectcolor=CARD, activebackground=BG,
                       activeforeground=GOLD, font=("Segoe UI", 10), anchor="w",
                       bd=0, highlightthickness=0, cursor="hand2").pack(anchor="w", pady=(1, 2))
        self.show_hero = tk.BooleanVar(value=not os.path.exists(_HIDE_HERO_FILE))
        tk.Checkbutton(cfg, text="Mostrar a minha HUD (Hero) na mesa",
                       variable=self.show_hero, command=self._toggle_hero,
                       bg=BG, fg=FG, selectcolor=CARD, activebackground=BG,
                       activeforeground=GOLD, font=("Segoe UI", 10), anchor="w",
                       bd=0, highlightthickness=0, cursor="hand2").pack(anchor="w", pady=(1, 2))
        srow = tk.Frame(cfg, bg=BG)
        srow.pack(fill="x")
        tk.Label(srow, text="Opacidade", font=("Segoe UI", 10), fg=FG, bg=BG).pack(side="left")
        self.alpha_val = tk.IntVar(value=_read_alpha_pct())
        tk.Scale(srow, from_=20, to=100, orient="horizontal", variable=self.alpha_val,
                 command=self._set_alpha, bg=BG, fg=MUTED, troughcolor=CARD,
                 highlightthickness=0, bd=0, sliderrelief="flat", length=300,
                 font=("Segoe UI", 7)).pack(side="right", fill="x", expand=True, padx=(8, 0))

        self.foot = tk.Label(self.root, text="iniciando…", font=("Segoe UI", 10, "bold"),
                             fg=GOLD, bg=BG)
        self.foot.pack(pady=(4, 6))
        self.btn = tk.Button(self.root, text="Parar tudo", font=("Segoe UI", 11, "bold"),
                             fg=BG, bg=GOLD, activebackground=GREEN, relief="flat",
                             cursor="hand2", command=self._quit, padx=18, pady=7)
        self.btn.pack(pady=(0, 16))

    def _set(self, key, state, info=None):
        dot, lbl = self.rows[key]
        color = {"wait": MUTED, "ok": GREEN, "skip": GOLD, "err": RED}.get(state, MUTED)
        mark = {"wait": "•", "ok": "✓", "skip": "—", "err": "✗"}.get(state, "•")
        dot.config(text=mark, fg=color)
        if info is not None:
            lbl.config(text=info, fg=(FG if state == "ok" else color if state == "err" else MUTED))
        self.root.update_idletasks()

    # ── config da HUD: escreve os flags que o overlay lê a cada ciclo (efeito em ~3s) ──
    def _toggle_lock(self):
        try:
            os.makedirs(_NVTDIR, exist_ok=True)
            if self.lock_hud.get():
                open(_LOCK_FILE, "w").close()          # fixa: não arrasta (segue a mesa)
            elif os.path.exists(_LOCK_FILE):
                os.remove(_LOCK_FILE)                  # solta: pode arrastar p/ reposicionar
        except Exception:
            pass

    def _toggle_hero(self):
        try:
            os.makedirs(_NVTDIR, exist_ok=True)
            if self.show_hero.get():
                if os.path.exists(_HIDE_HERO_FILE):
                    os.remove(_HIDE_HERO_FILE)
            else:
                open(_HIDE_HERO_FILE, "w").close()
        except Exception:
            pass

    def _set_alpha(self, v):
        try:
            os.makedirs(_NVTDIR, exist_ok=True)
            tmp = _ALPHA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("%.2f" % (max(20, min(100, int(float(v)))) / 100.0))
            os.replace(tmp, _ALPHA_FILE)
        except Exception:
            pass

    def _spawn(self, name, cmd, cwd, env, group=False):
        cf = NO_WINDOW | (NEW_GROUP if group else 0)
        logdir = os.path.join(REPO, "logs")
        os.makedirs(logdir, exist_ok=True)
        try:
            lf = open(os.path.join(logdir, "suprema_%s.log" % name), "w",
                      encoding="utf-8", errors="replace")
            self.logs.append(lf)
            p = subprocess.Popen(cmd, cwd=cwd, env=env, creationflags=cf,
                                 stdout=lf, stderr=subprocess.STDOUT)
        except Exception as e:
            return None, str(e)
        self.procs.append((name, p))
        return p, None

    def _bringup(self):
        tk = self.tk
        # 1) cliente aberto?
        self._set("suprema", "wait", "procurando…")
        if not _suprema_running():
            self._set("suprema", "err", "não encontrada")
            for k, _ in self.STEPS[1:]:
                self._set(k, "skip", "—")
            self.foot.config(text="Abra a Suprema (numa mesa) e inicie de novo.", fg=RED)
            self.btn.config(text="Fechar")
            return
        self._set("suprema", "ok", "no ar")

        # 2) limpeza de hooks órfãos (libera a trava de hook único)
        self._set("limpeza", "wait", "liberando hook…")
        killed = _cleanup_stale()
        self._set("limpeza", "ok", ("%d órfão(s)" % len(killed)) if killed else "limpo")

        base = _live_base()
        hud_dir = os.path.join(base, "_live_suprema")
        os.makedirs(hud_dir, exist_ok=True)
        raw_dir = os.path.join(REPO, "logs", "suprema_raw")
        os.makedirs(raw_dir, exist_ok=True)
        rawfile = os.path.join(raw_dir, "suprema_%s.jsonl" % datetime.now().strftime("%Y-%m-%d"))
        dsn = _resolve_dsn()
        member = _live_member(dsn)
        py = _find_python()
        tourney = "suprema_%s" % datetime.now().strftime("%Y-%m-%d")
        env = dict(os.environ, NVT_PARENT_PID=str(os.getpid()))
        if dsn:
            env["NVT_DATABASE_URL"] = dsn
        env["PYTHONPATH"] = TRACKER_ROOT + os.pathsep + env.get("PYTHONPATH", "")

        # 3) CAPTURADOR UNIFICADO (1 hook: dados + .txt + HUD + conselho). Grupo próprio p/ CTRL_BREAK.
        self._set("captura", "wait", "anexando…")
        p, err = self._spawn(
            "captura",
            [py, "-I", "-u", "capturar_suprema_net.py", "--base", base,
             "--hud-dir", hud_dir, "--tournament", tourney, "--advise",
             "--dump-raw", rawfile],
            cwd=REPO, env=env, group=True)
        self._set("captura", "ok" if p else "err", "1 hook no ar" if p else (err or "falhou"))

        # 4) WATCHER (ingere .txt -> banco). Só com membro e se nenhum já roda.
        self._set("watcher", "wait", "verificando…")
        if member and dsn and not _proc_has("nvt-watch"):
            p, err = self._spawn(
                "watcher",
                [py, "-u", "-m", "nvttracker.cli", "nvt-watch", base, "--member", member,
                 "--poll", "1", "--debounce", "1", "--rescan", "8"],
                cwd=TRACKER_ROOT, env=env)
            self._set("watcher", "ok" if p else "err",
                      ("membro %s" % member) if p else (err or "falhou"))
        elif _proc_has("nvt-watch"):
            self._set("watcher", "ok", "já rodando (reaproveitado)")
        else:
            self._set("watcher", "skip", "sem membro/DSN (.txt guardado)")

        # 5) HUD OVERLAY (--live-only: só mesa ao vivo; nunca inventa mesa do banco).
        self._set("hud", "wait", "abrindo…")
        if dsn:
            p, err = self._spawn(
                "hud",
                [py, "-u", "-m", "nvttracker.viz.hud_overlay", "--process", "suprema",
                 "--layout", "suprema", "--live-only", "--live-dir", hud_dir,
                 "--minutes", "180", "--refresh", "3"],
                cwd=TRACKER_ROOT, env=env)
            self._set("hud", "ok" if p else "err", "9 assentos" if p else (err or "falhou"))
        else:
            self._set("hud", "skip", "sem DSN p/ stats")

        up = len([1 for _n, pr in self.procs if pr.poll() is None])
        self.foot.config(text="● NO AR — %d componentes. Jogue; eu mostro a HUD e o conselho." % up,
                         fg=GREEN)
        self.root.after(1500, self._monitor)

    def _monitor(self):
        alive = [n for n, p in self.procs if p.poll() is None]
        if self.procs and not alive:
            self.foot.config(text="Todos os processos encerraram.", fg=MUTED)
            self.btn.config(text="Fechar")
            return
        if "captura" in [n for n, p in self.procs if p.poll() is not None]:
            self._set("captura", "err", "encerrou")
        self.root.after(1500, self._monitor)

    def _quit(self):
        self.foot.config(text="Parando (detach limpo do Frida)…", fg=GOLD)
        self.btn.config(state="disabled")
        self.root.update_idletasks()
        _shutdown(self.procs)
        for lf in self.logs:
            try:
                lf.close()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def run(self):
        self.root.mainloop()


def _shutdown(procs):
    """Encerra sem derrubar a Suprema: o CAPTURADOR (host Frida) recebe CTRL_BREAK -> unload+detach
    LIMPO; espera ele sair; o resto leva terminate."""
    brk = getattr(signal, "CTRL_BREAK_EVENT", None)
    cap = [(n, p) for n, p in procs if n == "captura"]
    for _n, p in cap:
        try:
            if p.poll() is None and brk is not None:
                p.send_signal(brk)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass
    deadline = time.time() + 8
    for _n, p in cap:
        try:
            p.wait(timeout=max(0.2, deadline - time.time()))
        except Exception:
            pass
    for n, p in procs:
        if (n, p) in cap:
            continue
        try:
            p.terminate()
        except Exception:
            pass


def main():
    _ensure_no_console()          # R2: nunca CMD ao fundo (re-exec sob pythonw se preciso)
    _ensure_desktop_shortcut()    # R1: atalho na Área de Trabalho
    try:
        Wizard().run()
    except Exception:
        # sem GUI (sem tkinter?): degrada p/ modo silencioso, ainda sem console visível
        _fallback_headless()


def _fallback_headless():
    if not _suprema_running():
        return
    _cleanup_stale()
    base = _live_base()
    hud_dir = os.path.join(base, "_live_suprema")
    os.makedirs(hud_dir, exist_ok=True)
    raw_dir = os.path.join(REPO, "logs", "suprema_raw")
    os.makedirs(raw_dir, exist_ok=True)
    rawfile = os.path.join(raw_dir, "suprema_%s.jsonl" % datetime.now().strftime("%Y-%m-%d"))
    dsn = _resolve_dsn()
    member = _live_member(dsn)
    py = _find_python()
    tourney = "suprema_%s" % datetime.now().strftime("%Y-%m-%d")
    env = dict(os.environ, NVT_PARENT_PID=str(os.getpid()))
    if dsn:
        env["NVT_DATABASE_URL"] = dsn
    env["PYTHONPATH"] = TRACKER_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    logdir = os.path.join(REPO, "logs")
    os.makedirs(logdir, exist_ok=True)
    procs = []

    def sp(name, cmd, cwd, group=False):
        cf = NO_WINDOW | (NEW_GROUP if group else 0)
        lf = open(os.path.join(logdir, "suprema_%s.log" % name), "w", encoding="utf-8", errors="replace")
        p = subprocess.Popen(cmd, cwd=cwd, env=env, creationflags=cf, stdout=lf, stderr=subprocess.STDOUT)
        procs.append((name, p))
    sp("captura", [py, "-I", "-u", "capturar_suprema_net.py", "--base", base, "--hud-dir", hud_dir,
                   "--tournament", tourney, "--advise", "--dump-raw", rawfile], REPO, group=True)
    if member and dsn and not _proc_has("nvt-watch"):
        sp("watcher", [py, "-u", "-m", "nvttracker.cli", "nvt-watch", base, "--member", member,
                       "--poll", "1", "--debounce", "1", "--rescan", "8"], TRACKER_ROOT)
    if dsn:
        sp("hud", [py, "-u", "-m", "nvttracker.viz.hud_overlay", "--process", "suprema",
                   "--layout", "suprema", "--live-only", "--live-dir", hud_dir,
                   "--minutes", "180", "--refresh", "3"], TRACKER_ROOT)
    try:
        while [n for n, p in procs if p.poll() is None]:
            time.sleep(2)
    finally:
        _shutdown(procs)


if __name__ == "__main__":
    main()
