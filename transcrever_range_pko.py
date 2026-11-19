"""Transcritor dos charts de BOUNTY/PKO do PDF 'Torneios Bounty - Ranges Práticos' (curso
Reg-Life/Eduardo — [[nvt-teoria-reg-life-corpus]]). Paleta PRÓPRIA (≠ GTOWizard):
    raise = VERMELHO (237,59,59)   fold = AZUL (60,123,182).
O grid 13×13 é uma IMAGEM EMBUTIDA limpa no PDF (sem texto por cima), então divide-se
direto em 13×13 e a FRAÇÃO de vermelho por célula = peso do raise. A mão vem da POSIÇÃO.

Valida sozinho: o % combo-ponderado de raise bate com o % do diagrama do PDF (ex.: 25,9%).
Reusa hand_at/summary do transcritor GTOWizard."""
import os

import cv2
import numpy as np

import transcrever_range_gtow as tg

_ACTIONS = ['fold', 'raise']
_CENT = np.array([(60, 123, 182),      # fold  = azul
                  (237, 59, 59)],      # raise = vermelho
                 dtype=np.float32)
_MAXDIST = 95.0


def _classify(rgb):
    mx = rgb.max(2); mn = rgb.min(2)
    valid = (mx >= 60) & ~(((mx - mn) < 30) & (mx > 150))     # tira borda/texto branco
    d = np.sqrt(((rgb[:, :, None, :] - _CENT[None, None, :, :]) ** 2).sum(3))
    idx = d.argmin(2)
    valid &= d.min(2) < _MAXDIST
    return np.where(valid, idx, -1)


def grid_image_from_page(page, doc):
    """A imagem ~quadrada (grid 13×13) embutida na página do PDF (RGB HxWx3) ou None."""
    import pymupdf
    best, ba = None, 0
    for info in page.get_images(full=True):
        pix = pymupdf.Pixmap(doc, info[0])
        if pix.n > 4:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        w, h = pix.width, pix.height
        if w > 200 and 0.8 < w / float(h) < 1.5 and w * h > ba:
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(h, w, pix.n)[:, :, :3]
            best, ba = arr.copy(), w * h
    return best


def read_range_image(rgb):
    """rgb HxWx3 do grid 13×13. {'hands': {hand: {action: freq}}}. Amostra faixa do meio
    da célula (largura inteira menos borda) — preserva a fração de vermelho (raise)."""
    rgb = rgb.astype(np.float32)
    h, w = rgb.shape[:2]
    cw, ch = w / 13.0, h / 13.0
    hands = {}
    for r in range(13):
        for c in range(13):
            x0 = int(c * cw + 0.08 * cw); x1 = int((c + 1) * cw - 0.08 * cw)
            y0 = int(r * ch + 0.30 * ch); y1 = int(r * ch + 0.72 * ch)
            cell = rgb[y0:y1, x0:x1]
            lab = _classify(cell)
            counts = np.array([(lab == i).sum() for i in range(2)], dtype=float)
            tot = counts.sum()
            hd = tg.hand_at(r, c)
            if tot < 0.02 * cell.shape[0] * cell.shape[1]:
                hands[hd] = {'fold': 1.0}
            else:
                hands[hd] = {_ACTIONS[i]: round(counts[i] / tot, 3)
                             for i in range(2) if counts[i] > 0}
    return {'hands': hands}


def summary(hands):
    return tg.summary(hands)


if __name__ == '__main__':
    import sys
    import pymupdf
    pdf = sys.argv[1]
    pages = [int(x) - 1 for x in sys.argv[2:]] if len(sys.argv) > 2 else None
    d = pymupdf.open(pdf)
    for i in (pages or range(d.page_count)):
        img = grid_image_from_page(d[i], d)
        if img is None:
            continue
        s = summary(read_range_image(img)['hands'])
        print('p%02d  %s' % (i + 1, '  '.join('%s=%.1f%%' % (a, v['pct']) for a, v in s.items())))
