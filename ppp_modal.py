"""Detector do modal "Confirma saída?" do PPPoker (offline, por imagem — não OCR).

ACHADO 22/11 (fixture real multitable_tiled): o modal que aparecia na mesa NÃO é "voltar do
sit-out" como se supunha — é a confirmação de SAÍDA DA MESA:
  "O jogo está em andamento. Suas mãos serão jogadas pelo sistema se você sair. Confirma saída?"
com o botão verde **"Confirmar"** (= CONFIRMA A SAÍDA) e **"Voltar"** (= cancela/permanece).

=> Clicar "Confirmar" FAZ O HERÓI SAIR DA MESA (pior que sit-out). Este detector serve pra
DETECTAR o modal e BLINDAR contra isso: NUNCA clicar Confirmar automaticamente. A ação de
permanecer ("Voltar") precisa de 1 confirmação AO VIVO antes de ser automatizada.

Assinatura do "Confirmar": botão verde VIVO e SÓLIDO (preenchido), largo, no miolo do painel
(exclui as abas verdes do topo). Verde ~ BGR (135,163,91). READ-ONLY (só analisa imagem).
"""
from __future__ import annotations

import cv2
import numpy as np

HAZARD = "CONFIRMAR_CONFIRMA_SAIDA_DA_MESA__NUNCA_CLICAR_AUTOMATICO"


def _green_button_mask(img):
    """Máscara do verde-de-botão do PPPoker (verde vivo, G dominante)."""
    b = img[:, :, 0].astype(int)
    g = img[:, :, 1].astype(int)
    r = img[:, :, 2].astype(int)
    return ((g > 110) & (g - r > 35) & (g - b > 35)).astype(np.uint8) * 255


def find_exit_confirm_modal(img, panels, *, min_w=150, max_w=360, min_h=40, max_h=110,
                            top_exclude_frac=0.12):
    """Procura o botão "Confirmar" (= modal de saída) em cada painel. Devolve lista de
    {panel, confirmar_bbox, confirmar_center, hazard}. Vazia = nenhum modal.

    NUNCA use confirmar_center pra clicar automaticamente: clicar lá SAI DA MESA. É só p/
    DETECTAR o modal (e então tratar com cautela/ao vivo — a ação de permanecer é "Voltar")."""
    mask = _green_button_mask(img)
    k = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    H = img.shape[0]
    out = []
    for i, (x0, x1) in enumerate(panels):
        sub = k[:, x0:x1]
        cnts, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if w * h == 0:
                continue
            ar = w / float(h)
            fill = cv2.contourArea(c) / (w * h)
            # botão Confirmar: largo+cheio+altura de botão, no MIOLO (y além das abas do topo).
            if (min_w <= w <= max_w and min_h <= h <= max_h and 2.2 <= ar <= 5.5
                    and fill >= 0.7 and y > H * top_exclude_frac):
                if best is None or w * h > best[0]:
                    best = (w * h, x0 + x, y, w, h)
        if best:
            _, X, Y, W, Hh = best
            out.append(dict(panel=i, confirmar_bbox=(X, Y, W, Hh),
                            confirmar_center=(X + W // 2, Y + Hh // 2), hazard=HAZARD))
    return out
