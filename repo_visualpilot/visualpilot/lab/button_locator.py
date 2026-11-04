"""Visual button localization with explicit crop origin and ambiguous-match rejection."""
import math
from pathlib import Path

import cv2
import numpy as np


def load_template(path):
    image = cv2.imread(str(Path(path)), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f'Template ausente ou inválido: {Path(path).name}')
    return image


def gray(image):
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
            or image.ndim not in (2, 3) or not image.size
            or image.shape[0] * image.shape[1] > 16 * 1024 * 1024):
        raise ValueError('Imagem inválida ou acima do limite.')
    if image.ndim == 3:
        if image.shape[2] != 3:
            raise ValueError('Imagem deve ter três canais BGR.')
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def overlap(a, b):
    x, y, w, h = a
    xx, yy, ww, hh = b
    area = max(0, min(x+w, xx+ww)-max(x, xx))*max(0, min(y+h, yy+hh)-max(y, yy))
    return area / min(w*h, ww*hh)


def locate_button(image, template, *, origin=(0, 0), scales=(.75, 1., 1.25, 1.5, 2.), threshold=.92):
    """Coordinates are image pixels plus origin, never an OS click permission.

    Collapse overlapping response peaks/scales belonging to the same button.
    Two spatially distinct candidates are ambiguous, regardless of which scores best.
    """
    source, target = gray(image), gray(template)
    if not math.isfinite(threshold) or not .8 <= threshold <= 1:
        raise ValueError('Limiar inválido.')
    if len(origin) != 2 or any(type(v) is not int for v in origin):
        raise ValueError('Origem do recorte inválida.')
    if not 1 <= len(scales) <= 10 or any(not math.isfinite(s) or not .25 <= s <= 4 for s in scales):
        raise ValueError('Escalas inválidas.')
    if min(target.shape) < 5 or float(target.std()) < 2:
        raise ValueError('Template sem detalhes suficientes.')
    candidates = []
    for scale in scales:
        width, height = (round(target.shape[1]*scale), round(target.shape[0]*scale))
        if min(width, height) < 5 or width > source.shape[1] or height > source.shape[0]:
            continue
        resized = cv2.resize(target, (width, height), interpolation=cv2.INTER_LINEAR)
        response = cv2.matchTemplate(source, resized, cv2.TM_CCOEFF_NORMED)
        for _ in range(16):
            _, score, _, (x, y) = cv2.minMaxLoc(response)
            if not math.isfinite(score) or score < threshold:
                break
            candidates.append(dict(box=(x, y, width, height), score=score, scale=scale))
            # Nearby peaks represent the same visual object, not separate buttons.
            response[max(0, y-height//2):y+height//2+1,
                     max(0, x-width//2):x+width//2+1] = -1
        else:
            return dict(status='ambiguous', reason='too_many_matches', candidates=[])
    unique = []
    for candidate in sorted(candidates, key=lambda item: item['score'], reverse=True):
        if not any(overlap(candidate['box'], other['box']) > .5 for other in unique):
            unique.append(candidate)
    if len(unique) != 1:
        return dict(status='ambiguous' if unique else 'missing', candidates=unique)
    match = unique[0]
    x, y, width, height = match['box']
    return dict(status='found', box=[x+origin[0], y+origin[1], width, height],
                point=[x+origin[0]+width/2, y+origin[1]+height/2],
                score=match['score'], scale=match['scale'])
