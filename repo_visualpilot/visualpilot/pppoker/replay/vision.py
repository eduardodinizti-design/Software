"""Componente observacional recuperado do projeto enviado; ver docs/LEGACY_REUSE.md."""
from pathlib import Path
import re
import unicodedata
import cv2
import numpy as np
from .reader import ID
ASSETS = Path(__file__).parent.parent / 'assets'

def plain(text):
    return ''.join((c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))).replace(' ', '')

def box_of(poly):
    x, y = (min((p[0] for p in poly)), min((p[1] for p in poly)))
    return [int(x), int(y), int(max((p[0] for p in poly)) - x), int(max((p[1] for p in poly)) - y)]

def classify(rows, rgb):
    texts = [plain(t) for _, t, s in rows if s >= 0.8]
    if 'perfil' in texts and any((re.search('ID\\s*[:：]?\\s*\\d{4,20}', t, re.I) for _, t, s in rows if s >= 0.9)):
        return 'profile'
    if any((ID.fullmatch(t.replace(' ', '')) for _, t, s in rows if s >= 0.9)) and any(('resumode' in t or 'detalhes' in t for t in texts)):
        return 'replay'
    if 'marcar' in texts and ('confirmar' in texts or any(('limitede200' in t for t in texts))):
        return 'note'
    from ..discovery import table_anchor_visible
    if table_anchor_visible(rgb):
        return 'table'
    if any((t in {'clube', 'clubes', 'meusclubes', 'login', 'entrar'} for t in texts)):
        return 'lobby'
    return 'unknown'

def live_hand_id(rows):
    ids = []
    for _, t, s in rows:
        m = ID.search(t.replace(' ', ''))
        if m and s >= 0.9:
            ids.append(m.group())
    return ids[0] if len(set(ids)) == 1 else None

def occupied_labels(rows, rgb):
    """Only nickname labels immediately above a stack, outside the action bar."""
    height, width = rgb.shape[:2]
    result = []
    for b, t, s in rows:
        bb = box_of(b)
        cx = bb[0] + bb[2] / 2
        cy = bb[1] + bb[3] / 2
        if s < 0.85 or not re.fullmatch('\\d+(?:[.,]\\d+)*\\s*(?:BB|[KM])?', t, re.I):
            continue
        if not 0.1 * height < cy < 0.93 * height:
            continue
        options = []
        for nb, name, score in rows:
            box = box_of(nb)
            nx = box[0] + box[2] / 2
            ny = box[1] + box[3] / 2
            if score >= 0.85 and 0 < cy - ny < 0.045 * height and (abs(nx - cx) < 0.09 * width):
                if not re.fullmatch('[\\d., /]+', name) and (not re.fullmatch('\\d+(?:[.,]\\d+)*\\s*(?:BB|[KM])?', name, re.I)) and (plain(name) not in {'d', 'fold', 'call', 'raise', 'check', 'bet', 'pagar', 'apostar'}) and (not plain(name).startswith(('pot:', 'pote:', 'id:', 'blinds', 'ante'))):
                    options.append((cy - ny, box, name, score))
        if not options:
            continue
        _, box, name, score = min(options)
        if any((abs(r['box'][1] + r['box'][3] / 2 - (box[1] + box[3] / 2)) < 5 and abs(r['box'][0] - box[0]) < 5 for r in result)):
            continue
        result.append(dict(box=box, nickname=name, score=score, control='profile_label'))
    return sorted(result, key=lambda p: (p['box'][1], p['box'][0]))
