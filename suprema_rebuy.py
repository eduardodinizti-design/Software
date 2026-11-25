"""Detector do modal REBUY da Suprema (por imagem). Política do Eduardo (22/11): fazer REBUY
SIMPLES ('Recompra') se der tempo; nunca Double, nunca Sair automático. Assinatura do modal:
DOIS botões LARANJA empilhados (Recompra em cima = rebuy simples; Double Rebuy embaixo) + 'Sair'
VERMELHO abaixo. Calibrado 22/11 (937x1666): Recompra fx≈0.807 fy≈0.572; Double 0.807/0.634;
Sair 0.507/0.775. READ-ONLY (só analisa imagem; a ação de clique é externa, cursor suave)."""
from __future__ import annotations

import cv2
import numpy as np


def _orange(img):
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    return ((r > 200) & (r - b > 90) & (g > 120) & (g < 200)).astype(np.uint8) * 255


def _red(img):
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    return ((r > 180) & (r - g > 70) & (r - b > 60) & (g < 140)).astype(np.uint8) * 255


def _buttons(mask, min_w=120, min_h=35, ar=(2.0, 8.0)):
    k = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((11, 31), np.uint8))
    cs, _ = cv2.findContours(k, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cs:
        x, y, w, h = cv2.boundingRect(c)
        if w >= min_w and h >= min_h and ar[0] <= w / float(h) <= ar[1]:
            out.append((x + w // 2, y + h // 2))
    return out


def find_rebuy(img):
    """Detecta o modal REBUY. Devolve {recompra, double, sair} em FRAÇÕES (fx,fy) do client,
    ou None. Exige o PADRÃO (2 laranjas empilhados + 1 vermelho largo abaixo) p/ não dar
    falso-positivo com outros botões laranja da UI."""
    h, w = img.shape[:2]
    orn = sorted(_buttons(_orange(img)), key=lambda p: p[1])
    red = _buttons(_red(img), min_w=200)
    for i in range(len(orn)):
        for j in range(i + 1, len(orn)):
            (x1, y1), (x2, y2) = orn[i], orn[j]
            if abs(x1 - x2) < 0.05 * w and 0.03 * h < abs(y1 - y2) < 0.12 * h:
                top, bot = ((x1, y1), (x2, y2)) if y1 < y2 else ((x2, y2), (x1, y1))
                sair = next(((rx, ry) for (rx, ry) in red if ry > bot[1]), None)
                if sair:
                    return dict(recompra=(top[0] / w, top[1] / h),
                                double=(bot[0] / w, bot[1] / h),
                                sair=(sair[0] / w, sair[1] / h))
    return None
