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


def parse_multiplier(text):
    """Multiplicador do rótulo ('2.5x' -> 2.5), ou None."""
    m = _MULT.search((text or '').replace(' ', ''))
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
    presets = []
    for (x, y, bw, bh) in boxes_of(green):
        roi = band[y + 6:y + bh - 6, x + 6:x + bw - 6]
        label = None
        if roi.size:
            g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            up = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            _, th = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            label = ocr(th)
        presets.append(dict(box=[x, y + oy, bw, bh], label=label,
                            mult=parse_multiplier(label)))
    conf_boxes = boxes_of(yellow)
    confirm = (dict(box=[conf_boxes[0][0], conf_boxes[0][1] + oy,
                         conf_boxes[0][2], conf_boxes[0][3]]) if conf_boxes else None)

    if 3 <= len(presets) <= 5 and confirm is not None:
        result['status'] = 'EXPERIMENTAL_RAISE_PANEL'
    result['presets'] = presets
    result['confirm'] = confirm
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


# Piso ABSOLUTO de shove: um alvo abaixo disto NUNCA é tratado como all-in, mesmo
# acima do maior preset. "Acima do menu" não prova all-in (A4 / contraexemplo
# raise-above-menu): um 4bet grande (ex.: 6x) fica sem preset compatível e deve
# ABSTER (lado seguro: nunca shova por engano), não virar jam. Um alvo >= 8x a
# aposta-a-bater é magnitude de jam (stack/to_beat), não um sizing que se escolhe
# por preset. Alvos de jam reais abaixo disso (short stack) abstêm — seguro.
SHOVE_FLOOR_MULT = 8.0


def is_shove_target(target_mult, presets, *, max_preset_slack=1.15, shove_floor=SHOVE_FLOOR_MULT):
    """True quando o alvo é um SHOVE/all-in: não há preset compatível, o alvo é
    MAIOR que o maior preset legível (×slack) E atinge o PISO absoluto de shove
    (`shove_floor`). Sem o piso, "acima do menu" por pouco (ex.: 6x sobre 4x) virava
    jam — bug de segurança. Distingue 'shove' (barra) de 'alvo acima do menu sem
    preset' (abstém)."""
    if target_mult is None:
        return False
    if map_multiplier_to_preset(target_mult, presets) is not None:
        return False
    usable = [p['mult'] for p in presets if p.get('mult') is not None]
    if not usable:
        return False
    return target_mult > max(usable) * max_preset_slack and target_mult >= shove_floor


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
