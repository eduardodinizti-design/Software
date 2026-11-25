"""INTEGRAÇÃO (capstone) da percepção por VISÃO da Suprema: junta tudo numa leitura ->
table_state do cérebro, SEM Frida.

  CARTAS  (hero/board)  <- YOLO (detector)        [split_hero_board]
  AÇÕES   (legais)      <- YOLO (botões)          [available_actions]
  POSIÇÕES              <- YOLO (dealer) + ativos  [positions.resolve_from_detections]
  STACKS  (em BB)       <- OCR fixo nos slots      [ocr_read.read_seats / STACK_REGIONS]

Produz o MESMO table_state que advise_from_reading consome. READ-ONLY (observa; não clica).
Falta só bets/pote exatos (OCR das regiões de aposta/pote) p/ o to_call numérico — por ora
to_call vem do botão (check disponível -> 0; call disponível -> faltando valor)."""
from __future__ import annotations

from vision_yolo.vision_state import split_hero_board, available_actions, street_from_board
from vision_yolo.positions import resolve_from_detections
from vision_yolo.ocr_read import read_seats
from vision_yolo import suprema_layout as SL

_FULL = (0.0, 0.0, 1.0, 1.0)
_ACT = {'allin': 'all_in'}                       # btn_allin -> ação do cérebro


def read_table(image, detector, *, conf=0.25, ocr=True):
    """(table_state, hero_cards) p/ advise_from_reading, ou (None, motivo). `detector` expõe
    .detect(image, conf) -> Detection[] (YOLO). `image` serve ao OCR dos stacks."""
    dets = detector.detect(image, conf=conf)
    hero_cards, board = split_hero_board(dets, _FULL)
    if len(hero_cards) != 2:
        return None, 'HERO_CARDS_UNKNOWN'

    stacks = read_seats(image, SL.STACK_REGIONS) if ocr else {}
    active = list(stacks.keys())
    if 'hero' not in active:
        active.append('hero')
    positions = resolve_from_detections(dets, active)
    if 'hero' not in positions:
        return None, 'POSICOES_INCONSISTENTES'

    legal = [_ACT.get(a, a) for a in available_actions(dets) if a != 'confirm']
    positions_state, seats, bets = {}, {}, []
    for seat in active:
        if seat not in positions:
            continue
        positions_state[seat] = positions[seat]
        seats[seat] = dict(stack_bb=stacks.get(seat), occupied=True, source='vision')
        bets.append(dict(seat=seat, bet_bb=0.0))     # TODO F3b: OCR das apostas por assento

    # to_call pela OFERTA de botão (valor exato = OCR do 'Pagar X BB', F3b)
    to_call = 0.0 if 'check' in legal else None
    n = len(board)
    state = dict(positions=positions_state, seats=seats, bets=bets, phase='mid',
                 source='vision', room='SupremaPoker',
                 scope=('POSTFLOP_VISION' if n >= 3 else 'PREFLOP_VISION'),
                 board=list(board), street=street_from_board(board),
                 legal_actions=sorted(legal), to_call={'to_call_bb': to_call},
                 pot={'pot_bb': None})
    return state, hero_cards


def advise_from_vision(image, detector, advisor, **kwargs):
    """Decide pela VISÃO, pelo MESMO cérebro/roteamento. Devolve o dict do advisor ou ABSTAIN."""
    state, hero_or_reason = read_table(image, detector)
    if state is None:
        return dict(status='ABSTAIN', reason=hero_or_reason, source='vision')
    return advisor.advise_from_reading(state, hero_or_reason, **kwargs)
