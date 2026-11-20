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


def detect_table_panels(frame, *, min_frac_w=0.08, min_frac_h=0.25):
    """Detecta os painéis de mesa (colunas claras contra fundo preto) via projeção de
    brilho por coluna. Retorna lista de (x, y, w, h) no FRAME físico, ordenada por x.

    PPPoker tila horizontalmente, então a assinatura é uma sequência de BANDAS de
    colunas claras separadas por vãos escuros. Para cada banda (x), recortamos o
    y por projeção de brilho nas linhas daquela banda.
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
    return panels


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
