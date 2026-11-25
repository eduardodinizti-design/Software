"""Transcritor DETERMINÍSTICO de charts GTOWizard (ChipEV) -> range máquina-legível
(Eduardo 19/11: aproveitar a pasta "Ranges E TEORIAS" p/ cobrir gaps, método automático).

A mão vem da POSIÇÃO no grid 13×13 (não de OCR) e o peso de cada ação vem da FRAÇÃO DE
COR dentro da célula. Paleta do GTOWizard ChipEV (medida por k-means nos próprios charts):
    fold=azul  call=verde  raise=salmão  allin=vinho.

Valida sozinho: o % combo-ponderado de cada ação TEM que bater com a barra do cabeçalho
do chart (ex.: Call 23,5% / 311,55 combos). Use `summary()` p/ conferir antes de ingerir.

NÃO cobre os PNGs de PKO (outra ferramenta/paleta) — esses têm transcritor próprio.
"""
import json
import os

import cv2
import numpy as np

# centroides RGB (medidos). Ordem fixa p/ indexar.
_ACTIONS = ['fold', 'call', 'raise', 'allin']
_CENT = np.array([
    (63, 122, 180),     # fold  (azul)
    (91, 181, 103),     # call  (verde)
    (247, 124, 124),    # raise (salmão)
    (110, 25, 25),      # allin (vinho)
], dtype=np.float32)
_MAXDIST = 85.0         # além disso o pixel é ignorado (texto/borda/hover)

_RANKS = 'AKQJT98765432'
_COMBOS = {}            # hand -> nº de combos (pair=6, suited=4, offsuit=12)


def hand_at(r, c):
    """Mão canônica na célula (linha r, coluna c) do grid 13×13 padrão."""
    if r == c:
        return _RANKS[r] * 2
    if c > r:
        return _RANKS[r] + _RANKS[c] + 's'
    return _RANKS[c] + _RANKS[r] + 'o'


def _combos(hand):
    if hand not in _COMBOS:
        _COMBOS[hand] = 6 if hand[0] == hand[1] else (4 if hand.endswith('s') else 12)
    return _COMBOS[hand]


def _classify(rgb):
    """rgb: HxWx3 float (R,G,B). Devolve HxW de índices 0..3 ou -1 (ignorar)."""
    mx = rgb.max(2); mn = rgb.min(2)
    valid = (mx >= 70) & ~(((mx - mn) < 30) & (mx > 140))      # tira preto/linha e branco/cinza
    d = np.sqrt(((rgb[:, :, None, :] - _CENT[None, None, :, :]) ** 2).sum(3))  # HxWx4
    idx = d.argmin(2)
    valid &= d.min(2) < _MAXDIST
    return np.where(valid, idx, -1)


def _detect_grid(rgb):
    """Acha o bbox do grid 13×13 (bloco de células coloridas na ESQUERDA)."""
    h, w = rgb.shape[:2]
    scale = 500.0 / w
    small = cv2.resize(rgb, (500, int(h * scale)), interpolation=cv2.INTER_AREA)
    lab = _classify(small.astype(np.float32))
    mask = (lab >= 0).astype(np.uint8)
    mask[:, int(0.70 * mask.shape[1]):] = 0        # painel direito fora (corte folgado)
    mask[:int(0.14 * mask.shape[0]), :] = 0        # header de posições fora
    # kernel PEQUENO: une as células do grid SEM atravessar o vão grid->painel direito.
    mask = cv2.morphologyEx(mask * 255, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
    best, best_area = None, 0
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if cent[i][0] > 0.5 * mask.shape[1]:       # grid é centrado à esquerda
            continue
        aspect = ww / float(hh or 1)
        if area > best_area and ww > 0.3 * mask.shape[1] and hh > 0.3 * mask.shape[0] \
                and 1.4 < aspect < 2.3:            # grid 13×13 ~ 1.9:1
            best, best_area = (x, y, ww, hh), area
    if best is None:
        raise ValueError('grid não detectado')
    x, y, ww, hh = [v / scale for v in best]
    return int(x), int(y), int(ww), int(hh)


def read_range(path):
    """Lê o chart e devolve {'hands': {hand: {action: freq}}, 'bbox': (...)}.
    freq = fração de cada ação na célula (soma≈1 nas células lidas). Amostra uma FAIXA
    horizontal no meio da célula (abaixo do rótulo, acima do EV) e com a LARGURA inteira —
    as bandas de ação do GTOWizard são verticais, então preservar a largura preserva as %."""
    bgr = cv2.imread(path)
    if bgr is None:
        raise FileNotFoundError(path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    x, y, ww, hh = _detect_grid(rgb)
    cw, ch = ww / 13.0, hh / 13.0
    hands = {}
    for r in range(13):
        for c in range(13):
            x0 = int(x + c * cw + 0.04 * cw); x1 = int(x + (c + 1) * cw - 0.04 * cw)
            y0 = int(y + r * ch + 0.36 * ch); y1 = int(y + r * ch + 0.72 * ch)
            cell = rgb[y0:y1, x0:x1]
            lab = _classify(cell)
            counts = np.array([(lab == i).sum() for i in range(4)], dtype=float)
            tot = counts.sum()
            h = hand_at(r, c)
            if tot < 0.02 * cell.shape[0] * cell.shape[1]:   # célula sem cor legível -> fold
                hands[h] = {'fold': 1.0}
            else:
                hands[h] = {_ACTIONS[i]: round(counts[i] / tot, 3)
                            for i in range(4) if counts[i] > 0}
    return {'hands': hands, 'bbox': (x, y, ww, hh)}


def summary(hands):
    """% combo-ponderado por ação (p/ bater com a barra do cabeçalho do chart)."""
    agg = {a: 0.0 for a in _ACTIONS}
    total = 0.0
    for h, acts in hands.items():
        n = _combos(h)
        total += n
        for a, f in acts.items():
            agg[a] += n * f
    return {a: dict(pct=round(100 * v / total, 1), combos=round(v, 1))
            for a, v in agg.items() if v > 0.05}


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        res = read_range(p)
        print('\n==', os.path.basename(p), '== bbox', res['bbox'])
        for a, s in summary(res['hands']).items():
            print('  %-6s %5.1f%%  %7.1f combos' % (a, s['pct'], s['combos']))
