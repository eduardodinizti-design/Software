"""Executor de APOSTA PÓS-FLOP (Eduardo 19/11: "o bot nunca clica bet no pós-flop").

A aposta pós-flop é multi-etapa (abrir painel -> escolher FRAÇÃO -> confirmar) e o painel
pós-flop usa FRAÇÃO DE POTE (1/3, 1/2, 2/3, Pote, All-in), não ×BB. O sequenciador de
raise (pré-flop) procura preset ×BB -> não casa -> não clicava. Aqui achamos o preset pela
FRAÇÃO (rótulo) e clicamos preset + confirmar, reusando as primitivas gated já existentes
(mesma máquina de _click_step do registrador). Só clica se ACHAR o preset da fração; senão
devolve NO_FRACTION_PRESET (não dispara às cegas).

Mapa do nosso slider (postflop_sizing.bucket) -> bucket do painel (raise_panel):
  1/3->t33, 1/2->t50, 2/3->t66, geo->t66 (geométrico ~>= 2/3; melhor fração disponível),
  allin->allin. 'pot' se algum dia usarmos pote cheio.
"""
from raise_panel import read_raise_panel, map_fraction_to_preset
from registrar_armado import _click_step

# bucket do postflop_sizing -> bucket de fração do painel
_SLIDER_TO_PANEL = {'1/3': 't33', '1/2': 't50', '2/3': 't66', 'geo': 't66',
                    'allin': 'allin', 'pot': 'pot'}


def panel_bucket(sizing_bucket):
    """Traduz o bucket do postflop_sizing ('1/3'...) p/ o bucket do painel ('t33'...)."""
    return _SLIDER_TO_PANEL.get(str(sizing_bucket), 't50')   # default 1/2 (size seguro)


def find_fraction_preset(frame, sizing_bucket, *, read_panel=read_raise_panel):
    """(preset, panel) — o preset de fração que casa com o bucket, ou (None, panel)."""
    panel = read_panel(frame)
    preset = map_fraction_to_preset(panel_bucket(sizing_bucket), panel.get('presets') or [])
    return preset, panel


def execute_postflop_bet(engine, hwnd, sizing_bucket, *, adapter, control,
                         read_panel=read_raise_panel, discover_rect=None):
    """Clica a aposta pós-flop: acha o preset da FRAÇÃO (bucket) e clica preset + confirmar.
    Devolve {state, preset, confirm, labels}. state:
      NO_FRAME / NO_PANEL / NO_FRACTION_PRESET (não clica) / DONE / PARTIAL."""
    cap = (lambda: engine.capture_frame(hwnd=hwnd)[0])
    frame = cap()
    if frame is None:
        return dict(state='NO_FRAME')
    preset, panel = find_fraction_preset(frame, sizing_bucket, read_panel=read_panel)
    labels = [p.get('label') for p in (panel.get('presets') or [])]
    if not panel.get('presets'):
        return dict(state='NO_PANEL', labels=labels)
    if preset is None:
        # não achou a fração -> NÃO clica às cegas (honesto); loga os rótulos p/ calibrar.
        return dict(state='NO_FRACTION_PRESET', labels=labels, bucket=panel_bucket(sizing_bucket))

    rect_kw = dict(window_rect=discover_rect) if discover_rect else {}

    def loc_preset(f):
        p = read_panel(f)
        m = map_fraction_to_preset(panel_bucket(sizing_bucket), p.get('presets') or [])
        return m.get('box') if m else None

    def loc_confirm(f):
        p = read_panel(f)
        c = p.get('confirm')
        return c.get('box') if c else None

    def _ok(_i, _n):
        return dict(confirmed=True)

    r1 = _click_step(engine, hwnd, locate_frame_rect=loc_preset, source_key='pf_frac:%s' % sizing_bucket,
                     adapter=adapter, control=control, verifier=_ok, label='frac:%s' % sizing_bucket, **rect_kw)
    if r1['state'] not in ('DONE', 'UNKNOWN_RESULT'):
        return dict(state='PARTIAL', preset=preset.get('label'), step='preset', reason=r1.get('reasons'))
    r2 = _click_step(engine, hwnd, locate_frame_rect=loc_confirm, source_key='pf_confirm',
                     adapter=adapter, control=control, verifier=_ok, label='confirmar', **rect_kw)
    return dict(state=('DONE' if r2['state'] in ('DONE', 'UNKNOWN_RESULT') else 'PARTIAL'),
                preset=preset.get('label'), confirm=r2['state'], labels=labels)
