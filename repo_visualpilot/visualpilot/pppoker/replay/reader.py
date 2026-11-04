"""Componente observacional recuperado do projeto enviado; ver docs/LEGACY_REUSE.md."""
import re
import unicodedata
from datetime import datetime
import numpy as np
import cv2
ID = re.compile('\\d{12}-\\d{6,12}-\\d{7}-\\d+')
STREETS = {'preflop': 'preflop', 'flop': 'flop', 'turn': 'turn', 'river': 'river', 'showdown': 'showdown'}
POSITIONS = {'SB', 'BB', 'BTN', 'CO', 'HJ', 'UTG', 'UTG+1', 'UTG+2', 'MP', 'MP1', 'MP2', 'LJ'}

class ReplayReader:

    def __init__(self, *, intra_op_num_threads=2):
        from rapidocr_onnxruntime import RapidOCR
        # O texto do cliente aparece sempre na horizontal. O classificador de
        # rotação acrescentava uma inferência a cada caixa sem trazer evidência.
        self.engine = RapidOCR(intra_op_num_threads=intra_op_num_threads, inter_op_num_threads=1,
                               text_score=0.0, use_cls=False)

    def detect(self, rgb):
        if rgb.shape[0] <= 1600:
            rows, _ = self.engine(np.ascontiguousarray(rgb[:, :, ::-1]))
            return self.header_fields(rows or [], rgb)
        found = []
        for top in range(0, rgb.shape[0], 1200):
            bottom = min(rgb.shape[0], top + 1500)
            rows, _ = self.engine(np.ascontiguousarray(rgb[top:bottom, :, ::-1]))
            for b, t, s in rows or []:
                if top > 0 and min((p[1] for p in b)) < 3 or (bottom < rgb.shape[0] and max((p[1] for p in b)) > bottom - top - 3):
                    continue
                box = [[x, y + top] for x, y in b]
                cx = sum((p[0] for p in box)) / 4
                cy = sum((p[1] for p in box)) / 4
                duplicate = next((i for i, (ob, ot, os) in enumerate(found) if abs(sum((p[0] for p in ob)) / 4 - cx) < 8 and abs(sum((p[1] for p in ob)) / 4 - cy) < 8), None)
                if duplicate is None:
                    found.append((box, t, s))
                elif s > found[duplicate][2]:
                    found[duplicate] = (box, t, s)
            if bottom == rgb.shape[0]:
                break
        return self.header_fields(sorted(found, key=lambda row: (min((p[1] for p in row[0])), min((p[0] for p in row[0])))), rgb)

    def header_fields(self, rows, rgb):
        result = []
        for b, t, s in rows:
            normalized = unicodedata.normalize('NFKC', t).replace(' ', '')
            if s < 0.92 and re.fullmatch('[\\d,]+/[\\d,]+\\([\\d,]+\\)', normalized):
                x, y = (max(0, int(min((p[0] for p in b))) - 1), max(0, int(min((p[1] for p in b))) - 1))
                right, bottom = (int(max((p[0] for p in b))) + 1, int(max((p[1] for p in b))) + 1)
                value, score = self.field(rgb[y:bottom, x:right])
                if score > s:
                    t, s = (value, score)
            result.append((b, t, s))
        return result

    def field(self, rgb):
        if rgb.size == 0:
            return ('', 0.0)
        h, w = rgb.shape[:2]
        scale = max(1.0, min(4.0, 48 / h))
        enlarged = cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        rows, _ = self.engine(np.ascontiguousarray(enlarged[:, :, ::-1]), use_det=False, use_cls=False)
        if not rows or len(rows) != 1:
            return ('', 0.0)
        return (str(rows[0][0]).strip(), float(rows[0][1]))
