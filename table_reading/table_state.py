"""Experimental PPPoker table-state reader: per-seat stacks and the pot.

Observation only, labelled experimental. Each numeric field carries its source
(ocr), a confidence (high/medium) and the raw OCR text; a field that cannot be
read is None (abstain), never guessed. PPPoker stacks and the pot show one
decimal (X,X BB); when OCR drops the comma we restore it from that fixed rule,
at medium confidence. Dealer button, positions, per-seat bets and to-call are
NOT read here yet (returned as None) and must not be inferred from cards/buttons.

Validated on a real gabarito (9/9 seat stacks, pot) with both OCR backends; only
the blue 9-max layout at the gabarito scale is validated.
"""
import re
import cv2
from .ocr_runtime import image_to_string
from .seat_layout import SEAT_ANCHORS, nameplate_box
from .dealer_button import find_dealer_seat, derive_positions

_WITH_COMMA = re.compile(r'(\d{1,4})[.,](\d)\s*B')
_DIGITS_BB = re.compile(r'(\d{2,5})\s*B[BR8]')


def parse_amount(text):
    """(value_bb, confidence) from a nameplate/pot OCR string, or (None, 'abstain').

    'high' when a decimal comma is present; 'medium' when only digits followed by
    BB are seen and the single decimal is restored (X,X). Never guesses otherwise."""
    t = (text or '').replace('O', '0').replace('o', '0')
    m = _WITH_COMMA.search(t)
    if m:
        return float('%s.%s' % (m.group(1), m.group(2))), 'high'
    m = _DIGITS_BB.search(t)
    if m:
        d = m.group(1)
        return float('%s.%s' % (d[:-1], d[-1])), 'medium'
    return None, 'abstain'


def _ocr(gray, config):
    return ' '.join(image_to_string(gray, config=config).split())


def read_seat_stacks(crop):
    """Per-seat {stack_bb, confidence, source, raw, occupied}. occupied is a
    best-effort flag: True when a stack was read, so an unreadable seat reads as
    not occupied (a known false-negative risk, flagged by the confidence)."""
    seats = {}
    for seat in SEAT_ANCHORS:
        x0, y0, x1, y1 = nameplate_box(crop.shape[1], crop.shape[0], seat)
        raw = _ocr(cv2.cvtColor(crop[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY), '--psm 6')
        value, conf = parse_amount(raw)
        seats[seat] = dict(stack_bb=value, confidence=conf, source='ocr', raw=raw,
                           occupied=value is not None)
    return seats


# Pot label box as (fx0, fy0, fx1, fy1), from the gabarito.
POT_BOX = (0.33, 0.34, 0.63, 0.38)


def read_pot(crop):
    h, w = crop.shape[:2]
    fx0, fy0, fx1, fy1 = POT_BOX
    region = crop[int(fy0 * h):int(fy1 * h), int(fx0 * w):int(fx1 * w)]
    raw = _ocr(cv2.cvtColor(region, cv2.COLOR_BGR2GRAY), '--psm 7')
    value, conf = parse_amount(raw)
    return dict(pot_bb=value, confidence=conf, source='ocr', raw=raw)


def read_table_state(crop):
    """Experimental table state: per-seat stacks, pot, dealer button and derived
    positions. Per-seat bets and to-call are placeholders (None) for the next
    increment, never inferred from cards or buttons. Positions use the occupancy
    implied by readable stacks, so an unreadable (occluded) seat can shift them;
    that limitation rides on the stacks' own confidence."""
    if crop is None or crop.ndim != 3 or crop.shape[2] != 3:
        raise ValueError('Expected a BGR table crop')
    seats = read_seat_stacks(crop)
    dealer = find_dealer_seat(crop)
    occupied = [s for s, d in seats.items() if d['occupied']]
    positions = derive_positions(dealer['seat'], occupied) if dealer['seat'] else {}
    return dict(experimental=True, scope='BLUE_LAYOUT_PASSIVE_READING', source='ocr',
                seats=seats, pot=read_pot(crop), dealer=dealer, positions=positions,
                pending=dict(bets=None, to_call_bb=None))
