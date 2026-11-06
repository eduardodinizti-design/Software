"""Exact OCR reuse within one snapshot only. No cross-frame card state."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import numpy as np
import pytesseract

_state = ContextVar('snapshot_ocr', default=None)
MAX_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 256

@contextmanager
def ocr_frame(enabled=True):
    existing = _state.get()
    if existing is not None:
        yield existing['stats']
        return
    state = dict(enabled=enabled, cache={}, stats=dict(requests=0, calls=0, hits=0, bytes=0))
    token = _state.set(state)
    try:
        yield state['stats']
    finally:
        _state.reset(token)
        state['cache'].clear()


def image_to_string(image, **kwargs):
    state = _state.get()
    if state is None:
        return pytesseract.image_to_string(image, **kwargs)
    stats = state['stats']; stats['requests'] += 1
    key = None
    if state['enabled'] and isinstance(image, np.ndarray) and image.dtype == np.uint8 and image.nbytes <= MAX_BYTES:
        try:
            options = tuple(sorted(kwargs.items()))
            hash(options)
            key = (image.shape, image.dtype.str, image.tobytes(), options, pytesseract.pytesseract.tesseract_cmd)
        except TypeError:
            pass
    if key is not None and key in state['cache']:
        stats['hits'] += 1
        return state['cache'][key]
    stats['calls'] += 1
    result = pytesseract.image_to_string(image, **kwargs)
    # Errors never reach here, and mutable/non-string outputs are not retained.
    if key is not None and isinstance(result, str):
        size = len(key[2]) + len(result.encode('utf8'))
        if len(state['cache']) < MAX_ENTRIES and stats['bytes'] + size <= MAX_BYTES:
            state['cache'][key] = result
            stats['bytes'] += size
    return result


def snapshot_ocr(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with ocr_frame() as stats:
            result = function(*args, **kwargs)
            result['ocr_work'] = dict(stats)
            return result
    return wrapped
