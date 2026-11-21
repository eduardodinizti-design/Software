"""Ponte de INFERENCIA: modelo YOLO treinado -> lista de `Detection` do vision_state.
Liga o detector ao mesmo adaptador que vira table_state -> cerebro. READ-ONLY (so le a imagem)."""
from __future__ import annotations

import os

from vision_yolo.vision_state import Detection

_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs", "cards", "weights", "best.pt")


class CardDetector:
    """Carrega o peso YOLO e detecta objetos (cartas/botoes) numa imagem -> Detection[]."""

    def __init__(self, weights=None):
        from ultralytics import YOLO
        self.model = YOLO(weights or _DEFAULT)

    def detect(self, image, conf=0.25, imgsz=768):
        """image = caminho, PIL.Image ou ndarray. Devolve Detection[] (box normalizado xyxy)."""
        res = self.model.predict(image, conf=conf, imgsz=imgsz, verbose=False)[0]
        out = []
        for b in res.boxes:
            cls_id = int(b.cls.item())
            c = float(b.conf.item())
            x0, y0, x1, y1 = b.xyxyn[0].tolist()
            out.append(Detection(cls_id, c, (x0, y0, x1, y1)))
        return out
