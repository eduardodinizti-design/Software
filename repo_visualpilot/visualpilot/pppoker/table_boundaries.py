"""Experimental blue-table boundary proposal anchored by three green controls.

Produces candidates, not OCR authorization. Layouts without visible controls need
another detector; never invent boundaries when the anchors are missing.
"""
from itertools import combinations
import cv2
import numpy as np


def detect_control_anchored_tables(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    green = cv2.inRange(hsv, (38,70,60), (90,255,255))
    blue = cv2.inRange(hsv, (90,45,30), (130,255,255)) > 0
    controls = []
    for contour in cv2.findContours(green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x,y,w,h = cv2.boundingRect(contour)
        if w >= 45 and h >= 12 and 2.3 <= w/h <= 4.5 and cv2.contourArea(contour)/(w*h) >= .8:
            controls.append((x,y,w,h))
    result = []
    height,width = rgb.shape[:2]
    # Avoid combinatorial work on unrelated screens with many green elements.
    if len(controls) > 60:
        return []
    for group in combinations(controls,3):
        group = sorted(group)
        widths = [b[2] for b in group]; heights = [b[3] for b in group]
        unit = float(np.median(widths)); bh = float(np.median(heights))
        if max(widths)/min(widths)>1.2 or max(heights)/min(heights)>1.2:
            continue
        if max(b[1] for b in group)-min(b[1] for b in group) > bh*.15:
            continue
        if any(not 0 <= group[i+1][0]-(group[i][0]+group[i][2]) <= unit*.15 for i in (0,1)):
            continue
        left = group[0][0]; right = group[-1][0]+group[-1][2]
        span = right-left; margin = max(2,round(span*.02))
        x0,x1 = left-margin,right+margin
        bottom = max(b[1]+b[3] for b in group)+margin
        if x0 < 0 or x1 > width or bottom > height:
            continue
        button_top = min(b[1] for b in group)
        # Follow blue surface upward; short interruptions from cards/HUD are allowed.
        rows = blue[:button_top,x0:x1].mean(axis=1) >= .30
        hits = np.flatnonzero(rows)
        if not len(hits) or button_top-hits[-1] > span*.2:
            continue
        start = int(hits[-1]); previous = start
        for row in hits[-2::-1]:
            if previous-row > span*.08:
                break
            start = int(row); previous = int(row)
        table_height = bottom-start
        if start <= 0 or not 1.45 <= table_height/(x1-x0) <= 2.25:
            continue
        if blue[start:button_top,x0:x1].mean() < .40:
            continue
        box = (x0,start,x1-x0,table_height)
        if box not in result:
            result.append(box)
    return sorted(result)
