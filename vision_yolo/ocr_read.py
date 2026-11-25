"""F3 - leitura de NÚMEROS por OCR na região detectada (stack/pote/aposta). Na Suprema os
valores aparecem EM BB ('112.6 BB') -> o OCR devolve o stack_bb DIRETO (sem bb_chips).
Motor = pytesseract (ja usado no projeto). READ-ONLY."""
from __future__ import annotations

import re

import numpy as np

try:
    import cv2
except Exception:
    cv2 = None
import os as _os

import pytesseract

# binario do Tesseract (nem sempre no PATH nesta maquina)
for _p in (r'C:\Program Files\Tesseract-OCR\tesseract.exe',
           r'C:\Users\tacao\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'):
    if _os.path.exists(_p):
        pytesseract.pytesseract.tesseract_cmd = _p
        break

_NUM = re.compile(r'(\d+(?:[.,]\d+)?)')


def _to_bgr(image):
    """PIL/ndarray/caminho -> ndarray BGR."""
    if isinstance(image, str):
        return cv2.imread(image)
    arr = np.asarray(image)
    if arr.ndim == 3 and arr.shape[2] == 3:
        return arr[:, :, ::-1].copy()        # assume RGB (PIL) -> BGR
    return arr


def crop_frac(img_bgr, box):
    """box=(cx,cy,w,h) em fração -> recorte BGR."""
    H, W = img_bgr.shape[:2]
    cx, cy, w, h = box
    x0 = max(0, int((cx - w / 2) * W)); x1 = min(W, int((cx + w / 2) * W))
    y0 = max(0, int((cy - h / 2) * H)); y1 = min(H, int((cy + h / 2) * H))
    return img_bgr[y0:y1, x0:x1]


def _prep(crop, upscale=3):
    """Pré-processa p/ texto claro em fundo escuro: cinza, upscale, Otsu (auto-invert)."""
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if th.mean() < 127:                       # texto deve ficar PRETO sobre branco p/ o tesseract
        th = 255 - th
    return th


def read_number(image, box=None, *, upscale=3):
    """Devolve o 1o número do recorte (float) ou None. `box` em fração (cx,cy,w,h); sem box,
    lê a imagem inteira. Aceita '112.6 BB' -> 112.6."""
    if cv2 is None:
        return None
    img = _to_bgr(image)
    crop = crop_frac(img, box) if box else img
    if crop is None or crop.size == 0:
        return None
    th = _prep(crop, upscale)
    txt = pytesseract.image_to_string(
        th, config='--psm 7 -c tessedit_char_whitelist=0123456789.,BBbb ')
    m = _NUM.search(txt.replace(',', '.'))
    return float(m.group(1)) if m else None


def read_seats(image, stack_regions):
    """{seat_key: stack_bb} lendo o OCR de cada caixa de stack (pula o que não ler)."""
    img = _to_bgr(image)
    out = {}
    for seat, box in (stack_regions or {}).items():
        v = read_number(img, box)
        if v is not None:
            out[seat] = v
    return out
