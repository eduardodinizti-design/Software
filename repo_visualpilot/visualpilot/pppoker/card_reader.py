"""Leitor especializado de Hero e board a partir dos recortes calibrados."""
from __future__ import annotations

from time import perf_counter
import re

import cv2
import numpy as np

from .card_rank import rank_field
from .readers import BaseRegionReader, valid_rgb
from .replay.cards import face, rectangles
from .training.perception import suit


CARD_REGIONS = {"hero_cards": 2, "board_flop": 3,
                "board_turn": 1, "board_river": 1}


class CardRegionReader(BaseRegionReader):
    """Segmenta cartas reais e rejeita valor, naipe ou duplicidade incertos."""
    def __init__(self, field_reader, minimum_rank_confidence: float = .90, *, colored_deck: bool = False):
        super().__init__("cards")
        self.field_reader = field_reader
        self.colored_deck = colored_deck
        self.minimum_rank_confidence = minimum_rank_confidence

    def _rank(self, crop):
        return rank_field(self.field_reader, crop, self.minimum_rank_confidence)

    def _pending(self, region, started, reason, diagnostics=None):
        return {"region": region, "status": "PENDING", "cards": [],
                "reason": reason, "diagnostics": diagnostics or {},
                "latency_sec": perf_counter() - started}

    def _board(self, image, expected):
        boxes = sorted(rectangles(image, 25, 125), key=lambda box: box[0])
        # A região pode conter decorações claras; cartas formam uma linha central.
        if boxes:
            median_y = float(np.median([box[1] + box[3] / 2 for box in boxes]))
            boxes = [box for box in boxes if abs(box[1] + box[3] / 2 - median_y) < 18]
        if len(boxes) != expected:
            return [], {"candidate_count": len(boxes), "boxes": boxes}

        class RankReader:
            def __init__(self, outer): self.outer = outer
            def field(self, crop): return self.outer._rank(crop)

        cards = []
        diagnostics = []
        for box in boxes:
            card, rank, confidence, symbol = face(
                RankReader(self), image, box, self.minimum_rank_confidence)
            accepted = bool(card and re.fullmatch(r"[2-9TJQKA][shdc]", card))
            diagnostics.append({"box": box, "rank_candidate": rank,
                                "rank_confidence": float(confidence),
                                "suit_candidate": symbol, "accepted": accepted})
            if not accepted:
                return [], {"candidate_count": len(boxes), "cards": diagnostics}
            cards.append({"card": card, "confidence": float(confidence), "box": box})
        return cards, {"candidate_count": len(boxes), "cards": diagnostics}

    def _hero_pair_box(self, image):
        candidates = []
        for threshold in (165, 100):
            light = ((image.min(2) > threshold) &
                     ((image.max(2).astype("int16") - image.min(2)) < 40))
            _, _, stats, _ = cv2.connectedComponentsWithStats(light.astype("uint8"))
            parts = [list(map(int, row)) for row in stats[1:]
                     if 65 < row[3] < 150 and .25 < row[2] / row[3] < 1.15
                     and row[4] / (row[2] * row[3]) > .55]
            boxes = [part for part in parts if .95 < part[2] / part[3] < 1.15]
            for first in parts:
                for second in parts:
                    x, y, width, height, area = first
                    xx, yy, w2, h2, area2 = second
                    # Separate paper components can have bounding boxes that
                    # overlap by one pixel after desktop capture/resampling.
                    if (-1 <= xx - (x + width) <= 8 and abs(y - yy) <= 3
                            and abs(height - h2) <= 4
                            and .95 < (xx + w2 - x) / max(height, h2) < 1.15):
                        boxes.append([x, min(y, yy), xx + w2 - x,
                                      max(height, h2), area + area2])
            if len(boxes) == 1:
                candidates = boxes
                break
        return candidates[0][:4] if len(candidates) == 1 else None

    def _hero(self, image):
        pair = self._hero_pair_box(image)
        if pair is None:
            return [], {"candidate_count": 0}
        x, y, width, height = pair
        paper = image[y:y + height, x:x + width]
        neutral = paper[(paper.max(2).astype("int16") - paper.min(2)) < 40]
        level = float(np.percentile(neutral, 80)) if neutral.size else 255.
        working = image.copy()
        if 95 < level < 210:
            working[y:y + height, x:x + width] = np.clip(
                paper.astype("float32") * (245 / level), 0, 255).astype("uint8")
        cards, diagnostics = [], []
        for index, card_x in enumerate((x, x + round(width * .34))):
            rank, rank_score = self._rank(
                working[y:y + round(height * .36),
                        card_x:card_x + round(height * .28)])
            rank = "T" if rank.upper() == "10" else rank.upper()
            suit_details = {}
            symbol, suit_score = suit(
                working[y + round(height * .36):y + round(height * .58),
                        card_x + round(height * .035):card_x + round(height * .29)],
                suit_details)
            accepted = bool(re.fullmatch(r"[2-9TJQKA]", rank) and
                            rank_score >= self.minimum_rank_confidence and symbol)
            card = rank + symbol if accepted else None
            confidence = min(float(rank_score), float(suit_score)) if accepted else 0.
            diagnostics.append({"slot": index, "rank_candidate": rank,
                                "rank_confidence": float(rank_score),
                                "suit_candidate": symbol,
                                "suit_confidence": float(suit_score),
                                "accepted": accepted, "suit_diagnostics": suit_details})
            if not accepted:
                return [], {"pair_box": pair, "cards": diagnostics}
            cards.append({"card": card, "confidence": confidence,
                          "box": [card_x, y, round(height * .29), round(height * .58)]})
        return cards, {"pair_box": pair, "cards": diagnostics}

    def read_region(self, region_name, roi_img, *, occupied=()):
        started = perf_counter()
        if region_name not in CARD_REGIONS:
            return self._pending(region_name, started, "Região de cartas desconhecida.")
        if not valid_rgb(roi_img) or roi_img.shape[0] < 20 or roi_img.shape[1] < 20:
            return self._pending(region_name, started, "Recorte de cartas inválido.")
        expected = CARD_REGIONS[region_name]
        cards, diagnostics = (self._hero(roi_img) if region_name == "hero_cards"
                              else self._board(roi_img, expected))
        if not cards and self.colored_deck:
            from .colored_cards import read_colored
            cards, diagnostics = read_colored(
                roi_img, self.field_reader, expected, self.minimum_rank_confidence)
        values = [item["card"] for item in cards]
        conflicts = set(values) & set(occupied)
        if len(cards) != expected:
            return self._pending(region_name, started, "Cartas incompletas ou ambíguas.", diagnostics)
        if len(set(values)) != len(values) or conflicts:
            diagnostics["conflicts"] = sorted(conflicts or set(values))
            return self._pending(region_name, started, "Cartas duplicadas; leitura rejeitada.", diagnostics)
        return {"region": region_name, "status": "SUCCESS", "cards": cards,
                "diagnostics": diagnostics, "latency_sec": perf_counter() - started}
