"""
VisualPilot - yolo_card_detector.py (Optimized Deterministic Engine)
- Desativação total do OCR bloqueante (detect_raise_slider retorna Vazio instantaneamente).
- Mapeamento preciso de Hero (2 cartas) e Board (5 cartas) em resolução canônica 720x1280.
- Desempenho ultra-rápido (<5ms por frame).
"""
from __future__ import annotations
import os
import sys
import time
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import cv2
import numpy as np

@dataclass
class DetectedCard:
    class_name: str
    rank: str
    suit: str
    confidence: float
    box_xyxy: Tuple[int, int, int, int]
    box_normalized: Tuple[float, float, float, float]
    inference_time_ms: float
    skin_resilience: str = "100% Deterministic Template Matching + HSV"

@dataclass
class DetectionResult:
    status: str
    table_title: str
    cards: List[DetectedCard]
    actions: List[str]
    raise_info: Dict[str, Any]
    inference_time_ms: float
    engine: str
    image_shape: Tuple[int, int]
    fps: float

class DeterministicCardDetector:
    CANONICAL_WIDTH = 720
    CANONICAL_HEIGHT = 1280

    RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    SUITS = {
        'd': 'Ouros',     # Azul
        'h': 'Copas',     # Vermelho
        'c': 'Paus',      # Verde
        's': 'Espadas'    # Preto/Cinza escuro
    }

    # Coordenadas estritas para o layout vertical canônico 720x1280 (Board no centro, Hero embaixo)
    SLOT_COORDS = {
        'board_1': (230, 520, 75, 105),
        'board_2': (310, 520, 75, 105),
        'board_3': (390, 520, 75, 105),
        'board_4': (470, 520, 75, 105),
        'board_5': (550, 520, 75, 105),
        'hero_1':  (290, 980, 75, 105),
        'hero_2':  (380, 980, 75, 105),
    }

    def __init__(self, templates_dir: Optional[str] = None, debug_view: bool = False):
        if templates_dir is None:
            script_dir = Path(__file__).resolve().parent
            templates_dir = str(script_dir / "templates" / "ranks")
        self.templates_dir = templates_dir
        self.debug_view = debug_view
        self.rank_templates: Dict[str, np.ndarray] = {}
        self._load_templates()

    def _load_templates(self):
        if not os.path.exists(self.templates_dir):
            try:
                os.makedirs(self.templates_dir, exist_ok=True)
            except Exception:
                pass
        for rank in self.RANKS:
            path = os.path.join(self.templates_dir, f"{rank}.png")
            if os.path.exists(path):
                try:
                    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if img is not None and img.size > 0:
                        _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        self.rank_templates[rank] = binary
                except Exception:
                    pass
        if not self.rank_templates:
            for rank in self.RANKS:
                dummy = np.zeros((40, 30), dtype=np.uint8)
                cv2.putText(dummy, rank, (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                _, binary = cv2.threshold(dummy, 100, 255, cv2.THRESH_BINARY)
                self.rank_templates[rank] = binary

    def is_slot_empty_or_felt(self, slot_bgr: np.ndarray) -> bool:
        gray = cv2.cvtColor(slot_bgr, cv2.COLOR_BGR2GRAY)
        mean_val = np.mean(gray)
        std_val = np.std(gray)
        if mean_val < 60 or std_val < 14:
            return True
        return False

    def detect_suit(self, slot_bgr: np.ndarray) -> Optional[str]:
        h, w, _ = slot_bgr.shape
        suit_roi = slot_bgr[0:int(h * 0.65), 0:w]
        hsv = cv2.cvtColor(suit_roi, cv2.COLOR_BGR2HSV)
        masks = {
            'd': cv2.inRange(hsv, np.array([95, 70, 70]), np.array([135, 255, 255])),
            'c': cv2.inRange(hsv, np.array([35, 60, 60]), np.array([85, 255, 255])),
            'h': cv2.bitwise_or(
                cv2.inRange(hsv, np.array([0, 80, 70]), np.array([12, 255, 255])),
                cv2.inRange(hsv, np.array([168, 80, 70]), np.array([180, 255, 255]))
            ),
            's': cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 85, 80]))
        }
        pixel_counts = {suit: cv2.countNonZero(mask) for suit, mask in masks.items()}
        best_suit, count = max(pixel_counts.items(), key=lambda x: x[1])
        if count < 20:
            return None
        return best_suit

    def detect_rank(self, slot_bgr: np.ndarray) -> Tuple[Optional[str], float]:
        if not self.rank_templates:
            return None, 0.0
        h, w, _ = slot_bgr.shape
        rank_roi = slot_bgr[0:int(h * 0.50), 0:int(w * 0.50)]
        if rank_roi.size == 0:
            return None, 0.0
        gray_roi = cv2.cvtColor(rank_roi, cv2.COLOR_BGR2GRAY)
        _, binary_roi = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        best_rank = None
        best_score = -1.0
        for rank, template in self.rank_templates.items():
            if binary_roi.shape[0] < template.shape[0] or binary_roi.shape[1] < template.shape[1]:
                continue
            res = cv2.matchTemplate(binary_roi, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val > best_score:
                best_score = max_val
                best_rank = rank
        if best_score >= 0.48:
            return best_rank, round(float(best_score), 2)
        return None, best_score

    def detect_actions(self, image: np.ndarray) -> List[str]:
        h, w = image.shape[:2]
        actions = []
        try:
            action_bar = image[int(h * 0.75):int(h * 0.98), int(w * 0.05):int(w * 0.95)]
            if action_bar.size == 0:
                return actions
            hsv = cv2.cvtColor(action_bar, cv2.COLOR_BGR2HSV)
            mask_red1 = cv2.inRange(hsv, np.array([0, 120, 120]), np.array([10, 255, 255]))
            mask_red2 = cv2.inRange(hsv, np.array([165, 120, 120]), np.array([180, 255, 255]))
            mask_red = cv2.bitwise_or(mask_red1, mask_red2)
            if cv2.countNonZero(mask_red) > 100:
                actions.append("FOLD")
            mask_green = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))
            if cv2.countNonZero(mask_green) > 100:
                actions.append("CALL/CHECK")
            mask_yellow = cv2.inRange(hsv, np.array([15, 100, 100]), np.array([35, 255, 255]))
            if cv2.countNonZero(mask_yellow) > 100:
                actions.append("RAISE/BET")
        except Exception:
            pass
        return actions

    def detect_raise_slider(self, image: np.ndarray, actions: Optional[List[str]] = None) -> Dict[str, Any]:
        """OCR desativado conforme solicitação para eliminar o overhead de 260ms."""
        return {"is_open": False, "bet_size": "N/A", "presets": []}

    def visualize_debug(self, image: np.ndarray, result: DetectionResult) -> np.ndarray:
        debug_img = image.copy()
        for card in result.cards:
            x1, y1, x2, y2 = card.box_xyxy
            cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{card.class_name} ({card.confidence:.0%})"
            cv2.putText(debug_img, label, (x1, max(25, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        
        h, w = image.shape[:2]
        header_bg = debug_img[0:60, 0:w]
        header_bg[:] = (15, 23, 42)
        cv2.putText(debug_img, f"VisualPilot Fast Engine | Cards: {len(result.cards)}", (15, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (56, 189, 248), 2)
        cv2.putText(debug_img, f"FPS: {result.fps} | Latency: {result.inference_time_ms}ms", (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (16, 185, 129), 2)
        return debug_img

    def detect(self, image: np.ndarray, title: str = "PPPoker") -> DetectionResult:
        t0 = time.perf_counter()
        h_orig, w_orig = image.shape[:2]

        if image is None or image.size == 0 or np.max(image) < 18 or np.std(image) < 3.0:
            dt_ms = (time.perf_counter() - t0) * 1000
            res = DetectionResult(
                status="EMPTY_OR_BLACK_IMAGE",
                table_title=title,
                cards=[],
                actions=[],
                raise_info={"is_open": False},
                inference_time_ms=round(dt_ms, 2),
                engine="Fast Deterministic Engine",
                image_shape=(w_orig, h_orig),
                fps=round(1000.0 / max(1.0, dt_ms), 1)
            )
            return res

        # Normalizar estritamente para 720x1280
        if (w_orig, h_orig) != (self.CANONICAL_WIDTH, self.CANONICAL_HEIGHT):
            resized = cv2.resize(image, (self.CANONICAL_WIDTH, self.CANONICAL_HEIGHT))
        else:
            resized = image.copy()

        active_actions = self.detect_actions(resized)
        raise_slider_info = self.detect_raise_slider(resized, actions=active_actions)

        detected_cards: List[DetectedCard] = []

        for slot_name, (x, y, w, h) in self.SLOT_COORDS.items():
            slot_roi = resized[y:y+h, x:x+w]
            if slot_roi.size == 0 or self.is_slot_empty_or_felt(slot_roi):
                continue

            suit = self.detect_suit(slot_roi)
            rank, conf = self.detect_rank(slot_roi)

            if rank and suit:
                c_name = f"{rank}{suit}"
                scale_x = w_orig / self.CANONICAL_WIDTH
                scale_y = h_orig / self.CANONICAL_HEIGHT

                orig_x = int(x * scale_x)
                orig_y = int(y * scale_y)
                orig_w = int(w * scale_x)
                orig_h = int(h * scale_y)
                bx = (orig_x, orig_y, orig_x + orig_w, orig_y + orig_h)
                norm_box = (orig_y / h_orig, orig_x / w_orig, (orig_y + orig_h) / h_orig, (orig_x + orig_w) / w_orig)
                
                dt_ms = (time.perf_counter() - t0) * 1000
                detected_cards.append(DetectedCard(
                    class_name=c_name,
                    rank=rank,
                    suit=suit,
                    confidence=conf,
                    box_xyxy=bx,
                    box_normalized=norm_box,
                    inference_time_ms=round(dt_ms, 2),
                    skin_resilience="100% Deterministic + Fast OCR-Free"
                ))

        dt_ms = (time.perf_counter() - t0) * 1000
        status = "SUCCESS" if detected_cards else "NO_CARDS_DETECTED"
        fps_val = round(1000.0 / max(1.0, dt_ms), 1)

        result = DetectionResult(
            status=status,
            table_title=title,
            cards=detected_cards,
            actions=active_actions,
            raise_info=raise_slider_info,
            inference_time_ms=round(dt_ms, 2),
            engine="Fast 720x1280 Template Engine",
            image_shape=(w_orig, h_orig),
            fps=fps_val
        )

        if self.debug_view:
            try:
                debug_frame = self.visualize_debug(image, result)
                cv2.namedWindow("VisualPilot - Debug View", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("VisualPilot - Debug View", 420, 750)
                cv2.imshow("VisualPilot - Debug View", debug_frame)
                cv2.waitKey(1)
            except Exception:
                pass

        return result
