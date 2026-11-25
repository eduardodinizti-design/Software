"""Multi-table TILADO: o PPPoker PC renderiza N mesas lado a lado numa ÚNICA janela
OS (grade horizontal). Este módulo detecta os PAINÉIS de mesa dentro do frame e liga
cada painel ao seu `table_ref` do protobuf (estado_mesa.json), para o operador
perceber+clicar POR MESA em vez de cruzar as mesas.

Ver [[nvt-multitable-tiled-bug]]. READ-ONLY: só analisa pixels + texto, nunca clica.
"""
from __future__ import annotations

import re

import cv2
import numpy as np

from table_reading.ocr_runtime import image_to_string

__all__ = ["detect_table_panels", "bind_panels_to_refs"]


def detect_table_panels(frame, *, min_frac_w=0.08, min_frac_h=0.25,
                        complete_grid=True, band_thresh=0.02, expected_n=None):
    """Detecta os painéis de mesa (colunas claras contra fundo preto) via projeção de
    brilho por coluna. Retorna lista de (x, y, w, h) no FRAME físico, ordenada por x.

    PPPoker tila horizontalmente, então a assinatura é uma sequência de BANDAS de
    colunas claras separadas por vãos escuros. Para cada banda (x), recortamos o
    y por projeção de brilho nas linhas daquela banda.

    Painel escurecido por MODAL (ex.: "Dicas… Confirmar", volta do sit-out) cai do
    limiar de brilho e sumiria da detecção direta. Como o PPPoker tila em COLUNAS
    IGUAIS, `complete_grid` reconstrói a grade: da banda de conteúdo + largura
    mediana dos painéis brilhantes (confiáveis) infere N e SINTETIZA os slots que
    faltam (herdando y/h mediano). Assim a 3ª mesa coberta pelo modal continua um
    painel endereçável — sem baixar limiar p/ "forçar" nada (ver
    [[nvt-multitable-tiled-bug]] fix #2). `expected_n` é só pista de desempate.
    """
    fh, fw = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # "não-preto": a mesa (azul) é bem mais clara que o fundo preto da janela.
    mask = (gray > 28).astype(np.uint8)
    col = mask.mean(axis=0)                      # fração de pixels claros por coluna
    on = col > 0.15                              # coluna pertence a um painel?
    # agrupa colunas contíguas em bandas
    bands = []
    x = 0
    while x < fw:
        if on[x]:
            x0 = x
            while x < fw and on[x]:
                x += 1
            if (x - x0) >= min_frac_w * fw:
                bands.append((x0, x))
        else:
            x += 1
    panels = []
    for x0, x1 in bands:
        sub = mask[:, x0:x1]
        row = sub.mean(axis=1)
        ys = np.where(row > 0.15)[0]
        if ys.size == 0:
            continue
        y0, y1 = int(ys.min()), int(ys.max())
        if (y1 - y0) < min_frac_h * fh:
            continue
        panels.append((int(x0), y0, int(x1 - x0), int(y1 - y0)))
    panels.sort(key=lambda p: p[0])
    if complete_grid and panels:
        panels = _complete_equal_grid(col, panels, band_thresh=band_thresh,
                                      expected_n=expected_n)
    return panels


def _complete_equal_grid(col, bright, *, band_thresh=0.02, expected_n=None):
    """Reconstrói a grade de N colunas IGUAIS a partir dos painéis brilhantes `bright`
    (confiáveis) e da banda de conteúdo (projeção `col`). Painéis cobertos por modal
    (dim) viram slots SINTÉTICOS no lugar certo, herdando y/h mediano dos brilhantes.

    Invariante usada: PPPoker tila em colunas de MESMA largura, lado a lado. Logo N =
    round(largura_da_banda / largura_mediana_dos_paineis). Não inventa mesa onde não
    há conteúdo: a banda (limiar baixo) delimita onde há pixels de mesa.
    """
    # banda de conteúdo = colunas com QUALQUER brilho (pega o painel dim do modal).
    xs = np.where(col > band_thresh)[0]
    if xs.size == 0:
        return bright
    x_lo = min(int(xs.min()), min(p[0] for p in bright))
    x_hi = max(int(xs.max()) + 1, max(p[0] + p[2] for p in bright))
    band_w = x_hi - x_lo
    pw = int(np.median([p[2] for p in bright]))
    if pw <= 0:
        return bright
    n = int(round(band_w / pw))
    if expected_n:
        # a pista do protobuf só decide quando a geometria está indecisa (empate .5)
        if abs(band_w / pw - round(band_w / pw)) > 0.33:
            n = int(expected_n)
    n = max(n, len(bright))        # nunca menos painéis do que os já vistos
    if n <= len(bright):
        return bright
    slot_w = band_w / n
    y_med = int(np.median([p[1] for p in bright]))
    h_med = int(np.median([p[3] for p in bright]))
    out = []
    for i in range(n):
        c_lo = int(round(x_lo + i * slot_w))
        c_hi = int(round(x_lo + (i + 1) * slot_w))
        c_center = (c_lo + c_hi) / 2
        # já existe painel brilhante neste slot? (centro dele cai na coluna i)
        hit = next((p for p in bright if c_lo <= (p[0] + p[2] / 2) < c_hi), None)
        if hit is not None:
            out.append(hit)
        else:
            out.append((c_lo, y_med, c_hi - c_lo, h_med))
    out.sort(key=lambda p: p[0])
    return out


_ROOM_CLEAN = re.compile(r"[^A-Z0-9 ]+")


def _room_in_panel(frame, panel):
    """OCR do cabeçalho do painel (faixa superior) p/ ler o nome do torneio/sala."""
    x, y, w, h = panel
    top = frame[y:y + max(1, int(0.10 * h)), x:x + w]
    gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)
    txt = image_to_string(gray, config="--psm 6")
    return _ROOM_CLEAN.sub(" ", txt.upper())


def bind_panels_to_refs(frame, panels, estado):
    """Liga cada painel ao `table_ref` do protobuf casando o NOME DA SALA lido no
    cabeçalho do painel com `estado[ref]['room']`. Retorna lista paralela a `panels`
    de refs (ou None quando não casou). Sem adivinhação: casa só por substring do room.
    """
    rooms = {ref: (v.get("room") or "").strip().upper() for ref, v in estado.items()}
    out = []
    used = set()
    for panel in panels:
        head = _room_in_panel(frame, panel)
        match = None
        for ref, room in rooms.items():
            if ref in used or not room:
                continue
            # casa se TODAS as palavras do room aparecem no cabeçalho lido
            if all(tok in head for tok in room.split()):
                match = ref
                break
        if match:
            used.add(match)
        out.append(match)
    return out
