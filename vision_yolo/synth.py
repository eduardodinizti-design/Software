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
# Baralho 2 cores (padrão): ♦♥ vermelho, ♣♠ preto. Baralho 4 CORES: cada naipe uma cor
# (♠ preto, ♥ vermelho, ♦ AZUL, ♣ VERDE) — elimina a confusão ♦↔♥ e vira leitura por COR
# (robusta, agnóstica de desenho) em qualquer sala que ofereça o baralho de 4 cores.
SUIT_COLOR_2 = {'d': (200, 28, 28), 'h': (200, 28, 28), 'c': (20, 20, 20), 's': (20, 20, 20)}
SUIT_COLOR_4 = {'d': (24, 86, 196), 'h': (200, 28, 28), 'c': (22, 140, 60), 's': (20, 20, 20)}
FOUR_COLOR = False                                 # make_train_data liga p/ gerar 4 cores
_FONTS = ('arial.ttf', 'arialbd.ttf', 'segoeui.ttf', 'DejaVuSans.ttf')


def _font(size):
    for name in _FONTS:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_suit(d, suit, box, color):
    """Desenha o pip do naipe por GEOMETRIA VETORIAL (nítido em qualquer escala) em
    box=(x0,y0,x1,y1). Silhuetas inconfundíveis: ♦ rombo pontudo, ♥ topo redondo/base
    pontuda, ♠ ♥ invertido + haste, ♣ três círculos + haste. Resolve a confusão ♦↔♥."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if suit == 'd':                                        # losango: 4 pontas
        d.polygon([(cx, y0), (x1, cy), (cx, y1), (x0, cy)], fill=color)
    elif suit == 'h':                                      # coração: 2 lóbulos + ponta p/ baixo
        d.ellipse([x0, y0, x0 + w * 0.56, y0 + h * 0.60], fill=color)
        d.ellipse([x1 - w * 0.56, y0, x1, y0 + h * 0.60], fill=color)
        d.polygon([(x0 + w * 0.02, y0 + h * 0.34), (x1 - w * 0.02, y0 + h * 0.34),
                   (cx, y1)], fill=color)
    elif suit == 's':                                      # espada: coração invertido + haste
        d.ellipse([x0, y0 + h * 0.40, x0 + w * 0.56, y0 + h * 1.0], fill=color)
        d.ellipse([x1 - w * 0.56, y0 + h * 0.40, x1, y0 + h * 1.0], fill=color)
        d.polygon([(cx, y0), (x0 + w * 0.02, y0 + h * 0.66),
                   (x1 - w * 0.02, y0 + h * 0.66)], fill=color)
        d.polygon([(cx - w * 0.16, y1), (cx + w * 0.16, y1),
                   (cx + w * 0.06, y0 + h * 0.70), (cx - w * 0.06, y0 + h * 0.70)], fill=color)
    else:                                                  # paus (c): 3 círculos + haste
        r = w * 0.30
        d.ellipse([cx - r, y0, cx + r, y0 + 2 * r], fill=color)
        d.ellipse([x0, cy - r * 0.2, x0 + 2 * r, cy + r * 1.8], fill=color)
        d.ellipse([x1 - 2 * r, cy - r * 0.2, x1, cy + r * 1.8], fill=color)
        d.polygon([(cx - w * 0.12, y1), (cx + w * 0.12, y1),
                   (cx + w * 0.05, cy), (cx - w * 0.05, cy)], fill=color)


def render_card(name, w=120, h=168):
    """PIL RGBA de uma carta ('As','Td',...) no estilo da Suprema: rank no canto + pip de
    canto + pip central, naipe desenhado por GEOMETRIA (não glifo de fonte)."""
    img = Image.new('RGBA', (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(w * 0.12),
                        outline=(170, 170, 170), width=max(2, w // 50))
    rank, suit = name[0], name[1]
    color = (SUIT_COLOR_4 if FOUR_COLOR else SUIT_COLOR_2)[suit]
    d.text((int(w * 0.09), int(h * 0.01)), rank, fill=color, font=_font(int(h * 0.32)))
    # pip de canto (logo abaixo do rank) — o traço discriminante que o detector lê
    cpw, cph = w * 0.26, h * 0.17
    _draw_suit(d, suit, (w * 0.11, h * 0.36, w * 0.11 + cpw, h * 0.36 + cph), color)
    # pip central grande (reforça o sinal, como nas cartas de número reais)
    bpw, bph = w * 0.46, h * 0.30
    _draw_suit(d, suit, (w * 0.5 - bpw / 2, h * 0.52, w * 0.5 + bpw / 2, h * 0.52 + bph), color)
    return img


# rótulo + cor dos botões de ação (mimetiza a Suprema) e mapa ação->classe YOLO
_BTN = {
    'fold':  ('Desistir', (150, 48, 30)),
    'check': ('Passar',   (38, 120, 70)),
    'call':  ('Pagar',    (38, 120, 70)),
    'raise': ('Aumentar', (200, 130, 30)),
}
_BTN_CLASS = {'fold': 'btn_fold', 'check': 'btn_check', 'call': 'btn_call',
              'raise': 'btn_raise', 'all_in': 'btn_allin'}


def render_dealer(size=56):
    """Disco branco 'D' do dealer (ancora as posições)."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([1, 1, size - 2, size - 2], fill=(245, 245, 245, 255), outline=(120, 120, 120), width=2)
    f = _font(int(size * 0.6))
    d.text((int(size * 0.30), int(size * 0.14)), 'D', fill=(30, 30, 30), font=f)
    return img


def render_button(action, w=250, h=80):
    """Botão de ação (rounded rect colorido + rótulo), estilo Suprema."""
    label, fill = _BTN.get(action, ('?', (90, 90, 90)))
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(h * 0.22), fill=fill + (255,))
    f = _font(int(h * 0.42))
    tw = d.textlength(label, font=f)
    d.text(((w - tw) / 2, int(h * 0.25)), label, fill=(240, 240, 240), font=f)
    return img


def _paste_rgba(bg, card, box, jitter=0.0):
    """Cola uma imagem RGBA em box=(cx,cy,w,h) frac; devolve o box real."""
    import random as _r
    W, H = bg.size
    cx, cy, w, h = box
    if jitter:
        cx += _r.uniform(-jitter, jitter); cy += _r.uniform(-jitter, jitter)
    pw, ph = max(8, int(w * W)), max(8, int(h * H))
    card = card.resize((pw, ph))
    bg.alpha_composite(card, (int(cx * W - pw / 2), int(cy * H - ph / 2)))
    return (cx, cy, w, h)


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


def make_scene(background, hero=(), board=(), dealer=None, buttons=()):
    """Compõe hero+board (+ dealer + botões) sobre o fundo. Devolve (RGB, labels[(cls,cx,cy,w,h)])."""
    bg = background.convert('RGBA').copy()
    labels = []
    for name, slot in zip(hero, SL.HERO_CARD_SLOTS):
        labels.append((NAME_TO_ID[name], *_paste_card(bg, name, slot, jitter=0.01)))
    for name, slot in zip(board, SL.BOARD_SLOTS):
        labels.append((NAME_TO_ID[name], *_paste_card(bg, name, slot, jitter=0.01)))
    if dealer and dealer in SL.SEATS:
        cx, cy = SL.SEATS[dealer]
        box = (cx + (0.5 - cx) * 0.18, cy + (0.5 - cy) * 0.18, 0.035, 0.022)   # desloca p/ dentro
        _paste_rgba(bg, render_dealer(), box)
        labels.append((NAME_TO_ID['dealer_button'], *box))
    for act in buttons:
        slot = SL.BUTTONS.get(act)
        cls = _BTN_CLASS.get(act)
        if slot and cls and cls in NAME_TO_ID:
            _paste_rgba(bg, render_button(act), slot)
            labels.append((NAME_TO_ID[cls], *slot))
    return bg.convert('RGB'), labels


def _rand_scene():
    deck = random.sample(CARD_CLASSES, 7)
    nboard = random.choice([0, 0, 3, 4, 5])        # pré-flop mais comum
    dealer = random.choice(list(SL.SEATS))
    r = random.random()
    buttons = [] if r < 0.3 else (['fold', 'call', 'raise'] if r < 0.65 else ['check', 'raise'])
    return deck[:2], deck[2:2 + nboard], dealer, buttons


def generate(backgrounds, n, images_dir, labels_dir, seed=None):
    """Gera `n` cenas rotuladas a partir dos fundos. Escreve images/*.png + labels/*.txt."""
    if seed is not None:
        random.seed(seed)
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)
    bgs = [Image.open(p) for p in backgrounds]
    for i in range(n):
        bg = random.choice(bgs)
        hero, board, dealer, buttons = _rand_scene()
        img, labels = make_scene(bg, hero, board, dealer, buttons)
        stem = 'synth_%05d' % i
        img.save(os.path.join(images_dir, stem + '.png'))
        with open(os.path.join(labels_dir, stem + '.txt'), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join('%d %.6f %.6f %.6f %.6f' % lb for lb in labels))
    return n
