"""Detector da tela de FIM DE TORNEIO do PPPoker (eliminação / Ranking).

Ao cair do torneio o cliente mostra um pop-up com o troféu MTT, "Ranking N/M",
o perfil do jogador e DOIS botões verdes: "Ficar" (re-entry/observar) e "Sair"
(fechar a mesa). A ROTINA correta ao cair é FECHAR a mesa -> clicar "Sair".

`detect_tournament_end(crop)` acha a assinatura (par de botões verdes embaixo +
"Ranking" no miolo) e devolve as caixas de "Sair"/"Ficar"/fechar e o ranking
lido. Observação/leitura; NÃO clica. Calibrado no gabarito
tests/fixtures/tournament_end/.
"""
import re

import cv2
import numpy as np

try:
    from table_reading.ocr_runtime import image_to_string
except Exception:                       # OCR opcional; a detecção geométrica funciona sem ele
    image_to_string = None

_RANK = re.compile(r'(\d{1,5})\s*/\s*(\d{1,5})')


def _green_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    m = np.uint8((hue > 60) & (hue < 95) & (sat > 70) & (val > 70)) * 255
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))


def _ocr(img):
    if image_to_string is None or img.size == 0:
        return ''
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    up = cv2.resize(g, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, th = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    try:
        return ' '.join(image_to_string(th, config='--psm 6').split())
    except Exception:
        return ''


def detect_tournament_end(crop):
    """{status, ranking, sair_box, ficar_box, close_box, buttons}. Boxes em coords
    do CROP (x, y, w, h). status TOURNAMENT_END quando há o PAR de botões verdes
    embaixo (Ficar/Sair) e confirmação de 'Ranking'/'Sair' por OCR; senão
    NO_TOURNAMENT_END. A caixa a clicar na rotina é `sair_box`."""
    result = dict(status='NO_TOURNAMENT_END', ranking=None, sair_box=None,
                  ficar_box=None, close_box=None, buttons=[])
    if not isinstance(crop, np.ndarray) or crop.ndim != 3 or crop.shape[2] != 3 \
            or crop.dtype != np.uint8:
        return dict(result, status='INVALID_CROP')
    h, w = crop.shape[:2]
    if h < 200 or w < 150:
        return dict(result, status='CROP_TOO_SMALL')

    # 1) PAR de botões verdes grandes na faixa inferior (Ficar à esquerda, Sair à direita).
    green = _green_mask(crop)
    n, _, st, _ = cv2.connectedComponentsWithStats(green, 8)
    btns = []
    for i in range(1, n):
        x, y, bw, bh, area = (int(v) for v in st[i, :5])
        cy = (y + bh / 2) / h
        if (bw > 0.18 * w and 0.03 * h < bh < 0.14 * h and cy > 0.80
                and 1.5 < bw / max(bh, 1) < 9 and area > 0.6 * bw * bh):
            btns.append((x, y, bw, bh))
    btns.sort(key=lambda b: b[0])                      # esquerda -> direita
    result['buttons'] = btns
    if len(btns) < 2:
        return result                                  # sem o par -> não é a tela de fim

    ficar, sair = btns[0], btns[-1]
    # Par Ficar/Sair: botões de TAMANHO semelhante, lado a lado, centrados em torno
    # do meio horizontal. Distingue de um único "confirmar" ou dos presets do raise.
    same_size = (abs(ficar[2] - sair[2]) < 0.25 * max(ficar[2], sair[2])
                 and abs(ficar[3] - sair[3]) < 0.4 * max(ficar[3], sair[3]))
    pair_center = (ficar[0] + sair[0] + sair[2]) / 2 / w
    if not (same_size and 0.35 < pair_center < 0.65 and sair[0] > ficar[0] + ficar[2]):
        return result

    # 2) Confirmação SEM depender de OCR: o BANNER superior do pop-up é azul e
    # brilhante (estádio MTT). Assinatura robusta junto do par de botões. OCR do
    # "Ranking N/M" é BÔNUS (quando o tesseract está disponível).
    top = crop[int(0.06 * h):int(0.38 * h), :]
    tb, tg, tr = (float(top[:, :, i].mean()) for i in range(3))
    banner_blue = tb > tr + 15 and (tb + tg + tr) / 3 > 55
    if not banner_blue:
        return result                                  # par verde sem o banner -> não confirma

    mid = crop[int(0.36 * h):int(0.48 * h), :]
    m = _RANK.search(_ocr(mid))
    ranking = ('%s/%s' % (m.group(1), m.group(2))) if m else None

    # 3) Botão X (fechar) no canto superior direito do pop-up (fallback ao "Sair").
    close_box = None
    top = crop[:int(0.12 * h), int(0.80 * w):]
    tg = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)
    nt, _, stt, _ = cv2.connectedComponentsWithStats(np.uint8(tg > 120) * 255, 8)
    xs = [tuple(int(v) for v in stt[i, :4]) for i in range(1, nt)
          if 0.01 * w < stt[i, 2] < 0.08 * w and 0.01 * h < stt[i, 3] < 0.06 * h]
    if xs:
        bx, by, bw2, bh2 = xs[0]
        close_box = [bx + int(0.80 * w), by, bw2, bh2]

    return dict(status='TOURNAMENT_END', ranking=ranking,
                sair_box=list(sair), ficar_box=list(ficar), close_box=close_box,
                buttons=btns)
