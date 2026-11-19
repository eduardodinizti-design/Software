"""Executor de APOSTA PÓS-FLOP (Eduardo 19/11). VALIDADO AO VIVO no PPPoker:
o painel de aposta pós-flop tem botões VERDES de FRAÇÃO em ordem fixa esquerda->direita
**1/3, 1/2, 2/3, Pot** (+ All-in quando aparece) e um confirmar AMARELO **"Bet"**; o
`read_raise_panel` (feito p/ o raise pré-flop ×BB) NÃO detecta esse painel. Aqui há um
leitor dedicado (`read_bet_panel`) que acha a linha verde, separa os botões por GAP e
atribui o bucket por POSIÇÃO (OCR confirma 2/3/Pot/Allin), e acha o "Bet".

- Sizes BÁSICOS (1/3,1/2,2/3,pot,allin) -> clica o BOTÃO + "Bet".
- Bet GEOMÉTRICO (bucket 'geo') -> precisa do SLIDER (vertical, à direita). Marcado como
  pendente de calibração do slider; por ora cai no botão mais próximo (2/3/Pot) com flag.

Só clica se ACHAR o botão da fração; senão devolve NO_FRACTION_BUTTON (não dispara cego).
"""
import cv2
import numpy as np

from registrar_armado import _click_step, _ocr_line

# bucket do postflop_sizing ('1/3'...) -> bucket do painel
_SLIDER_TO_PANEL = {'1/3': 't33', '1/2': 't50', '2/3': 't66', 'geo': 'geo',
                    'allin': 'allin', 'pot': 'pot'}
# Ordem canônica dos botões verdes esquerda->direita, por quantidade detectada.
_GREEN_ORDER = {
    3: ['t33', 't50', 't66'],
    4: ['t33', 't50', 't66', 'pot'],
    5: ['t33', 't50', 't66', 'pot', 'allin'],
}


def panel_bucket(sizing_bucket):
    return _SLIDER_TO_PANEL.get(str(sizing_bucket), 't50')


def _green_mask(f):
    b, g, r = f[:, :, 0].astype(int), f[:, :, 1].astype(int), f[:, :, 2].astype(int)
    return ((g > 110) & (g > r + 25) & (g > b + 10) & (r < 160)).astype('uint8')


def _yellow_mask(f):
    b, g, r = f[:, :, 0].astype(int), f[:, :, 1].astype(int), f[:, :, 2].astype(int)
    return ((r > 150) & (g > 120) & (b < 120) & (np.abs(r - g) < 90)).astype('uint8')


def _row_blobs(mask, fw, fh, *, min_w=0.015, min_h=0.015):
    m = cv2.morphologyEx(mask * 255, cv2.MORPH_CLOSE, np.ones((17, 17), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, _a = stats[i]
        if w > min_w * fw and h > min_h * fh and y > 0.5 * fh:
            out.append((int(x), int(y), int(w), int(h)))
    return out


def _ocr_bucket(text):
    t = ''.join(ch for ch in str(text or '').lower() if ch.isalnum() or ch == '/')
    if 'allin' in t or 'tudo' in t:
        return 'allin'
    if t in ('pot', 'pote') or 'pot' in t:
        return 'pot'
    if '2/3' in t or '23' == t:
        return 't66'
    if '1/2' in t or t == '12':
        return 't50'
    if '1/3' in t or t == '13':
        return 't33'
    return None


def read_bet_panel(frame):
    """{status, presets:[{bucket,label,box,center}], confirm:{box,center,label}}.
    status POSTFLOP_BET_PANEL quando há botões verdes de fração + o "Bet" amarelo."""
    res = dict(status='NO_BET_PANEL', presets=[], confirm=None)
    if not isinstance(frame, np.ndarray) or frame.ndim != 3:
        return res
    fh, fw = frame.shape[:2]
    green = _green_mask(frame)
    # a linha de botões de fração é o blob verde mais LARGO na metade de baixo.
    blobs = sorted(_row_blobs(green, fw, fh), key=lambda b: -b[2])
    presets = []
    if blobs:
        x0, y0, w, h = blobs[0]
        roi = green[y0:y0 + h, x0:x0 + w]
        colsum = roi.sum(axis=0)
        thr = max(1, colsum.max() * 0.25)
        on = colsum > thr
        segs, i = [], 0
        while i < len(on):
            if on[i]:
                j = i
                while j < len(on) and on[j]:
                    j += 1
                if j - i > 0.03 * w:        # largura mínima de um botão
                    segs.append((i, j))
                i = j
            else:
                i += 1
        order = _GREEN_ORDER.get(len(segs))
        for idx, (a, bb) in enumerate(segs):
            box = (x0 + a, y0, bb - a, h)
            txt = _ocr_line(cv2.cvtColor(frame[y0:y0 + h, x0 + a:x0 + bb], cv2.COLOR_BGR2GRAY)).strip()
            bucket = _ocr_bucket(txt) or (order[idx] if order else None)
            if bucket:
                presets.append(dict(bucket=bucket, label=(txt or bucket),
                                    box=box, center=(box[0] + box[2] // 2, box[1] + box[3] // 2)))
    # confirmar amarelo "Bet"
    for x, y, w, h in _row_blobs(_yellow_mask(frame), fw, fh):
        txt = _ocr_line(cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)).strip()
        if 'bet' in txt.lower() or 'apost' in txt.lower() or 'confirm' in txt.lower():
            res['confirm'] = dict(box=(x, y, w, h), center=(x + w // 2, y + h // 2), label=txt)
            break
    res['presets'] = presets
    if presets and res['confirm']:
        res['status'] = 'POSTFLOP_BET_PANEL'
    return res


def _pick(presets, target_bucket):
    """Preset do bucket alvo; 'geo' cai no maior disponível (<=2/3/Pot) com flag."""
    by = {p['bucket']: p for p in presets}
    if target_bucket in by:
        return by[target_bucket], False
    if target_bucket == 'geo':                 # geométrico usa SLIDER -> por ora maior botão
        for b in ('t66', 'pot', 't50'):
            if b in by:
                return by[b], True
    if target_bucket == 'allin':
        for b in ('allin', 'pot', 't66'):
            if b in by:
                return by[b], True
    return None, False


def execute_postflop_bet(engine, hwnd, sizing_bucket, *, adapter, control,
                         read_panel=read_bet_panel, discover_rect=None):
    """Clica o botão da FRAÇÃO (1/3,1/2,2/3,pot,allin) + "Bet". Devolve {state,...}.
    state: NO_FRAME / NO_BET_PANEL / NO_FRACTION_BUTTON / DONE / PARTIAL.
    (Bet GEOMÉTRICO ainda usa o botão mais próximo + flag SLIDER_PENDENTE.)"""
    frame, _ = engine.capture_frame(hwnd=hwnd)
    if frame is None:
        return dict(state='NO_FRAME')
    panel = read_panel(frame)
    labels = [p.get('bucket') for p in panel.get('presets') or []]
    if not panel.get('presets'):
        return dict(state='NO_BET_PANEL', labels=labels)
    target = panel_bucket(sizing_bucket)
    preset, approx = _pick(panel['presets'], target)
    if preset is None:
        return dict(state='NO_FRACTION_BUTTON', want=target, labels=labels)
    rect_kw = dict(window_rect=discover_rect) if discover_rect else {}

    def _ok(_i, _n):
        return dict(confirmed=True)

    def loc_frac(f):
        pn = read_panel(f)
        p, _ = _pick(pn.get('presets') or [], target)
        return p['box'] if p else None

    def loc_confirm(f):
        pn = read_panel(f)
        c = pn.get('confirm')
        return c['box'] if c else None

    r1 = _click_step(engine, hwnd, locate_frame_rect=loc_frac, source_key='pf_frac:%s' % target,
                     adapter=adapter, control=control, verifier=_ok, label='frac:%s' % target, **rect_kw)
    if r1['state'] not in ('DONE', 'UNKNOWN_RESULT'):
        return dict(state='PARTIAL', step='fraction', bucket=target, reason=r1.get('reasons'))
    r2 = _click_step(engine, hwnd, locate_frame_rect=loc_confirm, source_key='pf_confirm',
                     adapter=adapter, control=control, verifier=_ok, label='bet', **rect_kw)
    out = dict(state=('DONE' if r2['state'] in ('DONE', 'UNKNOWN_RESULT') else 'PARTIAL'),
               bucket=target, confirm=r2['state'])
    if approx:
        out['flag'] = 'SLIDER_PENDENTE_USOU_BOTAO_PROXIMO'
    return out
