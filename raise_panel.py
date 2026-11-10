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


def map_multiplier_to_preset(target_mult, presets):
    """Preset com multiplicador mais próximo do alvo (entre os que leram). None
    se nenhum preset legível. Empate -> o menor (mais conservador)."""
    usable = [p for p in presets if p.get('mult') is not None]
    if target_mult is None or not usable:
        return None
    return min(usable, key=lambda p: (abs(p['mult'] - target_mult), p['mult']))
