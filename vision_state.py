"""Percepção por VISÃO (YOLO) -> table_state genérico do cérebro. Traduz as DETECÇÕES do
detector (cartas/botões/elementos) na MESMA estrutura que advise_from_reading consome —
igual suprema_state/protobuf_state, mas a fonte é a TELA (crash-free, universal, multi-mesa).

Separação de responsabilidades (F0):
  - YOLO dá: CARTAS (hero/board), AÇÕES LEGAIS (botões), âncoras (dealer/assentos).
  - OCR nas regiões detectadas dá: NÚMEROS (stack/aposta/pote) e, com o dealer, as POSIÇÕES.
    Esses vêm INJETADOS em `seats` (F3 liga o OCR aqui). Mantém o adaptador testável offline.

Multi-mesa: `cluster_tables` agrupa as detecções por COLUNA (mesas tiladas lado a lado) ->
uma leitura por mesa. É o que resolve o cruzamento que o Frida tinha (nvt-multitable-tiled-bug).
READ-ONLY.
"""
from __future__ import annotations

from collections import namedtuple

import vision_classes as VC

# Detecção normalizada (0..1): classe, confiança, centro (cx,cy) e tamanho (w,h).
Detection = namedtuple('Detection', 'cls conf cx cy w h')

# Regiões padrão (fração da imagem) p/ separar cartas do HERÓI (rodapé central) do BOARD (centro).
DEFAULT_REGIONS = {
    'hero_cards': (0.28, 0.66, 0.78, 1.00),    # (x0,y0,x1,y1)
    'board':      (0.18, 0.28, 0.82, 0.64),
}


def _in(d, reg):
    x0, y0, x1, y1 = reg
    return x0 <= d.cx <= x1 and y0 <= d.cy <= y1


def extract_cards(dets, regions=None):
    """(hero_cards, board) como listas de strings ('Ad',...), pela REGIÃO do centro da carta.
    Hero = banda inferior-central (2 cartas face-up); board = centro (até 5), da esq p/ dir."""
    regions = regions or DEFAULT_REGIONS
    cards = [d for d in dets if VC.is_card(d.cls)]
    hero = sorted([d for d in cards if _in(d, regions['hero_cards'])], key=lambda d: d.cx)
    board = sorted([d for d in cards if _in(d, regions['board'])], key=lambda d: d.cx)
    return [d.cls for d in hero][:2], [d.cls for d in board][:5]


def legal_from_buttons(dets, min_conf=0.4):
    """Ações legais a partir dos botões detectados. 'confirm' não é ação (é passo de size)."""
    out = set()
    for d in dets:
        act = VC.BUTTON_TO_ACTION.get(d.cls)
        if act and act != 'confirm' and d.conf >= min_conf:
            out.add(act)
    return out


def cluster_tables(dets, max_tables=12, gap=0.05):
    """Agrupa detecções por COLUNA em cx (mesas tiladas lado a lado). Devolve lista de listas
    (uma por mesa, da esquerda p/ a direita). Resolve a leitura multi-mesa numa janela só."""
    if not dets:
        return []
    xs = sorted(set(round(d.cx, 3) for d in dets))
    # quebra em grupos onde o salto em cx > gap
    bounds = []
    start = xs[0]
    prev = xs[0]
    for x in xs[1:]:
        if x - prev > gap:
            bounds.append((start, prev))
            start = x
        prev = x
    bounds.append((start, prev))
    bounds = bounds[:max_tables]
    groups = [[] for _ in bounds]
    for d in dets:
        for i, (a, b) in enumerate(bounds):
            if a - gap <= d.cx <= b + gap:
                groups[i].append(d)
                break
    return [g for g in groups if g]


def build_table_state(detections, *, seats, regions=None, legal_min_conf=0.4):
    """(table_state, hero_cards) p/ advise_from_reading, ou (None, motivo).

    `seats` = info de assento INJETADA (do OCR, F3): lista de dicts
      {key:'hero'|'seatN', pos:<RangeLab>, stack_bb:float, bet_bb:float}.
    Cartas, board e ações legais saem das `detections` (YOLO). Mesma semântica de abstenção
    das outras fontes (sem herói com 2 cartas / sem assentos -> None, motivo)."""
    hero_cards, board = extract_cards(detections, regions)
    if len(hero_cards) != 2:
        return None, 'HERO_CARDS_UNKNOWN'
    if not seats:
        return None, 'SEM_ASSENTOS'
    hero = next((s for s in seats if s.get('key') == 'hero'), None)
    if hero is None or not hero.get('pos'):
        return None, 'POSICOES_INCONSISTENTES'

    positions, seat_map, bets = {}, {}, []
    for s in seats:
        k = s['key']
        positions[k] = s.get('pos')
        seat_map[k] = dict(stack_bb=s.get('stack_bb'), occupied=True, source='vision')
        bets.append(dict(seat=k, bet_bb=round(float(s.get('bet_bb') or 0.0), 4)))

    legal = legal_from_buttons(detections, min_conf=legal_min_conf)
    n = len(board)
    street = ('RIVER' if n >= 5 else 'TURN' if n == 4 else 'FLOP' if n == 3 else 'PREFLOP')
    max_bet = max((b['bet_bb'] for b in bets), default=0.0)
    hero_bet = next((b['bet_bb'] for b in bets if b['seat'] == 'hero'), 0.0)
    to_call_bb = round(max(0.0, max_bet - hero_bet), 2)
    state = dict(positions=positions, seats=seat_map, bets=bets, phase='mid',
                 source='vision', scope=('POSTFLOP_VISION' if n >= 3 else 'PREFLOP_VISION'),
                 board=list(board), street=street, legal_actions=sorted(legal),
                 to_call={'to_call_bb': to_call_bb}, pot={'pot_bb': None})
    return state, hero_cards


def advise_from_vision(detections, seats, advisor, *, regions=None, **kwargs):
    """Decide a partir das detecções + assentos (OCR), pelo MESMO cérebro/roteamento."""
    state, hero_or_reason = build_table_state(detections, seats=seats, regions=regions)
    if state is None:
        return dict(status='ABSTAIN', reason=hero_or_reason, source='vision')
    return advisor.advise_from_reading(state, hero_or_reason, **kwargs)
