"""Read the tournament phase from the table and map it to a strategy stage.

The PPPoker table prints "Lugares pagos: N" (paid places) and "Minha posicao:
rank/left" (left = players remaining). From those we pick the ICM stage the range
pack models (pre_itm / bubble / ft) or fall back to chip EV far from the money.

These thresholds are a first proposal, to calibrate with use; every answer says
which stage was chosen so it is never silent. No capture, no clicks.
"""
import re

import cv2

from .ocr_runtime import image_to_string

FINAL_TABLE = 9
_PAID = re.compile(r'pagos[:\s]*(\d+)', re.I)
_POSITION = re.compile(r'posi\w*[:\s]*(\d+)\s*/\s*(\d+)', re.I)   # OCR reads "posigao: 40/55"
_NAME = re.compile(r'^(.*?)\s*Blinds', re.I)
_PKO = re.compile(r'\bP?KO\b|BOUNTY', re.I)


def is_pko(name):
    """Whether the tournament name marks a bounty (PKO/KO/Bounty) event.
    Unvalidated against a real PKO table yet (no gabarito); calibrate when one
    arrives."""
    return bool(name) and bool(_PKO.search(name))


def read_tournament(crop):
    """{paid, players_left, hero_rank, name, is_pko, raw, confidence}."""
    h, w = crop.shape[:2]
    region = crop[int(0.49 * h):int(0.62 * h), int(0.25 * w):int(0.75 * w)]
    raw = ' '.join(image_to_string(cv2.cvtColor(region, cv2.COLOR_BGR2GRAY), config='--psm 6').split())
    paid = _PAID.search(raw)
    pos = _POSITION.search(raw)
    name = _NAME.search(raw)
    paid_n = int(paid.group(1)) if paid else None
    left_n = int(pos.group(2)) if pos else None
    rank_n = int(pos.group(1)) if pos else None
    name_s = name.group(1).strip() if name else None
    conf = 'high' if (paid_n and left_n) else ('medium' if (paid_n or left_n) else 'abstain')
    return dict(paid=paid_n, players_left=left_n, hero_rank=rank_n, name=name_s,
                is_pko=is_pko(name_s), raw=raw, confidence=conf)


def tournament_stage(players_left, paid):
    """ICM stage the pack models, or 'far' (chip EV), or None if unknown.

    ft at the final table; bubble just before the money; pre_itm approaching it;
    'far' when deep before the money. In the money but before the final table has
    no matching pack stage, so it returns None (the caller uses chip EV)."""
    if not isinstance(players_left, int) or not isinstance(paid, int) or players_left <= 0 or paid <= 0:
        return None
    if players_left <= FINAL_TABLE:
        return 'ft'
    if players_left <= paid:          # in the money, before the final table: no pack stage
        return None
    band = max(1, round(0.15 * paid))
    if players_left <= paid + band:
        return 'bubble'
    if players_left <= round(paid * 1.6):
        return 'pre_itm'
    return 'far'


def tournament_context(tourney):
    """(mode, stage) for the advisor, from the phase and whether it is a PKO:
    near the money -> icm / pko_icm at that stage; far or unknown -> chip_ev / pko
    at 'mid'. PKO detection is by name and still unvalidated."""
    stage = tournament_stage(tourney.get('players_left'), tourney.get('paid'))
    pko = bool(tourney.get('is_pko'))
    if stage in ('ft', 'bubble', 'pre_itm'):
        return ('pko_icm' if pko else 'icm'), stage
    return ('pko' if pko else 'chip_ev'), 'mid'
