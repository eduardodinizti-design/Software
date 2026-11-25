"""POSIÇÕES por VISÃO: ancora as posições RangeLab nos assentos a partir do DEALER (botão 'D'
detectado pelo YOLO) + os assentos ATIVOS (os que o OCR leu stack, ou com cartas). Reusa
protobuf_state.assign_positions (mesma lógica de ordem horária + rótulos SB/BB/BTN/...).

Fecha a leitura de POSICAO sem Frida: dealer (YOLO) -> assento mais próximo -> rótulos."""
from __future__ import annotations

import math

from protobuf_state import assign_positions
from vision_yolo import suprema_layout as SL


def _angle(seat_key):
    cx, cy = SL.SEATS[seat_key]
    a = math.atan2(cx - 0.5, -(cy - 0.5))      # 0 no TOPO, cresce no sentido horário
    return a + 2 * math.pi if a < 0 else a


def clockwise_seats():
    """Assentos do layout em ordem HORÁRIA a partir do topo."""
    return sorted(SL.SEATS, key=_angle)


def nearest_seat(cx, cy):
    """Assento do layout mais próximo de (cx,cy) — mapeia o dealer_button detectado p/ assento."""
    return min(SL.SEATS, key=lambda k: (SL.SEATS[k][0] - cx) ** 2 + (SL.SEATS[k][1] - cy) ** 2)


def resolve_positions(active_seats, dealer_seat):
    """{seat_key: posição RangeLab} dos assentos ATIVOS, ancorado no dealer. {} se não der
    (dealer fora dos ativos ou <2 jogadores) — NÃO chuta posição."""
    order = [s for s in clockwise_seats() if s in active_seats]
    if dealer_seat not in order or len(order) < 2:
        return {}
    ids = list(range(len(order)))               # id = rank horário (0..n-1)
    dealer_id = order.index(dealer_seat)
    pos_by_id = assign_positions(ids, dealer_id, None, None)
    return {order[i]: pos_by_id[i] for i in ids if i in pos_by_id}


def resolve_from_detections(detections, active_seats):
    """Acha o dealer pela detecção 'dealer_button' (centro) e resolve as posições. Devolve {}
    se não há detecção de dealer."""
    deal = next((d for d in detections if d.name == 'dealer_button'), None)
    if deal is None:
        return {}
    return resolve_positions(active_seats, nearest_seat(deal.cx, deal.cy))
