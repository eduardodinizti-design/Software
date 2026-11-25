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
# Painel de size do raise (abre ao clicar 'Aumentar'): CALIBRADO 20/11 numa captura do painel
# ABERTO (870x1564). Barra inferior vira presets: 2X/3X/4X/All In + 'Confirmar'(laranja);
# slider a direita com +/- p/ ajuste fino.
PRESET_LAYOUT = {
    '2X': (0.101, 0.949), '3X': (0.261, 0.949), '4X': (0.420, 0.949),
    # PÓS-FLOP (painel de APOSTA, botão 'Apostar'): presets de POTE. CALIBRADO AO VIVO 22/11
    # (captura 937x1666 do painel aberto): 1/2 POT/2/3 POT/1 POT em fx 0.092/0.255/0.419 @ fy 0.956;
    # All In e Confirmar coincidem com o painel de raise (0.583 / 0.816).
    '1/2 POT': (0.092, 0.956), '2/3 POT': (0.255, 0.956), '1 POT': (0.419, 0.956),
    'all_in': (0.583, 0.949),     # "All In 128.3 BB"
    'confirm': (0.816, 0.949),    # "Confirmar" (laranja)
    'plus': (0.618, 0.650), 'minus': (0.618, 0.724),   # ajuste fino do slider
}
_CALIBRATED = True                # botoes principais E painel de size calibrados+validados

# MODO DE CLIQUE p/ MULTI-TABLE (Eduardo 22/11: joga outras telas; o SendInput PUXA o cursor
# fisico compartilhado -> colide). SUPREMA_CLICK_BG=True faz TODA a sequencia sair por
# PostMessage DIRETO no hwnd (cursor fica PARADO onde o Eduardo esta). Default False = SendInput
# (caminho validado ao vivo). O param `background=` do execute() tem prioridade sobre este flag.
# INCERTEZA: cliente Cocos/GPU pode IGNORAR PostMessage sintetico (le so input de hardware) ->
# por isso o fallback `restore_cursor=True` (SendInput que devolve o cursor ao lugar logo apos).
SUPREMA_CLICK_BG = False

# mensagens de mouse Win32
_WM_MOUSEMOVE, _WM_LBUTTONDOWN, _WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
_MK_LBUTTON = 0x0001


def _make_lparam(x, y):
    """lParam de msg de mouse: (y<<16)|(x&0xFFFF), coords de CLIENTE. PURO/TESTAVEL."""
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


def _frac_to_client_wh(fx, fy, w, h):
    """Fracao -> coord de CLIENTE (relativa ao canto 0,0 do client, SEM offset de tela). PURO."""
    return int(fx * w), int(fy * h)


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


TABLE_ASPECT = 0.5625   # mesa RETRATO 9:16 (medido nas capturas só-mesa: 849x1509, 1141x2029...)


def table_rect_screen(hwnd):
    """(left, top, w, h) da MESA em coords de TELA. A Suprema cola o LOBBY/grind à ESQUERDA da
    mesa quando aberto (janela fica larga); a MESA é um retrato ancorado à DIREITA, de largura
    altura*TABLE_ASPECT. Em modo retrato (só mesa) isso = o client inteiro (sem mudança). Assim
    o clique nunca cai no Lobby (bug 22/11: fold 0.185*clientW caía dentro do Lobby)."""
    left, top, w, h = client_rect_screen(hwnd)
    tw = min(w, int(round(h * TABLE_ASPECT)))
    return left + (w - tw), top, tw, h


def frac_to_screen(hwnd, fx, fy):
    # frações são relativas à MESA (não ao client) -> robusto ao Lobby grudado à esquerda.
    left, top, w, h = table_rect_screen(hwnd)
    return int(left + fx * w), int(top + fy * h)


def _tile_rect(left, top, w, h, room_index, n_rooms, aspect=TABLE_ASPECT):
    """PURO/TESTÁVEL. Região (x, y, tw, th) em coords de TELA da MESA `room_index` (0-based)
    de `n_rooms` TILADAS dentro de um client (left, top, w, h).

    A Suprema tila N mesas LADO A LADO numa única janela OS (confirmado pela aritmética do
    client multi-mesa ~1249x1110: 1249/2 = 624.5 e 624.5/1110 = 0.5626 ≈ TABLE_ASPECT, i.e.
    cada metade é EXATAMENTE um retrato 9:16). Cada mesa = uma COLUNA de largura w/n; dentro
    da coluna a mesa é o retrato (largura th*aspect) CENTRADO — se a coluna já é retrato (caso
    2 mesas), tw==coluna e não há deslocamento.

    n_rooms<=1 cai no modo de 1 mesa = `table_rect_screen` (retrato ancorado à DIREITA, p/ o
    modo Lobby+mesa com o Lobby colado à esquerda — ver nvt-suprema-lobby-mesa-clique)."""
    n = max(1, int(n_rooms))
    i = max(0, min(int(room_index), n - 1))
    if n == 1:
        tw = min(w, int(round(h * aspect)))
        return left + (w - tw), top, tw, h          # 1 mesa: ancora à DIREITA (idem table_rect_screen)
    cell_w = w / n
    cell_left = left + i * cell_w
    tw = min(int(round(cell_w)), int(round(h * aspect)))
    tx = int(round(cell_left + (cell_w - tw) / 2.0))  # retrato CENTRADO na coluna
    return tx, top, tw, h


def table_rect_for_room(hwnd, room_index, n_rooms):
    """(left, top, w, h) em coords de TELA da MESA `room_index` de `n_rooms` tiladas na janela.
    A camada multi-mesa (suprema_agente) mapeia roomID -> room_index (ordem ESTÁVEL) e usa isto
    p/ clicar na mesa CERTA. n_rooms<=1 == comportamento atual de 1 mesa."""
    left, top, w, h = client_rect_screen(hwnd)
    return _tile_rect(left, top, w, h, room_index, n_rooms)


def frac_to_screen_room(hwnd, fx, fy, room_index, n_rooms):
    """Fração (relativa à MESA) -> coord de TELA, para a mesa `room_index` de `n_rooms` tiladas.
    Com n_rooms<=1 DELEGA a frac_to_screen (1 mesa) — mantém o mesmo ponto de injeção/comportamento."""
    if int(n_rooms) <= 1:
        return frac_to_screen(hwnd, fx, fy)
    x, y, w, h = table_rect_for_room(hwnd, room_index, n_rooms)
    return int(x + fx * w), int(y + fy * h)


def client_wh(hwnd):
    """(width, height) do CLIENT (sem offset de tela)."""
    u = ctypes.windll.user32
    r = wt.RECT(); u.GetClientRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def frac_to_client(hwnd, fx, fy):
    """Fracao -> coord de CLIENTE (p/ PostMessage: lParam quer coords RELATIVAS a janela)."""
    w, h = client_wh(hwnd)
    return _frac_to_client_wh(fx, fy, w, h)


def frac_to_client_room(hwnd, fx, fy, room_index, n_rooms):
    """Fração (relativa à MESA) -> coord de CLIENTE da mesa `room_index` de `n_rooms` tiladas,
    p/ o clique em BACKGROUND (PostMessage quer coords relativas à JANELA). Com n_rooms<=1
    DELEGA a frac_to_client. Deriva a célula da mesa SEM o offset de tela (usa client 0,0)."""
    if int(n_rooms) <= 1:
        return frac_to_client(hwnd, fx, fy)
    w, h = client_wh(hwnd)
    x, y, tw, th = _tile_rect(0, 0, w, h, room_index, n_rooms)
    return int(x + fx * tw), int(y + fy * th)


def columns_from_size(w, h, aspect=TABLE_ASPECT):
    """PURA/TESTÁVEL. Número de mesas TILADAS (colunas) deduzido do TAMANHO do client:
    round(w / (h*aspect)), clamp >=1. É a VERDADE-TERRENO de quantas colunas a janela tem.

    Cada mesa é um retrato de largura h*aspect; N lado a lado => w ≈ N*(h*aspect), logo
    N = w/(h*aspect). Exemplos: 1470x1307 -> 1470/735≈2.0 -> 2; 849x1509 -> ~1.0 -> 1;
    2940x1307 -> ~4.0 -> 4. Degenerado (h<=0, aspect<=0, não-numérico) => 1.

    LIMITAÇÃO: é uma dedução por TAMANHO; assume a janela = N retratos lado a lado SEM Lobby
    grudado. No modo Lobby+mesa (1 mesa) a janela fica larga e esta função superestimaria (a
    camada multi-mesa só deve consultá-la quando está em grade tilada, não com o Lobby aberto)."""
    try:
        col_w = float(h) * float(aspect)
        if col_w <= 0:
            return 1
        n = int(round(float(w) / col_w))
    except (TypeError, ValueError, ZeroDivisionError):
        return 1
    return max(1, n)


def columns_from_window(hwnd):
    """Wrapper: lê o CLIENT (w,h) do hwnd e deduz o nº de colunas tiladas via columns_from_size.
    Devolve >=1 sempre; em falha de leitura (client 0x0) cai no degenerado = 1 mesa."""
    w, h = client_wh(hwnd)
    return columns_from_size(w, h)


def resolve_target(plan, layout=None):
    """(action, (fx, fy)) do botão único p/ fold/check/call, ou (action, None). TESTÁVEL."""
    layout = layout or BUTTON_LAYOUT
    act = (plan or {}).get('action')
    if act in (A.WAIT, A.ABSTAIN, None):
        return act, None
    return act, layout.get(act)


def build_sequence(plan):
    """Sequência de frações (fx,fy) a clicar EM ORDEM p/ o plano. Fold/Check/Call = 1 clique.
    RAISE = Aumentar(abre painel) -> preset(2X/3X/4X) -> Confirmar. ALL_IN = Aumentar -> All In
    -> Confirmar. TESTÁVEL offline (puro)."""
    act = (plan or {}).get('action')
    if act in (A.FOLD, A.CHECK, A.CALL):
        f = BUTTON_LAYOUT.get(act)
        return [f] if f else []
    if act == A.RAISE:
        seq = [BUTTON_LAYOUT[A.RAISE]]                 # 'Aumentar' abre o painel de size
        preset = (plan or {}).get('preset')
        if preset and preset in PRESET_LAYOUT:
            seq.append(PRESET_LAYOUT[preset])          # escolhe o preset (2X/3X/4X)
        seq.append(PRESET_LAYOUT['confirm'])           # Confirmar
        return seq
    if act == A.ALL_IN:
        return [BUTTON_LAYOUT[A.RAISE], PRESET_LAYOUT['all_in'], PRESET_LAYOUT['confirm']]
    return []


def execute(plan, hwnd, *, armed=False, mover=None, sleeper=None, step_delay=0.5,
            panel_delay=0.5, background=None, restore_cursor=False, room_index=0, n_rooms=1):
    """Executa o plano na janela. DRY-RUN por padrão (armed=False: só resolve a sequência de
    coords e loga). armed=True clica cada passo com `step_delay` entre eles (deixa o painel de
    size renderizar).

    MODO DE CLIQUE:
      - default (SendInput): move o CURSOR FÍSICO e clica em coords de TELA. `restore_cursor=True`
        devolve o cursor à posição anterior logo após cada clique (minimiza perturbação quando o
        Eduardo multi-tabla). Devolve {action, screen:[...], clicked, reason}.
      - background (`background=True`, ou o flag de módulo SUPREMA_CLICK_BG): posta WM_* DIRETO no
        hwnd em coords de CLIENTE, SEM mexer no cursor. Devolve {action, client:[...], mode:'bg',
        clicked, reason}. INCERTO em Cocos/GPU (pode ser ignorado) — validar ao vivo.

    `mover(x,y)` injeta um clicker (p/ teste): recebe coords de TELA no default, de CLIENTE no bg.
    """
    import time as _t
    act = (plan or {}).get('action')
    seq = build_sequence(plan)
    if not seq:
        return dict(action=act, clicked=False, reason='SEM_ALVO:%s' % act)
    bg = SUPREMA_CLICK_BG if background is None else bool(background)
    if bg:
        clients = [frac_to_client_room(hwnd, fx, fy, room_index, n_rooms) for (fx, fy) in seq]
        if not armed:
            return dict(action=act, client=clients, mode='bg', clicked=False, reason='DRY_RUN')
        for i, (cx, cy) in enumerate(clients):
            (mover(cx, cy) if mover is not None else _click_postmessage(hwnd, cx, cy))
            if i < len(clients) - 1:
                # após 'Aumentar'/'Apostar' (1º de uma sequência) o PAINEL de size precisa RENDERIZAR
                # antes do clique do preset -> espera MAIS (senão o preset cai no vazio = zig-zag / size
                # errado / all-in acidental = bust). Eduardo 23/11.
                (sleeper or _t.sleep)(panel_delay if (i == 0 and len(clients) > 1) else step_delay)
        return dict(action=act, client=clients, mode='bg', clicked=True, reason='CLICOU')
    # DEFAULT: SendInput (cursor físico). Dict IDÊNTICO ao histórico (não quebra chamadores).
    # room_index/n_rooms default (0,1) -> frac_to_screen_room == frac_to_screen (1 mesa).
    screens = [frac_to_screen_room(hwnd, fx, fy, room_index, n_rooms) for (fx, fy) in seq]
    if not armed:
        return dict(action=act, screen=screens, clicked=False, reason='DRY_RUN')
    click_fn = mover or (_click_sendinput_restore if restore_cursor else _click_sendinput)
    for i, (x, y) in enumerate(screens):
        click_fn(x, y)
        if i < len(screens) - 1:
            # após 'Aumentar'/'Apostar' (1º de uma sequência) o PAINEL de size precisa RENDERIZAR antes
            # do clique do preset -> espera MAIS (senão o preset cai no vazio = zig-zag / size errado /
            # all-in acidental = bust). Eduardo 23/11. Fold/call/check = 1 clique, sem espera.
            (sleeper or _t.sleep)(panel_delay if (i == 0 and len(screens) > 1) else step_delay)
    return dict(action=act, screen=screens, clicked=True, reason='CLICOU')


_SMOOTH = None   # (WindowsCursorInput, TrajectoryGenerator) cacheados


def _smooth_cursor():
    global _SMOOTH
    if _SMOOTH is None:
        from cursor_input_win import WindowsCursorInput
        from cursor_trajectory import TrajectoryGenerator
        _SMOOTH = (WindowsCursorInput(), TrajectoryGenerator())
    return _SMOOTH


def _click_sendinput(x, y):
    """Move o cursor em CURVA SUAVE (min-jerk + Bézier, MESMO padrão do PPPoker: TrajectoryGenerator
    + WindowsCursorInput) ate (x,y) e clica. O movimento/HOVER real faz o botao REGISTRAR — o
    teleporte seco (SetCursorPos) nao ativava o preset do painel (apostava o minimo) e deixava o
    cursor PULANDO na tela. Fallback: SetCursorPos+mouse_event se o controlador suave falhar."""
    import time as _t
    try:
        adapter, tg = _smooth_cursor()
        try:
            cur = adapter.cursor_pos()
            sx, sy = cur if isinstance(cur, (tuple, list)) else (cur["x"], cur["y"])
        except Exception:
            sx, sy = x, y
        plan = tg.plan((float(sx), float(sy)), (float(x), float(y)))
        t_end = _t.monotonic() + max(0.12, float(getattr(plan, "duration_s", 0.25)) + 0.03)
        while _t.monotonic() < t_end and not plan.done(_t.monotonic()):
            px, py = plan.point_at(plan.progress(_t.monotonic()))
            adapter.move_to(int(round(px)), int(round(py)))
            _t.sleep(0.008)
        adapter.move_to(int(x), int(y))     # ponto final EXATO
        _t.sleep(0.04)                       # assenta (hover) antes de clicar -> botao ativa
        adapter.click_once(int(x), int(y))
        return
    except Exception:
        pass
    u = ctypes.windll.user32              # fallback: teleporte (ultimo recurso)
    u.SetCursorPos(int(x), int(y))
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
    u.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    u.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _click_sendinput_restore(x, y):
    """SendInput normal, mas DEVOLVE o cursor à posição anterior logo após clicar — plano B pro
    multi-table quando o PostMessage (background) não pega: perturba o cursor do Eduardo só por
    um instante. NÃO elimina a colisão (há uma janela de ~ms com o cursor movido), só reduz."""
    u = ctypes.windll.user32
    prev = wt.POINT()
    try:
        u.GetCursorPos(ctypes.byref(prev))
        had = True
    except Exception:
        had = False
    _click_sendinput(x, y)
    if had:
        try:
            u.SetCursorPos(int(prev.x), int(prev.y))
        except Exception:
            pass


def _click_postmessage(hwnd, cx, cy):
    """CLIQUE EM BACKGROUND: posta WM_MOUSEMOVE + WM_LBUTTONDOWN + WM_LBUTTONUP DIRETO no hwnd,
    em coords de CLIENTE, SEM mover o cursor físico (não perturba as outras telas do Eduardo).
    PostMessage é assíncrono/não-bloqueante. INCERTO em Cocos/GPU: muitos jogos ignoram input
    sintético (só leem hardware real) — por isso validar ao vivo e ter o fallback restore."""
    u = ctypes.windll.user32
    lp = _make_lparam(cx, cy)
    u.PostMessageW(wt.HWND(hwnd), _WM_MOUSEMOVE, 0, lp)
    u.PostMessageW(wt.HWND(hwnd), _WM_LBUTTONDOWN, _MK_LBUTTON, lp)
    u.PostMessageW(wt.HWND(hwnd), _WM_LBUTTONUP, 0, lp)
