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
import numpy as np
from .ocr_runtime import image_to_string
from .seat_layout import SEAT_ANCHORS, nameplate_box, avatar_box
from .dealer_button import find_dealer_seat, derive_positions

# A seat is occupied when its NAMEPLATE (the dark name/stack pill) is present. We
# test it by blue fraction: the pill is never blue (occupied 0.09-0.30 on real
# crops), while an empty seat shows blue felt or the green "Empty" button (0.61
# measured on a real empty seat, ~1.00 for bare felt). The threshold sits in the
# gap. The nameplate is used, not the avatar, because a blue-themed avatar (e.g.
# an underwater photo) reads as felt and caused a false 'empty'.
OCCUPANCY_BLUE = 0.45
_OCCLUSION_STD = 15.0  # a flat, dark nameplate box is likely covered by a panel (bet slider)

_WITH_COMMA = re.compile(r'(\d{1,4})[.,](\d)\s*B')
# Some skins (Evolution) render the decimal comma as a gap: "35,5" -> "35 5BB".
_SPACE_DECIMAL = re.compile(r'(\d{1,4})\s+(\d)\s*[BR8]{2}')
# Trailing unit is "BB", often OCR'd as BR/RR/B8; accept two of [BR8]. The digit
# run must not be glued to a letter: a bet chip or the stats grid overlapping a
# nameplate yields garbage like "alecaixeta R20RB", where "20RB" would otherwise
# be read as 2.0. Requiring a non-letter before the digits turns that dangerous
# misread into a safe abstention, while real stacks ("...AABui 760BB") still read.
_DIGITS_BB = re.compile(r'(?<![A-Za-z])(\d{2,5})\s*[BR8]{2}')


def parse_amount(text):
    """(value_bb, confidence) from a nameplate/pot OCR string, or (None, 'abstain').

    'high' when a decimal comma is present; 'medium' when only digits followed by
    BB are seen and the single decimal is restored (X,X). Never guesses otherwise."""
    t = (text or '').replace('O', '0').replace('o', '0')
    m = _WITH_COMMA.search(t)
    if m:
        return float('%s.%s' % (m.group(1), m.group(2))), 'high'
    m = _SPACE_DECIMAL.search(t)
    if m:
        return float('%s.%s' % (m.group(1), m.group(2))), 'medium'
    m = _DIGITS_BB.search(t)
    if m and len(m.group(1)) <= 4:
        # No comma: restore the single decimal (X,X). A 5+ digit run is OCR noise
        # (e.g. "15,3" misread as "15232"), so abstain rather than invent a value.
        d = m.group(1)
        return float('%s.%s' % (d[:-1], d[-1])), 'medium'
    return None, 'abstain'


def _ocr(gray, config):
    return ' '.join(image_to_string(gray, config=config).split())


def read_seat_stacks(crop):
    """Per-seat {stack_bb, confidence, source, raw}. Occupancy is separate
    (read_occupancy): a seat can be occupied yet have an unreadable stack."""
    seats = {}
    for seat in SEAT_ANCHORS:
        x0, y0, x1, y1 = nameplate_box(crop.shape[1], crop.shape[0], seat)
        raw = _ocr(cv2.cvtColor(crop[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY), '--psm 6')
        value, conf = parse_amount(raw)
        seats[seat] = dict(stack_bb=value, confidence=conf, source='ocr', raw=raw)
    return seats


def _felt_blue_and_std(region):
    if region.size == 0:
        return 1.0, 0.0
    b, g, r = region[:, :, 0].astype(int), region[:, :, 1].astype(int), region[:, :, 2].astype(int)
    blue = float(((b > r + 20) & (b > g + 10) & (b > 60)).mean())
    std = float(region.reshape(-1, 3).std(axis=0).mean())
    return blue, std


def read_occupancy(crop):
    """Per-seat occupancy from the nameplate box: occupied when the dark name/stack
    pill is present (not empty blue felt). A flat, dark box (bet slider over the
    seat) is still 'occupied' but flagged occluded_suspected, since we cannot
    confirm or read it there."""
    out = {}
    H, W = crop.shape[0], crop.shape[1]
    for seat in SEAT_ANCHORS:
        x0, y0, x1, y1 = nameplate_box(W, H, seat)
        blue, std = _felt_blue_and_std(crop[y0:y1, x0:x1])
        occupied = blue < OCCUPANCY_BLUE
        source = 'nameplate'
        if not occupied:
            # FALLBACK pelo AVATAR (foto do jogador). O box do nameplate nos assentos
            # do TOPO mistura nameplate + chip de aposta + feltro (ex.: top_center/SB
            # dava blue~0.51, borderline → marcava VAZIO e desalinhava TODAS as
            # posições). O avatar é limpo: foto clara → blue baixo (0.03–0.56);
            # assento vazio (feltro ou botão 'Empty') → blue alto (~0.72–0.99). Um
            # corte CONSERVADOR em 0.5 só confirma foto nítida, sem risco de FP no
            # 'Empty' (~0.72). Resolve a Camada 2 (ocupação → posições corretas).
            ax0, ay0, ax1, ay1 = avatar_box(W, H, seat)
            av_blue, _ = _felt_blue_and_std(crop[ay0:ay1, ax0:ax1])
            if av_blue < 0.5:
                occupied, source = True, 'avatar'
        out[seat] = dict(occupied=occupied, felt_blue=round(blue, 3), source=source,
                         occluded_suspected=bool(occupied and source == 'nameplate'
                                                 and blue < 0.1 and std < _OCCLUSION_STD))
    return out


# Pot label box as (fx0, fy0, fx1, fy1), from the gabarito.
POT_BOX = (0.33, 0.34, 0.63, 0.38)


def read_pot(crop):
    h, w = crop.shape[:2]
    fx0, fy0, fx1, fy1 = POT_BOX
    region = crop[int(fy0 * h):int(fy1 * h), int(fx0 * w):int(fx1 * w)]
    raw = _ocr(cv2.cvtColor(region, cv2.COLOR_BGR2GRAY), '--psm 7')
    value, conf = parse_amount(raw)
    return dict(pot_bb=value, confidence=conf, source='ocr', raw=raw)


def read_to_call(crop):
    """Hero's amount to call, taken from the action buttons the game shows: the
    Call button's amount, or 0 when a Check is offered (nothing to call). None
    when there is no button row (not the hero's turn / unknown). This reads the
    displayed amount, not an inference from other seats' bets."""
    from .action_buttons import read_action_buttons
    buttons = read_action_buttons(crop).get('buttons', [])
    for button in buttons:
        if button.get('action') == 'CALL' and button.get('amount') is not None:
            if button.get('unit') != 'BB':
                # The amount has no confirmed BB unit: do not assume it is in big
                # blinds (it could be chips). Unknown unit stays unknown.
                return dict(to_call_bb=None, confidence='abstain',
                            source='call_button_unit_unknown', raw=button.get('label'))
            return dict(to_call_bb=float(button['amount']), confidence='high',
                        source='call_button', raw=button.get('label'))
    if any(b.get('action') == 'CHECK' for b in buttons):
        return dict(to_call_bb=0.0, confidence='high', source='check_button', raw='Check')
    return dict(to_call_bb=None, confidence='abstain', source='buttons', raw=None)


def _detect_red_chips(crop):
    """Bounding centres (cx, cy, w, h) of the red bet chips on the felt.

    Only the felt band is searched: the top banner (flags, logo) and the bottom
    action bar also carry red, and their numbers were being read as phantom bets
    (e.g. a recurring 14.0bb from the US flag). Bets sit between the seats and the
    pot, well inside this band, so none are lost. Mirrors dealer_button's mask."""
    h, w = crop.shape[:2]
    b, g, r = crop[:, :, 0].astype(int), crop[:, :, 1].astype(int), crop[:, :, 2].astype(int)
    red = ((r > 130) & (r > g + 50) & (r > b + 40)).astype(np.uint8) * 255
    felt = np.zeros_like(red)
    felt[int(0.13 * h):int(0.86 * h), int(0.04 * w):int(0.96 * w)] = 255
    red = cv2.bitwise_and(red, felt)
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _, stats, cent = cv2.connectedComponentsWithStats(red, 8)
    chips = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if 12 < w < 60 and 10 < h < 50 and area > 120:
            chips.append((int(cent[i][0]), int(cent[i][1]), int(w), int(h)))
    return chips


def read_bets(crop):
    """Bets on the felt, found by their red chip and the amount beside it,
    attributed to the nearest seat (approximate). The pot chip is skipped by its
    'Pot' label. Observation only; a seat with no chip simply has no bet, and the
    one-decimal rule applies to a dropped comma as elsewhere."""
    h, w = crop.shape[:2]
    # Rejeita chips sobre o AVATAR de um assento OCUPADO: elementos vermelhos/laranjas
    # das FOTOS (timer, roupa, logo) viram falso-positivo de 'chip'. Uma aposta real
    # fica no FELTRO (entre o assento e o pote), nunca sobre a foto. Usa a ocupação
    # confiável (fallback por avatar) pra saber quais fotos estão presentes.
    occ = read_occupancy(crop)
    avatars = [avatar_box(w, h, s) for s, v in occ.items() if v.get('occupied')]
    occupied_seats = [s for s, v in occ.items() if v.get('occupied')] or list(SEAT_ANCHORS)
    best = {}   # seat -> (dist2, bet_dict): UMA aposta por assento (chip mais perto dele)
    for cx, cy, cw, ch in _detect_red_chips(crop):
        if any(ax0 <= cx <= ax1 and ay0 <= cy <= ay1 for (ax0, ay0, ax1, ay1) in avatars):
            continue   # chip sobre avatar ocupado = falso-positivo, não é aposta
        # Filter the 'Pot: ...' chip with an unrestricted OCR of a wide region
        # (so the 'Pot' word survives), then read the amount to the RIGHT of the
        # chip, starting past the disc so its white suit symbol is not mistaken
        # for a digit. A digit/comma/B whitelist keeps the Evolution bet font's
        # noise from becoming a value (it read "1,5 BB" as "45 RR" -> 4.5); on a
        # hard read it now abstains (None) rather than a confident wrong number.
        label = _ocr(cv2.cvtColor(crop[max(0, cy - 16):cy + 16, max(0, cx - 10):min(w, cx + cw + 120)],
                                  cv2.COLOR_BGR2GRAY), '--psm 7')
        if 'ot' in label.lower():   # the 'Pot: ...' chip, not a bet
            continue
        # Valor à DIREITA do chip. `cx` é o CENTRO do chip (centroide), então a região
        # começa na borda direita (cx + cw//2), NÃO em cx+cw (que pulava meio chip e
        # cortava os 1os dígitos). Altura ±0.02h (a ±16px fixa CORTAVA o texto na
        # vertical e perdia/erravas apostas — ex.: o raise de 4bb do vilão). Upscale
        # 4x + OTSU deixam o OCR confiável (validado: 0,5 / 0,9 / 1,0 / 4,0 -> 4/4).
        rx0 = min(w, cx + cw // 2 + 2)
        rx1 = min(w, cx + cw // 2 + int(0.16 * w))
        ry0, ry1 = max(0, cy - int(0.02 * h)), min(h, cy + int(0.02 * h))
        region = crop[ry0:ry1, rx0:rx1]
        if region.size == 0:
            continue
        g = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        up = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        _, th = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        raw = _ocr(th, '--psm 7 -c tessedit_char_whitelist=0123456789.,B ')
        value, conf = parse_amount(raw)
        if value is None:
            continue
        # Atribui ao assento OCUPADO mais próximo (não a um vazio) e mantém UMA aposta
        # por assento: a do chip mais PERTO do jogador (o chip real fica junto dele;
        # um chip central/morto fica longe e perde p/ o verdadeiro → sem phantom).
        seat = min(occupied_seats, key=lambda s: (SEAT_ANCHORS[s][0] * w - cx) ** 2 + (SEAT_ANCHORS[s][1] * h - cy) ** 2)
        d2 = (SEAT_ANCHORS[seat][0] * w - cx) ** 2 + (SEAT_ANCHORS[seat][1] * h - cy) ** 2
        if seat not in best or d2 < best[seat][0]:
            best[seat] = (d2, dict(seat=seat, bet_bb=value, confidence=conf, source='chip', chip=[cx, cy], raw=raw))
    return [b for _, b in best.values()]


_BREAK_CLOCK = re.compile(r'(\d{1,2})\s*[:.\-]\s*(\d{2})')


def read_break_state(crop):
    """Detecta o INTERVALO do torneio: overlay central 'Pausa' + contador MM:SS.
    Retorna {in_break, countdown, seconds}. Durante o intervalo não há botões de
    ação e o operador espera; este detector deixa o estado EXPLÍCITO (faixa mostra
    'EM INTERVALO mm:ss') e serve ao runner da rotina (saber que o jogo está pausado).

    Calibrado no skin Karekas (REENTRY): 'Pausa' ~y0.43–0.49, contador ~y0.49–0.57,
    centralizado. O contador usa upscale+OTSU + whitelist de dígitos/':'."""
    out = dict(in_break=False, countdown=None, seconds=None)
    if not isinstance(crop, np.ndarray) or crop.ndim != 3 or crop.shape[2] != 3:
        return out
    h, w = crop.shape[:2]
    lbl = crop[int(0.43 * h):int(0.49 * h), int(0.30 * w):int(0.70 * w)]
    if lbl.size == 0:
        return out
    label = _ocr(cv2.cvtColor(lbl, cv2.COLOR_BGR2GRAY), '--psm 7').lower()
    if 'pausa' not in label and 'break' not in label and 'interval' not in label:
        return out
    out['in_break'] = True
    band = crop[int(0.49 * h):int(0.57 * h), int(0.28 * w):int(0.72 * w)]
    if band.size:
        g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
        up = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, th = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        raw = _ocr(th, '--psm 7 -c tessedit_char_whitelist=0123456789:.-')
        m = _BREAK_CLOCK.search(raw)
        if m:
            mm, ss = int(m.group(1)), int(m.group(2))
            out['countdown'] = '%02d:%02d' % (mm, ss)
            out['seconds'] = mm * 60 + ss
    return out


def read_table_state(crop):
    """Experimental table state: per-seat stacks, pot, dealer button and derived
    positions. Per-seat bets and to-call are placeholders (None) for the next
    increment, never inferred from cards or buttons. Positions use the occupancy
    implied by readable stacks, so an unreadable (occluded) seat can shift them;
    that limitation rides on the stacks' own confidence."""
    if crop is None or crop.ndim != 3 or crop.shape[2] != 3:
        raise ValueError('Expected a BGR table crop')
    stacks = read_seat_stacks(crop)
    occupancy = read_occupancy(crop)
    seats = {s: dict(stacks[s], occupied=occupancy[s]['occupied'], felt_blue=occupancy[s]['felt_blue'],
                     occupancy_source='avatar', occluded_suspected=occupancy[s]['occluded_suspected'])
             for s in SEAT_ANCHORS}
    dealer = find_dealer_seat(crop)
    occupied = [s for s in SEAT_ANCHORS if seats[s]['occupied']]
    positions = derive_positions(dealer['seat'], occupied) if dealer['seat'] else {}
    return dict(experimental=True, scope='BLUE_LAYOUT_PASSIVE_READING', source='ocr',
                seats=seats, pot=read_pot(crop), dealer=dealer, positions=positions,
                to_call=read_to_call(crop), bets=read_bets(crop))
