"""OPERADOR (execução gated) da SUPREMA — gate de 1º CLIQUE, espelha o 1º-Fold do PPPoker.

Amarra: suprema_net.run_live (1 hook READ-ONLY) -> SupremaTable -> advisor (make_on_state,
já com a trava anti-flicker _SpotGate: só decide em spot ESTÁVEL) -> suprema_act (PLANO) ->
suprema_click (clique EXTERNO via SendInput, nunca injeção — nvt-hotkeys-politica).

SEGURANÇA (camadas):
  1) DRY-RUN por padrão: mostra o PLANO e as COORDENADAS que clicaria; NÃO clica.
  2) --arm-fold arma UM ÚNICO clique, e SÓ de FOLD, e SÓ em spot estável: depois DESARMA
     (one-shot). FOLD é a ação mais segura (sem slider, sem fichas; e um fold de graça já
     vira CHECK no plan_action, então o gate só dispara num fold REAL enfrentando aposta).
  3) Nunca clica WAIT/ABSTAIN nem ação sem alvo. 1 mesa, play money.
Precisa do hook livre: se o Wizard (iniciar_suprema/capturar) estiver rodando, a trava de
instância única RECUSA este operador — pare o Wizard antes (botão "Parar tudo").

Uso:
    python -I suprema_operar.py --bb 1000                 # DRY-RUN: mostra PLANO + coords
    python -I suprema_operar.py --bb 1000 --arm-fold      # arma 1 clique de FOLD (one-shot)
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import suprema_act as A        # noqa: E402
import suprema_click as C      # noqa: E402


class FoldGate:
    """Gate de 1º clique. Só devolve 'click' quando: armado, ainda NÃO disparou, e o PLANO é
    FOLD. Qualquer outra ação -> 'dry' (só mostra). WAIT/ABSTAIN/sem-ação -> 'skip'. Após
    disparar, DESARMA (one-shot) — volta a dry-run p/ o Eduardo validar o 1º fold ao vivo."""

    def __init__(self, armed=False):
        self.armed = bool(armed)
        self.fired = False

    def decide(self, plan):
        act = (plan or {}).get('action')
        if act in (A.WAIT, A.ABSTAIN, None):
            return 'skip'
        if self.armed and not self.fired and act == A.FOLD:
            return 'click'
        return 'dry'

    def mark_fired(self):
        self.fired = True
        self.armed = False        # one-shot: desarma após o 1º clique


def find_suprema_hwnd(process='SupremaPoker.exe'):
    """HWND da janela PRINCIPAL (maior área de client) do processo da Suprema. None se não achar."""
    try:
        import psutil
        pids = {p.info['pid'] for p in psutil.process_iter(['pid', 'name'])
                if (p.info.get('name') or '').lower() == process.lower()}
    except Exception:
        pids = set()
    if not pids:
        return None
    u = ctypes.windll.user32
    best = {'hwnd': None, 'area': 0}
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def _cb(hwnd, _lp):
        if not u.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            r = wt.RECT()
            u.GetClientRect(hwnd, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            if area > best['area']:
                best['area'], best['hwnd'] = area, hwnd
        return True

    u.EnumWindows(WNDENUMPROC(_cb), 0)
    return best['hwnd']


def find_suprema_instances(process='SupremaPoker.exe'):
    """[(pid, hwnd), ...] — a janela PRINCIPAL (maior área) de CADA instância da Suprema. MULTI-CONTA
    (Eduardo 24/11): duas contas = duas instâncias = duas janelas, uma por PID. Cada agente mira uma."""
    try:
        import psutil
        pids = {p.info['pid'] for p in psutil.process_iter(['pid', 'name'])
                if (p.info.get('name') or '').lower() == process.lower()}
    except Exception:
        pids = set()
    if not pids:
        return []
    u = ctypes.windll.user32
    best = {}   # pid -> (area, hwnd)
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def _cb(hwnd, _lp):
        if not u.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            r = wt.RECT()
            u.GetClientRect(hwnd, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            cur = best.get(pid.value)
            if cur is None or area > cur[0]:
                best[pid.value] = (area, hwnd)
        return True

    u.EnumWindows(WNDENUMPROC(_cb), 0)
    return [(pid, hw) for pid, (ar, hw) in best.items() if hw]


def _fmt_coords(hwnd, plan):
    """Coordenadas de TELA que o plano clicaria (dry-run do executor), p/ o Eduardo validar."""
    try:
        dry = C.execute(plan, hwnd, armed=False)
        return dry.get('screen')
    except Exception as e:
        return 'erro:%s' % e


def make_operator(hwnd, gate, *, stats=None):
    """Callback `emit` p/ o make_on_state: mostra o PLANO + coords e, se o gate liberar, CLICA
    (uma vez, só fold). Reusa a trava de estabilidade do make_on_state (só chega aqui em spot
    estável)."""
    stats = stats if stats is not None else {}

    def emit(state, advice, plan, hero):
        from assistir_suprema import _fmt
        act = (plan or {}).get('action')
        coords = _fmt_coords(hwnd, plan)
        decision = gate.decide(plan)
        print("%s | ALVO=%s | gate=%s" % (_fmt(state, advice, plan, hero), coords, decision), flush=True)
        if decision == 'click':
            res = C.execute(plan, hwnd, armed=True)
            gate.mark_fired()
            stats['cliques'] = stats.get('cliques', 0) + 1
            print("[OPERADOR] >>> CLIQUE DE FOLD EXECUTADO (one-shot, desarmado agora): %s" % res,
                  flush=True)
            print("[OPERADOR] valide na tela se foi no botão 'Desistir'. Reanalise antes de rearmar.",
                  flush=True)

    return emit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bb", type=float, default=None, help="BB em fichas (stake da mesa)")
    ap.add_argument("--seconds", type=float, default=0.0, help="0 = roda até Ctrl+C")
    ap.add_argument("--mode", default="chip_ev")
    ap.add_argument("--stage", default="mid")
    ap.add_argument("--arm-fold", action="store_true",
                    help="ARMA 1 clique de FOLD (one-shot). Sem isso = DRY-RUN (só mostra).")
    ap.add_argument("--process", default="SupremaPoker.exe")
    args = ap.parse_args()

    C.set_dpi_aware()
    hwnd = find_suprema_hwnd(args.process)
    if not hwnd:
        print("[OPERADOR] não achei a janela da Suprema (%s aberta numa mesa?)." % args.process, flush=True)
        return
    left, top, w, h = C.client_rect_screen(hwnd)
    print("[OPERADOR] janela Suprema hwnd=%s client=%dx%d @ (%d,%d). calibrado=%s"
          % (hwnd, w, h, left, top, C._CALIBRATED), flush=True)
    print("[OPERADOR] %s. %s"
          % ("ARMADO p/ 1 FOLD (one-shot)" if args.arm_fold else "DRY-RUN (nenhum clique)",
             "Jogue; mostro o PLANO + as coords e, na 1ª vez de FOLD estável, clico 1x."
             if args.arm_fold else "Jogue; mostro o PLANO e ONDE eu clicaria (sem clicar)."), flush=True)

    from assistir_suprema import load_advisor, make_on_state
    import suprema_net

    advisor = load_advisor()
    gate = FoldGate(armed=args.arm_fold)
    stats = {}
    on_state = make_on_state(advisor, mode=args.mode, stage=args.stage,
                             emit=make_operator(hwnd, gate, stats=stats))
    suprema_net.run_live(bb_chips=args.bb, on_state=on_state, seconds=args.seconds)
    print("[OPERADOR] fim. cliques=%d" % stats.get('cliques', 0), flush=True)


if __name__ == "__main__":
    main()
