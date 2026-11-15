"""Leitor do painel de AUMENTO do PPPoker + mapeamento de sizing (bloco Raise).

Quando o hero clica em Raise, abre um painel com PRESETS de multiplicador
(2× / 2.5× / 3× / 4×, verdes) + um botão de CONFIRMAR ("Raise", amarelo) + um
slider para ajuste fino. O multiplicador é sobre a APOSTA A BATER: sem open,
× o BB (2.5× = 2,5bb); com um open de 2bb, 3× = 6bb (3× o open). Isso casa
direto com os multiplicadores do `sizing.py` (open 2–2,5×; 3bet 2,5–3,4×).

`read_raise_panel(crop)` detecta os presets (box + rótulo + multiplicador) e o
botão confirmar. `map_multiplier_to_preset` escolhe o preset mais próximo do
multiplicador-alvo. Observação/leitura; não clica.

Calibrado no skin Karekas (gabarito tests/fixtures/raise_panel/).
"""
import re

import cv2
import numpy as np

from table_reading.ocr_runtime import image_to_string

_MULT = re.compile(r'(\d+(?:[.,]\d+)?)\s*[xX×]')


def parse_preset(text):
    text = (text or '').strip().replace(' ', '').replace(',', '.').casefold()
    mult = parse_multiplier(text)
    if mult is not None:
        return dict(basis='multiplier', mult=mult)
    if text in ('pot', 'pote'):
        return dict(basis='pot', fraction=1.0)
    if text in ('allin', 'all-in', 'shove'):
        return dict(basis='all_in')
    fraction = re.fullmatch(r'(\d+)/(\d+)', text)
    if fraction and int(fraction[2]):
        return dict(basis='pot', fraction=int(fraction[1]) / int(fraction[2]))
    percent = re.fullmatch(r'(\d+(?:\.\d+)?)%', text)
    if percent:
        return dict(basis='pot', fraction=float(percent[1]) / 100)
    return {}


def _white_ink(region):
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    return np.uint8((hsv[:, :, 1] < 85) & (hsv[:, :, 2] > 165)) * 255


def _last_glyph(ink):
    n, _, stats, _ = cv2.connectedComponentsWithStats(ink)
    components = [tuple(int(v) for v in row) for row in stats[1:] if row[4] >= 4]
    if not components:
        return None
    x, y, w, h, _ = max(components, key=lambda v: v[0] + v[2])
    body_height = max(v[3] for v in components)
    if not .75 <= w / h <= 1.3 or h < .45 * body_height:
        return None
    glyph = cv2.resize(ink[y:y+h, x:x+w], (24, 24), interpolation=cv2.INTER_NEAREST) > 0
    return x, glyph


def _recover_multiplier(region, donors):
    """OCR '%' versus the actual x glyph: verify x against this frame's donors.

    Never reinterpret percent as multiplier based on the number or slot.
    Require glyph similarity AND two independent numeric OCR modes.
    """
    ink = _white_ink(region)
    last = _last_glyph(ink)
    if last is None or not donors:
        return None
    x, glyph = last
    similarities = [float((glyph & other).sum()) / max(1, int((glyph | other).sum())) for other in donors]
    if max(similarities) < .80:
        return None
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    up = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, clean = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    values = []
    for mode in (7, 6):
        raw = image_to_string(clean, config='--psm %d' % mode).strip().replace(' ', '')
        number = re.fullmatch(r'(\d+(?:[.,]\d+)?)[%xX×]+', raw)
        if not number:
            return None
        values.append(float(number[1].replace(',', '.')))
    return values[0] if values[0] == values[1] else None


def parse_selected_amount(text):
    # A trailing vertical caret can be OCR'd as I/l; no other label is ignored.
    m = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*BB\s*[|Il]?\s*', text or '', re.I)
    if not m:
        return None
    digits = m[1].replace(',', '.')
    decimals = len(digits.split('.')[1]) if '.' in digits else 0
    return dict(value_bb=float(digits), quantum_bb=10 ** -decimals, unit='BB')


def read_selected_amount(crop, *, amount_box=(.76, .425, .205, .06), _ocr=None):
    if not isinstance(crop, np.ndarray) or crop.ndim != 3:
        return dict(status='AMOUNT_UNREADABLE')
    h, w = crop.shape[:2]
    x, y, bw, bh = amount_box
    box = [round(x*w), round(y*h), round(bw*w), round(bh*h)]
    px, py, pw, ph = box
    region = crop[py:py+ph, px:px+pw]
    if region.size == 0:
        return dict(status='AMOUNT_UNREADABLE')
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    white = (hsv[:, :, 1] < 85) & (hsv[:, :, 2] > 165)
    yellow = (hsv[:, :, 0] > 18) & (hsv[:, :, 0] < 40) & (hsv[:, :, 1] > 90) & (hsv[:, :, 2] > 150)
    ink = np.uint8(white | yellow)*255
    n, _, components, _ = cv2.connectedComponentsWithStats(ink)
    bodies = [row for row in components[1:] if row[4] >= 8
              and row[3] < .9*ink.shape[0] and row[2] < .8*ink.shape[1]]
    if bodies:
        max_height = max(row[3] for row in bodies)
        text = [row for row in bodies if row[3] >= .55*max_height]
        top = max(0, min(row[1] for row in text) - 3)
        bottom = min(ink.shape[0], max(row[1]+row[3] for row in text) + 3)
        ink = ink[top:bottom]
    clean = cv2.resize(255 - ink, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    clean = cv2.copyMakeBorder(clean, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    raw = [(_ocr(clean, mode) if _ocr else image_to_string(clean, config='--psm %d' % mode)).strip() for mode in (7, 6)]
    values = [parse_selected_amount(r) for r in raw]
    if values[0] is None or values[0] != values[1]:
        return dict(status='AMOUNT_UNREADABLE', raw=raw, box=box)
    return dict(status='AMOUNT_CONFIRMED', confidence='high', source='ocr_consensus_7_6',
                semantics='RAISE_TO_BB', raw=raw, box=box, **values[0])


def parse_multiplier(text):
    """Multiplicador do rótulo ('2.5x' -> 2.5), ou None."""
    m = _MULT.fullmatch((text or '').strip().replace(' ', ''))
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', '.'))
    except ValueError:
        return None


def read_raise_panel(crop, *, _ocr=None):
    """{status, presets:[{box,label,mult}], confirm:{box}}. box em coords do CROP.

    status EXPERIMENTAL_RAISE_PANEL quando há 3–5 presets verdes + o confirmar
    amarelo; senão NO_RAISE_PANEL. Boxes já com o offset da banda inferior.
    """
    result = dict(status='NO_RAISE_PANEL', presets=[], confirm=None)
    if not isinstance(crop, np.ndarray) or crop.ndim != 3 or crop.shape[2] != 3 \
            or crop.dtype != np.uint8:
        return dict(result, status='INVALID_CROP')
    h, w = crop.shape[:2]
    if h < 250 or w < 150:
        return dict(result, status='CROP_TOO_SMALL')
    oy = round(h * 0.88)
    band = crop[oy:h]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    green = np.uint8((hue > 60) & (hue < 95) & (sat > 60) & (val > 60)) * 255
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    yellow = np.uint8((hue > 18) & (hue < 38) & (sat > 80) & (val > 120)) * 255
    yellow = cv2.morphologyEx(yellow, cv2.MORPH_CLOSE, np.ones((5, 15), np.uint8))

    def boxes_of(mask):
        n, _, st, _ = cv2.connectedComponentsWithStats(mask)
        return sorted(tuple(int(v) for v in st[i, :4]) for i in range(1, n)
                      if st[i, 2] > 0.07 * w and st[i, 3] > 0.25 * band.shape[0])

    ocr = _ocr or (lambda img: ' '.join(image_to_string(img, config='--psm 7').split()))
    presets, regions = [], []
    for (x, y, bw, bh) in boxes_of(green):
        roi = band[y + 6:y + bh - 6, x + 6:x + bw - 6]
        label = None
        if roi.size:
            g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            up = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            _, th = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            label = ocr(th)
        preset = dict(box=[x, y + oy, bw, bh], label=label, mult=parse_multiplier(label))
        preset.update(parse_preset(label))
        presets.append(preset)
        regions.append(roi)
    if _ocr is None:
        donors = []
        for preset, region in zip(presets, regions):
            if preset.get('mult') is not None and region.size:
                last = _last_glyph(_white_ink(region))
                if last is not None:
                    donors.append(last[1])
        for preset, region in zip(presets, regions):
            if preset.get('mult') is None and region.size:
                recovered = _recover_multiplier(region, donors)
                if recovered is not None:
                    preset.update(mult=recovered, basis='multiplier', label='%sx' % recovered,
                                  source='same_frame_x_glyph_and_numeric_ocr_consensus')
    conf_boxes = boxes_of(yellow)
    confirm = (dict(box=[conf_boxes[0][0], conf_boxes[0][1] + oy,
                         conf_boxes[0][2], conf_boxes[0][3]]) if conf_boxes else None)

    if 3 <= len(presets) <= 5 and confirm is not None:
        result['status'] = 'EXPERIMENTAL_RAISE_PANEL'
    result['presets'] = presets
    result['confirm'] = confirm
    result['selected'] = read_selected_amount(crop) if _ocr is None and confirm else None
    return result


def read_raise_slider(crop):
    """Localiza a BARRA de aposta (slider) do painel p/ ajustar o tamanho — em
    especial ALL-IN (arrastar o handle ao topo do trilho). Observação/leitura; não
    arrasta. Retorna {status, handle:{box,center}, allin_to:(x,y)} em coords do
    CROP; status SLIDER_FOUND quando acha o handle, senão NO_SLIDER.

    O handle é o retângulo CLARO na coluna direita, na metade inferior do painel
    (no mínimo, perto do fundo). O topo do trilho (= all-in) fica ~na altura da
    caixa de valor. Calibrado no gabarito Karekas (handle cx≈0.86, cy≈0.88; topo
    cy≈0.46); usamos frações p/ tolerar escala. O arrasto real valida ao vivo."""
    result = dict(status='NO_SLIDER', handle=None, allin_to=None)
    if not isinstance(crop, np.ndarray) or crop.ndim != 3 or crop.shape[2] != 3:
        return result
    h, w = crop.shape[:2]
    b = crop[:, :, 0].astype(int)
    g = crop[:, :, 1].astype(int)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    light = np.uint8((gray > 150) & (b > 120) & (np.abs(b - g) < 45)) * 255
    light = cv2.morphologyEx(light, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(light, 8)
    best = None
    for i in range(1, n):
        x, y, bw, bh, a = (int(v) for v in st[i, :5])
        cx, cy = (x + bw / 2) / w, (y + bh / 2) / h
        # O HANDLE fica na coluna BEM à direita (cx≈0.86), metade inferior. Os botões
        # +/- também são claros mas ficam mais à ESQUERDA (cx≈0.64) — por isso exigimos
        # cx>0.78 e, entre candidatos, pegamos o MAIS À DIREITA (o handle do trilho).
        if cx > 0.78 and 0.55 < cy < 0.95 and bw > 0.07 * w and a > 0.0006 * w * h:
            if best is None or cx > (best[0] + best[2] / 2) / w:
                best = (x, y, bw, bh, a)
    if best is None:
        return result
    x, y, bw, bh, _ = best
    hx, hy = x + bw // 2, y + bh // 2
    # topo do trilho (all-in): mesma coluna, altura da caixa de valor (~0.46h). Miramos
    # um pouco ACIMA p/ garantir o máximo (o slider satura no topo).
    allin_to = (hx, int(0.44 * h))
    return dict(status='SLIDER_FOUND', handle=dict(box=[x, y, bw, bh], center=[hx, hy]),
                allin_to=list(allin_to))


def is_shove_target(target_mult, presets, *, max_preset_slack=1.15):
    """True quando o alvo é um SHOVE/all-in: não há preset compatível E o alvo é
    MAIOR que o maior preset legível (×slack). Distingue 'shove' (usa a barra) de
    'alvo intermediário sem preset' (abstém)."""
    if target_mult is None:
        return False
    if map_multiplier_to_preset(target_mult, presets) is not None:
        return False
    usable = [p['mult'] for p in presets if p.get('mult') is not None]
    if not usable:
        return False
    return target_mult > max(usable) * max_preset_slack


def target_multiplier(advice, table_state):
    """Multiplicador-alvo do aumento (× a aposta a bater), ou None p/ abster.

    O preset multiplica a APOSTA A BATER: sem open = BB (1,0); com open = a maior
    aposta na mesa. target = size_bb / aposta-a-bater. O sizing.py dá `size_bb`
    absoluto. Aproximação segura: a aposta a bater = maior `bet_bb` lido (ou 1,0).
    """
    sz = (advice or {}).get('sizing') or {}
    size_bb = sz.get('size_bb')
    if not isinstance(size_bb, (int, float)) or size_bb <= 0:
        return None
    bets = [b.get('bet_bb') for b in ((table_state or {}).get('bets') or [])
            if isinstance(b.get('bet_bb'), (int, float)) and b.get('bet_bb') > 0]
    # A "aposta a bater" é o maior RAISE (acima do BB). Num pote NÃO-ABERTO (só
    # blinds) NÃO há raise -> o BB vale 1.0 POR DEFINIÇÃO. Ignorar os blinds evita
    # que um blind MISLIDO (ex.: BB=0,6) infle o open: 2bb/0,6=3,3->3x em vez de 2x.
    raises = [b for b in bets if b > 1.5]
    to_beat = max(raises) if raises else 1.0
    return round(size_bb / to_beat, 2)


def map_multiplier_to_preset(target_mult, presets, *, tol=None):
    """Preset com multiplicador mais próximo do alvo (entre os que leram), SE
    estiver dentro da tolerância; senão None (abster — não aproximar à força).

    Evita transformar um sizing grande/all-in (ex.: alvo 25×) num preset de 4×:
    sem tamanho compatível e conferível, não clica. Tolerância padrão =
    max(0,5×, 20% do alvo). Empate -> o menor (mais conservador). None também
    quando nenhum preset é legível ou o alvo é None."""
    usable = [p for p in presets if p.get('mult') is not None]
    if target_mult is None or not usable:
        return None
    best = min(usable, key=lambda p: (abs(p['mult'] - target_mult), p['mult']))
    limit = tol if tol is not None else max(0.5, 0.2 * target_mult)
    if abs(best['mult'] - target_mult) > limit:
        return None                                  # nenhum preset compatível -> abster
    return best
