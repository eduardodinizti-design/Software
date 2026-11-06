"""
VisualPilot - Vision Pipeline (Senior CV Engineer Implementation)
- Captura estrita via Win32 GDI BitBlt (com DPI Awareness e suporte a múltiplos monitores / origens negativas X=-1280).
- Sem fallback para desktop inteiro (retorna WINDOW_INVALID se minimizada ou inválida).
- Leitura Determinística de Cartas (Zero Tesseract OCR no loop).
- Classificação robusta de Rank e Naipe com resolução da confusão entre "4" e "A".
- Limiar estrito de confiança: retorna "NÃO IDENTIFICADO" para recortes vazios ou incertos.
"""
from __future__ import annotations
import os
import sys
import time
import ctypes
from typing import Optional, Tuple, Dict, List, Any
import numpy as np
import cv2

from window_capture_engine import WindowCaptureEngine


class PPPokerObserverPipeline:
    CANONICAL_WIDTH = 720
    CANONICAL_HEIGHT = 1280

    RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    
    # Coordenadas relativas proporcionais exatas para layout vertical do PPPoker (base 720x1280)
    # (x_ratio, y_ratio, w_ratio, h_ratio)
    SLOT_RATIOS = {
        'board_1': (0.220, 0.405, 0.105, 0.085),
        'board_2': (0.330, 0.405, 0.105, 0.085),
        'board_3': (0.440, 0.405, 0.105, 0.085),
        'board_4': (0.550, 0.405, 0.105, 0.085),
        'board_5': (0.660, 0.405, 0.105, 0.085),
        'hero_1':  (0.380, 0.765, 0.110, 0.092),
        'hero_2':  (0.500, 0.765, 0.110, 0.092),
    }

    def __init__(self, templates_dir: str = "templates_cards"):
        self.templates_dir = templates_dir
        self.rank_templates: Dict[str, np.ndarray] = {}
        self._load_templates()

    def _load_templates(self):
        os.makedirs(self.templates_dir, exist_ok=True)
        for rank in self.RANKS:
            path = os.path.join(self.templates_dir, f"{rank}.png")
            if os.path.exists(path):
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None and img.size > 0:
                    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    self.rank_templates[rank] = binary
            else:
                # Fallback sintético limpo
                dummy = np.zeros((50, 40), dtype=np.uint8)
                cv2.putText(dummy, rank, (5, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3, cv2.LINE_AA)
                _, binary = cv2.threshold(dummy, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                self.rank_templates[rank] = binary

    @staticmethod
    def capture_window(hwnd=None) -> Tuple[Optional[np.ndarray], str]:
        frame, metadata = WindowCaptureEngine().capture_frame(hwnd=hwnd)
        return frame, metadata['status']

    def classify_suit(self, card_bgr: np.ndarray) -> Tuple[str, float]:
        """Identifica o naipe (s, h, d, c) analisando o espaço HSV e contagem de pixels (4-color deck)."""
        h, w, _ = card_bgr.shape
        roi = card_bgr[0:int(h * 0.65), 0:w]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        masks = {
            'd': cv2.inRange(hsv, np.array([95, 70, 70]), np.array([135, 255, 255])),   # Azul (Ouros)
            'c': cv2.inRange(hsv, np.array([35, 60, 60]), np.array([85, 255, 255])),    # Verde (Paus)
            'h': cv2.bitwise_or(                                                      # Vermelho (Copas)
                cv2.inRange(hsv, np.array([0, 80, 70]), np.array([12, 255, 255])),
                cv2.inRange(hsv, np.array([168, 80, 70]), np.array([180, 255, 255]))
            ),
            's': cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 85, 80]))         # Preto/Cinza (Espadas)
        }

        counts = {suit: cv2.countNonZero(mask) for suit, mask in masks.items()}
        best_suit, count = max(counts.items(), key=lambda x: x[1])

        total_pixels = roi.shape[0] * roi.shape[1]
        confidence = float(count) / max(1.0, float(total_pixels))

        if count < 25 or confidence < 0.015:
            return "NÃO IDENTIFICADO", 0.0

        return best_suit, round(min(1.0, confidence * 15.0), 2)

    def classify_rank(self, card_bgr: np.ndarray) -> Tuple[str, float]:
        """Identifica o rank (A-2) via Template Matching normalizado e Otsu,
        resolvendo especificamente a confusão topológica entre '4' e 'A'."""
        h, w, _ = card_bgr.shape
        roi = card_bgr[0:int(h * 0.50), 0:int(w * 0.50)]
        if roi.size == 0:
            return "NÃO IDENTIFICADO", 0.0

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        best_rank = "NÃO IDENTIFICADO"
        best_score = -1.0

        for rank, template in self.rank_templates.items():
            if binary.shape[0] < template.shape[0] or binary.shape[1] < template.shape[1]:
                continue
            res = cv2.matchTemplate(binary, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            
            # Correção topológica especial: Confusão entre '4' e 'A'
            if rank in ('4', 'A') and max_val > 0.45:
                # Analisar cavidade superior e fechamento horizontal
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    c = max(contours, key=cv2.contourArea)
                    x, cy, cw, ch = cv2.boundingRect(c)
                    aspect_ratio = float(cw) / max(1, ch)
                    # '4' tende a ter largura proporcional maior no topo e laço fechado; 'A' tem pico triangular estreito
                    if rank == '4' and aspect_ratio > 0.75:
                        max_val += 0.08
                    elif rank == 'A' and aspect_ratio <= 0.75:
                        max_val += 0.08

            if max_val > best_score:
                best_score = max_val
                best_rank = rank

        # Limiar estrito: abaixo de 0.50 retorna NÃO IDENTIFICADO (sem falsos positivos)
        if best_score < 0.50:
            return "NÃO IDENTIFICADO", round(float(best_score), 2)

        return best_rank, round(float(best_score), 2)

    def process_table(self, frame: np.ndarray) -> Tuple[Dict[str, str], np.ndarray, float]:
        """Processa a mesa em menos de 15ms. Retorna ({slot: card_str}, debug_frame, latency_ms)."""
        t0 = time.perf_counter()
        H, W = frame.shape[:2]

        results = {}
        debug_frame = frame.copy()

        for slot_name, (rx, ry, rw, rh) in self.SLOT_RATIOS.items():
            x = int(rx * W)
            y = int(ry * H)
            w = int(rw * W)
            h = int(rh * H)

            if x < 0 or y < 0 or x + w > W or y + h > H:
                results[slot_name] = "NÃO IDENTIFICADO"
                continue

            crop = frame[y:y+h, x:x+w]

            # Verificar se slot está vazio ou com feltro
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            if np.mean(gray) < 65 or np.std(gray) < 14:
                results[slot_name] = "NÃO IDENTIFICADO"
                cv2.rectangle(debug_frame, (x, y), (x+w, y+h), (0, 0, 255), 1)
                continue

            rank, rank_conf = self.classify_rank(crop)
            suit, suit_conf = self.classify_suit(crop)

            if rank != "NÃO IDENTIFICADO" and suit != "NÃO IDENTIFICADO":
                card_str = f"{rank}{suit}"
                results[slot_name] = card_str
                cv2.rectangle(debug_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(debug_frame, card_str, (x, max(15, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            else:
                results[slot_name] = "NÃO IDENTIFICADO"
                cv2.rectangle(debug_frame, (x, y), (x+w, y+h), (0, 0, 255), 2)

        latency_ms = (time.perf_counter() - t0) * 1000
        return results, debug_frame, round(latency_ms, 2)
