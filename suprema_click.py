"""Fase 2 (execução) da SUPREMA — EXECUTOR de clique (gated, DPI-aware).

Liga o PLANO do suprema_act (action, chips, preset) ao CLIQUE nos botões da Suprema. A
decisão de QUE fazer já vem pronta e gated pelas ações legais do prompt; aqui é só o COMO:
mover o cursor e clicar o botão certo (ação externa, nunca injeção de rede — nvt-hotkeys-politica).

COORDENADAS: a barra de ação fica no RODAPÉ da janela (recon de UI 20/11: vi 'Apostar'(Bet),
'Aumentar'(Raise), botão verde Check, controle de aposta BB/+/slider). O layout aqui é
RELATIVO À JANELA (frações 0..1 do client), p/ sobreviver a resize; os valores sao um ponto
de partida A CALIBRAR com uma captura limpa (suprema_calibrar). Multi-monitor + DPI: as frações
viram coords de TELA via ClientToScreen com o processo DPI-aware (coords físicas).

SEGURANÇA: por padrão DRY-RUN (só calcula e loga o alvo); só clica com armed=True. Nunca
clica uma ação fora de `plan` nem sem alvo. O resolve_target é testável offline (sem clicar).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

import suprema_act as A

# Layout RELATIVO ao client (fx, fy em 0..1). CALIBRADO 20/11 numa captura LIMPA DPI-aware
# (922x1657). Barra inferior com 3 botoes: 'Desistir'(Fold) esq, 'Pagar'/'Passar'(Call/Check)
# centro, 'Aumentar'/'Apostar'(Raise/Bet) dir (laranja). Fracoes sobrevivem a resize.
BUTTON_LAYOUT = {
    A.FOLD:   (0.185, 0.950),     # "Desistir"
    A.CHECK:  (0.500, 0.950),     # "Passar" (= Pagar quando ha aposta)
    A.CALL:   (0.500, 0.950),     # "Pagar X BB"
    A.RAISE:  (0.815, 0.950),     # "Aumentar"/"Apostar"
    A.ALL_IN: (0.815, 0.950),     # via painel de aumento no MAXIMO (ver PRESET_LAYOUT/TODO)
}
# Painel de size do raise (quando 'Aumentar' abre o slider): A CALIBRAR com 1 captura do painel
# aberto. Controles vistos no rodapé: toggle verde "BB" + "+" (lado direito, ~x0.9). Placeholder.
PRESET_LAYOUT = {
    '2X': (0.30, 0.86), '3X': (0.50, 0.86), '4X': (0.70, 0.86),
    'confirm': (0.815, 0.950),    # 'Aumentar' confirma apos ajustar o size
    'plus': (0.90, 0.880), 'bb_toggle': (0.90, 0.810),
}
_CALIBRATED = True                # botoes principais calibrados; painel de size pendente


def set_dpi_aware():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # PER_MONITOR_V2
        return True
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return True
        except Exception:
            return False


def client_rect_screen(hwnd):
    """(left, top, width, height) do CLIENT em coords de TELA (físicas, se DPI-aware)."""
    u = ctypes.windll.user32
    r = wt.RECT(); u.GetClientRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    pt = wt.POINT(0, 0); u.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, w, h


def frac_to_screen(hwnd, fx, fy):
    left, top, w, h = client_rect_screen(hwnd)
    return int(left + fx * w), int(top + fy * h)


def resolve_target(plan, layout=None):
    """(action, (fx, fy)) do botão a clicar p/ o plano, ou (action, None) se não há alvo.
    TESTÁVEL offline (não toca em janela). `plan` = saída de suprema_act.plan_action."""
    layout = layout or BUTTON_LAYOUT
    act = (plan or {}).get('action')
    if act in (A.WAIT, A.ABSTAIN, None):
        return act, None
    return act, layout.get(act)


def execute(plan, hwnd, *, armed=False, mover=None):
    """Executa o plano na janela. DRY-RUN por padrão (armed=False: só resolve+loga). Com
    armed=True, move e clica via `mover(x,y)` (injeta p/ testar; default = SendInput real).
    Devolve dict {action, screen?, clicked, reason}."""
    act, frac = resolve_target(plan)
    if frac is None:
        return dict(action=act, clicked=False, reason='SEM_ALVO:%s' % act)
    x, y = frac_to_screen(hwnd, *frac)
    if not armed:
        return dict(action=act, screen=(x, y), clicked=False, reason='DRY_RUN')
    (mover or _click_sendinput)(x, y)
    # RAISE: além de clicar o botao de aumentar, aqui entraria o ajuste de size (preset/slider
    # + confirmar). Mantido como passo seguinte da calibracao (precisa do painel de aumento real).
    return dict(action=act, screen=(x, y), clicked=True, reason='CLICOU')


def _click_sendinput(x, y):
    """Move o cursor p/ (x,y) em coords de TELA e clica (SendInput). Reusa o controlador de
    cursor do PPPoker se disponível (trajetória min-jerk); senão, SendInput direto."""
    try:
        from cursor_input_win import move_to, click    # mesmo input do PPPoker
        move_to(x, y); click()
        return
    except Exception:
        pass
    u = ctypes.windll.user32
    u.SetCursorPos(int(x), int(y))
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
    u.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    u.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
