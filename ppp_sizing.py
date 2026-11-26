"""on_sizing do agente PPPoker: executa RAISE/BET multi-etapa REUSANDO os executores validados —
RaiseSequencer (pré-flop ×BB) e execute_postflop_bet (pós-flop por FRAÇÃO, já slot-based via
_GREEN_ORDER). Captura por ImageGrab (RGB), não BitBlt (que dá PRETO na janela Unity do PPPoker).
Cursor FÍSICO (adapter). Gated por control.execution_allowed() (DRY nunca clica).

LIMITE (ovo-galinha, honesto): o PAINEL de aposta (presets/slider/confirmar) só APARECE DEPOIS de
clicar Raise/Bet — então a detecção do painel no cliente 4K só dá p/ calibrar AO ARMAR o 1º Raise.
Este módulo entrega o DISPATCH + wiring (testado offline com os executores injetados); a calibração
viva do painel fica para o arme, por ordem do Eduardo [[nvt-regra-master-sem-autonomia]]."""
from __future__ import annotations

import ppp_grab


class ImageGrabEngine:
    """Interface mínima que execute_postflop_bet/_click_step usam: capture_frame(hwnd)->(frame,meta).
    Captura a REGIÃO da janela via ImageGrab (enxerga Unity/GPU; BitBlt dá preto)."""

    def __init__(self, rect, capture=None):
        self._rect = rect
        self._cap = capture or ppp_grab.imagegrab_capture_bgr   # executores leem em BGR

    def capture_frame(self, hwnd=None):
        f = self._cap(self._rect)
        return (f, {}) if f is not None else (None, {})


def street_is_postflop(entry):
    board = ((entry or {}).get('table') or {}).get('board') or []
    return len(board) >= 3


# Ordem dos presets ×BB do painel de RAISE do PPPoker, esquerda->direita (calibrado no frame real
# 25/11: 2× · 2.5× · 3× · 4×). O preset é escolhido por SLOT (posição), sem OCR do rótulo.
_RAISE_ORDER = (2.0, 2.5, 3.0, 4.0)


def pick_raise_preset(presets, target_mult, order=_RAISE_ORDER):
    """Escolhe o preset ×BB pelo SLOT (posição) que corresponde ao `target_mult`, sem depender do
    OCR do rótulo. `presets` = [{box,...}] já ordenados esquerda->direita (read_raise_panel).
    Devolve (preset, exato: bool) ou (None, False) se o multiplicador não casa a ordem conhecida.
    exato=False quando cai no preset mais próximo <= alvo (p/ o chamador decidir usar slider)."""
    if not presets or target_mult is None:
        return None, False
    known = list(order)[:len(presets)]
    try:
        tm = float(target_mult)
    except (TypeError, ValueError):
        return None, False
    if tm in known:
        return presets[known.index(tm)], True
    # não-exato: maior preset <= alvo (ex.: alvo 2.2 -> 2×), senão o menor
    le = [i for i, m in enumerate(known) if m <= tm]
    if le:
        return presets[le[-1]], False
    return presets[0], False


def execute_raise_preset(view, target_mult, *, adapter, open_box=None, capture_bgr=None,
                         read_panel=None, to_screen=None, settle_s=0.5, sleep=None, log=print):
    """Executa um RAISE ×BB OCR-free, multi-etapa:
      1) ABRE o painel clicando o botão "Aumentar" da linha de ação (`open_box`, coords do CROP);
      2) espera `settle_s` o painel renderizar; re-captura o CROP em BGR;
      3) read_raise_panel -> pick_raise_preset (por SLOT) -> clica o PRESET + o botão Raise.
    Mapeia box do CROP -> tela somando o `origin` da view (igual ao single-click). Injetável p/ teste.
    Abstém (não clica preset/confirm) se o painel não sai — nunca clica no escuro.
      view = {origin:(ox,oy), box:(ox,oy,cw,ch), window_rect, full_size}  (do grab que clicou Raise)
    Devolve {state: CLICKED_RAISE | NO_PANEL | NO_PRESET | NO_CONFIRM | NO_FRAME}."""
    import time as _time
    if capture_bgr is None:
        capture_bgr = ppp_grab.imagegrab_capture_bgr
    if read_panel is None:
        from raise_panel import read_raise_panel as read_panel
    if to_screen is None:
        from screen_coords import rect_frame_to_screen as to_screen
    sleep = sleep or _time.sleep
    ox, oy, cw, ch = view['box']

    def _click(box, label):
        bx, by, bw, bh = box
        sx, sy, sw, sh = to_screen((ox + bx, oy + by, bw, bh),
                                   window_rect=view['window_rect'], frame_size=view['full_size'])
        cx, cy = int(sx + sw / 2), int(sy + sh / 2)
        adapter.move_to(cx, cy)
        adapter.click_once(cx, cy)
        log('[raise] CLIQUE %s em (%d,%d)' % (label, cx, cy))
        return (cx, cy)

    if open_box is not None:               # 1) abre o painel (clica Aumentar na linha de ação)
        _click(open_box, 'abrir-painel(Aumentar)')
        sleep(settle_s)                    # 2) deixa o painel renderizar
    frame = capture_bgr(view['window_rect'])
    if frame is None:
        log('[raise] sem frame BGR'); return {'state': 'NO_FRAME'}
    crop = frame[oy:oy + ch, ox:ox + cw]
    panel = read_panel(crop, _ocr=lambda im: '')      # OCR neutralizado: slot/geometria
    if panel.get('status') != 'EXPERIMENTAL_RAISE_PANEL' or not panel.get('presets'):
        log('[raise] painel não reconhecido (%s) -> não clica preset' % panel.get('status'))
        return {'state': 'NO_PANEL'}
    preset, exato = pick_raise_preset(panel['presets'], target_mult)
    if preset is None:
        log('[raise] preset p/ %sx não resolvido -> não clica' % target_mult)
        return {'state': 'NO_PRESET'}
    confirm = panel.get('confirm')
    if not confirm:
        log('[raise] sem botão Raise (confirmar) -> não clica')
        return {'state': 'NO_CONFIRM'}
    xy_preset = _click(preset['box'], 'preset %sx%s' % (target_mult, '' if exato else '~'))
    xy_confirm = _click(confirm['box'], 'RAISE')
    return {'state': 'CLICKED_RAISE', 'mult': target_mult, 'exato': exato,
            'preset_xy': xy_preset, 'confirm_xy': xy_confirm}


def execute_raise_shove(view, *, adapter, open_box=None, capture_bgr=None, read_slider=None,
                        read_panel=None, to_screen=None, settle_s=0.5, sleep=None, log=print):
    """ALL-IN/SHOVE OCR-free: abre o painel (Aumentar) -> lê o SLIDER (read_raise_slider: handle +
    allin_to=topo do trilho) -> ARRASTA o handle até o topo (all-in) -> clica Raise (confirmar).
    Shove NÃO é preset ×BB: por isso usa o slider no MÁXIMO, não os botões 2×/3×. Injetável p/ teste.
    Abstém se o slider/confirmar não saem. Devolve {state: CLICKED_SHOVE | NO_SLIDER | NO_CONFIRM | NO_FRAME}."""
    import time as _time
    if capture_bgr is None:
        capture_bgr = ppp_grab.imagegrab_capture_bgr
    if read_slider is None:
        from raise_panel import read_raise_slider as read_slider
    if read_panel is None:
        from raise_panel import read_raise_panel as read_panel
    if to_screen is None:
        from screen_coords import rect_frame_to_screen as to_screen
    sleep = sleep or _time.sleep
    ox, oy, cw, ch = view['box']

    def _pt(px, py):                 # ponto no CROP -> ponto na TELA (centro)
        sx, sy, sw, sh = to_screen((ox + px, oy + py, 2, 2),
                                   window_rect=view['window_rect'], frame_size=view['full_size'])
        return int(sx + sw / 2), int(sy + sh / 2)

    def _click(box, label):
        bx, by, bw, bh = box
        cx, cy = _pt(bx + bw / 2, by + bh / 2)
        adapter.move_to(cx, cy)
        adapter.click_once(cx, cy)
        log('[shove] CLIQUE %s em (%d,%d)' % (label, cx, cy))
        return (cx, cy)

    if open_box is not None:
        _click(open_box, 'abrir-painel(Aumentar)')
        sleep(settle_s)
    frame = capture_bgr(view['window_rect'])
    if frame is None:
        log('[shove] sem frame BGR'); return {'state': 'NO_FRAME'}
    crop = frame[oy:oy + ch, ox:ox + cw]
    sl = read_slider(crop)
    if sl.get('status') != 'SLIDER_FOUND' or not sl.get('handle') or not sl.get('allin_to'):
        log('[shove] slider não reconhecido (%s) -> não clica' % sl.get('status'))
        return {'state': 'NO_SLIDER'}
    hc = sl['handle']['center']
    at = sl['allin_to']
    hx, hy = _pt(hc[0], hc[1])
    ax, ay = _pt(at[0], at[1])
    adapter.drag(hx, hy, ax, ay)       # arrasta o handle -> topo do trilho (all-in)
    log('[shove] DRAG handle (%d,%d) -> all-in (%d,%d)' % (hx, hy, ax, ay))
    sleep(settle_s)                    # deixa o valor assentar (o botão vira "Raise X"/"All-in")
    frame2 = capture_bgr(view['window_rect'])          # RE-CAPTURA pós-drag (o painel mudou)
    crop2 = frame2[oy:oy + ch, ox:ox + cw] if frame2 is not None else crop
    confirm = (read_panel(crop2, _ocr=lambda im: '') or {}).get('confirm')
    if confirm:
        confirm_box = confirm['box']
    elif open_box is not None:
        # FALLBACK: o botão de CONFIRMAR (Raise/All-in) ocupa o slot do "Aumentar" (direita) depois que
        # o painel abre — reusa a posição do open_box. Evita o NO_CONFIRM que travava o shove ao vivo.
        confirm_box = open_box
        log('[shove] confirm não lido -> fallback no slot do Aumentar')
    else:
        log('[shove] sem botão Raise (confirmar) e sem open_box -> não confirma')
        return {'state': 'NO_CONFIRM'}
    xy = _click(confirm_box, 'RAISE(all-in)')
    return {'state': 'CLICKED_SHOVE', 'drag': (hx, hy, ax, ay), 'confirm_xy': xy}


def make_on_sizing(hwnd, *, adapter, control, discover_rect=None, capture=None,
                   engine_factory=None, sequencer_factory=None, postflop_bet=None, log=print):
    """Devolve on_sizing(plan, table_key, entry, button_row) -> resultado do executor.
    PÓS-FLOP -> execute_postflop_bet(bucket). PRÉ-FLOP -> RaiseSequencer(target_mult).run().
    Tudo injetável p/ teste (discover_rect/capture/engine_factory/sequencer_factory/postflop_bet).
    NUNCA clica sem ARMAR (control.execution_allowed())."""
    if discover_rect is None:
        # MONITOR PRINCIPAL (coords IDENTIDADE 0,0), não a janela (-1280 + DPI multi-monitor) — mesmo
        # fix do single-click (grab_primary). Assim o painel de raise/bet captura e clica no lugar certo.
        discover_rect = lambda h=None: ppp_grab.primary_monitor_rect()
    if postflop_bet is None:
        from postflop_bet_executor import execute_postflop_bet as postflop_bet

    def _default_seq(rect, target_mult):
        from raise_sequencer import RaiseSequencer
        cap = capture or ppp_grab.imagegrab_capture_bgr    # read_raise_panel/slider leem em BGR
        return RaiseSequencer(capture=lambda h=None, r=rect: cap(r), window_rect=rect,
                              input_adapter=adapter, target_mult=target_mult, bot_control=control)

    seqf = sequencer_factory or _default_seq
    engf = engine_factory or (lambda rect: ImageGrabEngine(rect, capture))

    def on_sizing(plan, table_key, entry, button_row, view=None):
        rect = discover_rect(hwnd)
        if rect is None:
            log('[sizing %s] sem rect da janela -> não executa' % table_key)
            return {'state': 'NO_RECT'}
        if control is None or not control.execution_allowed():
            log('[sizing %s] DRY/pausado -> não executa sizing' % table_key)
            return {'state': 'DRY'}
        if street_is_postflop(entry):
            bucket = (plan or {}).get('bucket') or '1/2'
            res = postflop_bet(engf(rect), hwnd, bucket, adapter=adapter, control=control,
                               discover_rect=rect)
            log('[sizing %s] POS-FLOP bet bucket=%s -> %s' % (table_key, bucket, res.get('state')))
            return res
        tmult = (plan or {}).get('size')         # pré-flop: multiplicador/size_bb do cérebro
        if tmult is None:
            log('[sizing %s] PRE-FLOP raise sem target -> não executa' % table_key)
            return {'state': 'NO_TARGET'}
        # PRÉ-FLOP preferido: executores OCR-free (precisam do CROP da mesa = view). SHOVE (all_in)
        # usa o SLIDER no máximo; raise ×BB usa os presets. Distingue pelo caveat ALL_IN do plano.
        if view is not None and sequencer_factory is None:
            btns = (button_row or {}).get('buttons') or []
            open_box = btns[-1].get('box') if len(btns) >= 3 else None   # Aumentar = o + à direita
            is_shove = 'ALL_IN' in ((plan or {}).get('caveats') or [])
            if is_shove:
                res = execute_raise_shove(view, adapter=adapter, open_box=open_box,
                                          capture_bgr=capture, log=log)
                log('[sizing %s] PRE-FLOP SHOVE (slider max) -> %s' % (table_key, res.get('state')))
            else:
                res = execute_raise_preset(view, tmult, adapter=adapter, open_box=open_box,
                                           capture_bgr=capture, log=log)
                log('[sizing %s] PRE-FLOP raise x%s (preset) -> %s' % (table_key, tmult, res.get('state')))
            return res
        res = seqf(rect, tmult).run()            # fallback: sequenciador ×BB (slider)
        log('[sizing %s] PRE-FLOP raise x%s (seq) -> %s' % (table_key, tmult, (res or {}).get('result_state')))
        return res

    return on_sizing
