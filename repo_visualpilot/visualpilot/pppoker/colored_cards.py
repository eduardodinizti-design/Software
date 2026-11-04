"""Candidate reader for the solid-colour PPPoker deck.

Explicit opt-in until independent real-frame coverage is available. Background
colour proposes the suit; a visible glyph and OCR agreement are also required.
"""
from pathlib import Path
import re
import cv2
import numpy as np
from .replay.cards import normalized


def candidates(image):
    r, g, b = image.astype(float).transpose(2, 0, 1)
    low, high = image.min(2), image.max(2)
    masks = {'h': (r > g*1.7) & (r > b*1.7) & (r > 30),
             'c': (g > r*1.7) & (g > b*1.7) & (g > 25),
             'd': (b > r*1.7) & (b > g*1.25) & (b > 30),
             's': (high.astype(float)-low < 18) & (low > 22) & (high < 145)}
    found = []
    for symbol, mask in masks.items():
        kernel = np.ones((3, 3), np.uint8)
        # Remove JPEG edge bridges before closing small background gaps.
        mask = cv2.morphologyEx(mask.astype('uint8'), cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        for x, y, w, h, area in stats[1:]:
            if (h >= 45 and .27 < w/h < .80 and area/(w*h) > .55
                    and x > 0 and y > 0 and x+w < image.shape[1]
                    and y+h < image.shape[0]):
                found.append((list(map(int, (x, y, w, h))), symbol))
    return sorted(found, key=lambda item: item[0][0])


def read_colored(image, reader, expected, minimum_rank_confidence=.95):
    boxes = candidates(image)
    diagnostics = {'deck': 'solid_colour_candidate', 'candidate_count': len(boxes), 'cards': []}
    if len(boxes) != expected:
        return [], diagnostics
    heights = [box[3] for box, _ in boxes]
    if max(heights)/min(heights) > 1.12 or max(box[1] for box, _ in boxes)-min(box[1] for box, _ in boxes) > max(heights)*.08:
        return [], diagnostics
    cards = []
    for box, symbol in boxes:
        x, y, w, h = box
        crop = image[y:y+h, x:x+w]
        v = crop.min(2).astype(float)
        spread = crop.max(2).astype(float)-v
        mask = ((spread < 35) & (v > max(35, np.percentile(v, 95)*.7))).astype('uint8')*255
        binary = mask[:round(h*.36), :round(h*.30)]
        gx, gy, gw, gh = cv2.boundingRect(binary)
        if not gw or not gh:
            return [], diagnostics
        glyphs = [('binary', 255-binary[gy:gy+gh, gx:gx+gw])]
        # A fixed fallback preserves antialiasing when JPEG fragments a thin 1.
        inset = max(1, round(h*.025))
        soft = v[inset:round(h*.36), inset:round(h*.30)]
        background, foreground = np.percentile(v, 60), np.percentile(soft, 98)
        if foreground-background >= 15:
            soft = (255-np.clip((soft-background)/(foreground-background), 0, 1)*255).astype('uint8')
            glyphs.append(('antialiased', soft))
        attempts = []
        for route, glyph in glyphs:
            votes = []
            for padding in (5, 9):
                clean = cv2.copyMakeBorder(glyph, padding, padding, padding, padding,
                                           cv2.BORDER_CONSTANT, value=255)
                value, score = reader.field(np.repeat(clean[:, :, None], 3, axis=2))
                value = value.upper()
                votes.append(('T' if value == '10' else value, float(score)))
            attempts.append(dict(route=route, votes=votes))
            if (votes[0][0] == votes[1][0] and re.fullmatch('[2-9TJQKA]', votes[0][0])
                    and min(v[1] for v in votes) >= max(.95, minimum_rank_confidence)):
                break
        shape = normalized(mask[round(h*.36):round(h*.61), :round(h*.24)])
        reference = cv2.imread(str(Path(__file__).parent/'assets'/f'suit_{symbol}.png'), 0)
        similarity = 0.
        if reference is not None:
            target = normalized(reference)
            similarity = float((shape & target).sum()/max(1, (shape | target).sum()))
        accepted = (votes[0][0] == votes[1][0] and re.fullmatch('[2-9TJQKA]', votes[0][0])
                    and min(v[1] for v in votes) >= max(.95, minimum_rank_confidence) and similarity >= (.76 if symbol == 's' else .60))
        diagnostics['cards'].append(dict(box=box, suit=symbol, shape_similarity=similarity,
                                         rank_votes=votes, rank_attempts=attempts, accepted=bool(accepted)))
        if not accepted:
            return [], diagnostics
        cards.append(dict(card=votes[0][0]+symbol, confidence=min(v[1] for v in votes), box=box))
    return cards, diagnostics
