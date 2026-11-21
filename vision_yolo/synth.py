"""Gerador de DATASET SINTÉTICO p/ o detector YOLO de cartas — SEM Frida, SEM rotular à mão.

Ideia: renderiza as 52 cartas (estilo padrão de poker: carta branca, rank+naipe, vermelho p/
♦♥ e preto p/ ♣♠) e COMPÕE sobre FUNDOS DE MESA REAIS (capturas da Suprema) nos SLOTS do
layout (hero + board), com variação (posição/escala/brilho). Como o gerador POSICIONA cada
carta, o rótulo YOLO sai de graça. Treina offline; valida nas capturas reais; depois fine-tune
com dados reais auto-rotulados (F1-live) quando o Frida voltar. Ver nvt-visao-yolo-decisao.
"""
from __future__ import annotations

import os
import random

from PIL import Image, ImageDraw, ImageFont

from vision_yolo.classes import NAME_TO_ID, CARD_CLASSES
from vision_yolo import suprema_layout as SL

SUIT_SYM = {'d': '♦', 'h': '♥', 'c': '♣', 's': '♠'}
SUIT_RED = {'d', 'h'}
_FONTS = ('arial.ttf', 'arialbd.ttf', 'segoeui.ttf', 'DejaVuSans.ttf')


def _font(size):
    for name in _FONTS:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_card(name, w=120, h=168):
    """PIL RGBA de uma carta ('As','Td',...) no estilo padrão de poker."""
    img = Image.new('RGBA', (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(w * 0.12),
                        outline=(170, 170, 170), width=max(2, w // 50))
    rank, suit = name[0], name[1]
    color = (200, 28, 28) if suit in SUIT_RED else (20, 20, 20)
    d.text((int(w * 0.10), int(h * 0.02)), rank, fill=color, font=_font(int(h * 0.34)))
    d.text((int(w * 0.10), int(h * 0.40)), SUIT_SYM[suit], fill=color, font=_font(int(h * 0.30)))
    return img


def _paste_card(bg, name, box, jitter=0.0):
    """Cola a carta renderizada em `box`=(cx,cy,w,h) frac; devolve o box REAL (c/ jitter)."""
    W, H = bg.size
    cx, cy, w, h = box
    if jitter:
        cx += random.uniform(-jitter, jitter); cy += random.uniform(-jitter, jitter)
        s = 1 + random.uniform(-jitter, jitter); w *= s; h *= s
    pw, ph = max(8, int(w * W)), max(10, int(h * H))
    card = render_card(name, pw, ph)
    if random.random() < 0.5:                      # leve variação de brilho
        from PIL import ImageEnhance
        card = ImageEnhance.Brightness(card).enhance(random.uniform(0.82, 1.0))
    x0, y0 = int(cx * W - pw / 2), int(cy * H - ph / 2)
    bg.alpha_composite(card, (x0, y0))
    return (cx, cy, w, h)


def make_scene(background, hero=(), board=()):
    """Compõe hero+board sobre o fundo. Devolve (imagem RGB, labels[(cls,cx,cy,w,h)])."""
    bg = background.convert('RGBA').copy()
    labels = []
    for name, slot in zip(hero, SL.HERO_CARD_SLOTS):
        b = _paste_card(bg, name, slot, jitter=0.01)
        labels.append((NAME_TO_ID[name], *b))
    for name, slot in zip(board, SL.BOARD_SLOTS):
        b = _paste_card(bg, name, slot, jitter=0.01)
        labels.append((NAME_TO_ID[name], *b))
    return bg.convert('RGB'), labels


def _rand_deal():
    deck = random.sample(CARD_CLASSES, 7)
    nboard = random.choice([0, 0, 3, 4, 5])        # pré-flop mais comum
    return deck[:2], deck[2:2 + nboard]


def generate(backgrounds, n, images_dir, labels_dir, seed=None):
    """Gera `n` cenas rotuladas a partir dos fundos. Escreve images/*.png + labels/*.txt."""
    if seed is not None:
        random.seed(seed)
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)
    bgs = [Image.open(p) for p in backgrounds]
    for i in range(n):
        bg = random.choice(bgs)
        hero, board = _rand_deal()
        img, labels = make_scene(bg, hero, board)
        stem = 'synth_%05d' % i
        img.save(os.path.join(images_dir, stem + '.png'))
        with open(os.path.join(labels_dir, stem + '.txt'), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join('%d %.6f %.6f %.6f %.6f' % lb for lb in labels))
    return n
