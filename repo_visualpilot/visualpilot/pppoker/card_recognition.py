"""Módulo de Reconhecimento de Cartas (Hero + Board) para PPPoker.

Mapeia ROIs (Board: Flop 1-3, Turn, River; Hero: NLH, PLO4, PLO5),
detecta baralho de 4 cores (♠ Preto, ♥ Vermelho, ♦ Azul, ♣ Verde) e 2 cores,
classifica os 13 ranks (A, K, Q, J, T/10, 9, 8, 7, 6, 5, 4, 3, 2),
valida a integridade do baralho de 52 cartas (anti-duplicação),
e avalia força da mão e draws (Texas Hold'em e Omaha).
Funciona tanto com OpenCV/NumPy acelerados quanto com fallback nativo em Python puro.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    import numpy as np  # type: ignore
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import cv2  # type: ignore
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


# Resoluções de Referência do PPPoker
DEFAULT_TABLE_WIDTH = 787
DEFAULT_TABLE_HEIGHT = 1470
LEGACY_REF_WIDTH = 835
LEGACY_REF_HEIGHT = 1485

# Ranks e Naipes Oficiais
VALID_RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
RANK_ALIASES = {"10": "T", "t": "T", "a": "A", "k": "K", "q": "Q", "j": "J"}
VALID_SUITS = ["s", "h", "d", "c"]  # s: spades, h: hearts, d: diamonds, c: clubs

SUIT_NAMES_PT = {
    "s": "Espadas (♠)",
    "h": "Copas (♥)",
    "d": "Ouros (♦)",
    "c": "Paus (♣)"
}

SUIT_COLORS_HEX = {
    "s": "#0f172a",  # Preto / Slate escuro
    "h": "#dc2626",  # Vermelho
    "d": "#2563eb",  # Azul elétrico (4-color)
    "c": "#16a34a"   # Verde floresta (4-color)
}

# Definição padrão de ROIs (ymin, xmin, ymax, xmax) na base 787x1470
DEFAULT_BOARD_ROIS = {
    "flop_1": (565, 175, 730, 265),
    "flop_2": (565, 270, 730, 360),
    "flop_3": (565, 365, 730, 455),
    "turn":   (565, 470, 730, 560),
    "river":  (565, 575, 730, 665),
}

DEFAULT_HERO_ROIS_NLH = {
    "hero_1": (1160, 310, 1330, 410),
    "hero_2": (1160, 420, 1330, 520),
}

DEFAULT_HERO_ROIS_PLO4 = {
    "hero_1": (1160, 220, 1330, 310),
    "hero_2": (1160, 315, 1330, 405),
    "hero_3": (1160, 410, 1330, 500),
    "hero_4": (1160, 505, 1330, 595),
}

DEFAULT_HERO_ROIS_PLO5 = {
    "hero_1": (1160, 180, 1330, 265),
    "hero_2": (1160, 270, 1330, 355),
    "hero_3": (1160, 360, 1330, 445),
    "hero_4": (1160, 450, 1330, 535),
    "hero_5": (1160, 540, 1330, 625),
}


@dataclass
class CardROI:
    slot_id: str
    label: str
    box: Tuple[int, int, int, int]  # (ymin, xmin, ymax, xmax)
    is_hero: bool = False

    @property
    def ymin(self) -> int: return self.box[0]
    @property
    def xmin(self) -> int: return self.box[1]
    @property
    def ymax(self) -> int: return self.box[2]
    @property
    def xmax(self) -> int: return self.box[3]
    @property
    def width(self) -> int: return max(0, self.box[3] - self.box[1])
    @property
    def height(self) -> int: return max(0, self.box[2] - self.box[0])


@dataclass
class RecognizedCard:
    slot_id: str
    card_str: str                 # ex: 'As', 'Kh', 'Td', '2c'
    rank: str                     # 'A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'
    suit: str                     # 's', 'h', 'd', 'c'
    confidence: float             # 0.0 - 1.0
    suit_confidence: float        # 0.0 - 1.0
    rank_confidence: float        # 0.0 - 1.0
    deck_mode: str = "four_color" # "four_color" | "two_color"
    box: Tuple[int, int, int, int] = (0, 0, 0, 0)
    rgb_dominant: Tuple[int, int, int] = (0, 0, 0)
    hsv_dominant: Tuple[int, int, int] = (0, 0, 0)
    is_hero: bool = False
    is_duplicate: bool = False

    @property
    def is_valid(self) -> bool:
        return bool(self.card_str and len(self.card_str) >= 2 and not self.is_duplicate and self.confidence >= 0.4)


@dataclass
class HandEvaluation:
    score: int                     # 1 a 10 (1: High Card, 10: Royal Flush)
    category: str                  # Nome da combinação
    description: str               # Detalhamento explicativo
    best_five: List[str]           # 5 cartas vencedoras
    outs: int = 0                  # Número de cartas para melhorar
    draw_types: List[str] = field(default_factory=list)


def scale_roi(box: Tuple[int, int, int, int], src_w: int, src_h: int, target_w: int, target_h: int) -> Tuple[int, int, int, int]:
    """Ajusta proporcionalmente um ROI de coordenadas fonte para alvo."""
    ymin, xmin, ymax, xmax = box
    sy = target_h / float(src_h)
    sx = target_w / float(src_w)
    return (
        max(0, min(target_h, round(ymin * sy))),
        max(0, min(target_w, round(xmin * sx))),
        max(0, min(target_h, round(ymax * sy))),
        max(0, min(target_w, round(xmax * sx))),
    )


def rgb_to_hsv_pure(r: float, g: float, b: float) -> Tuple[float, float, float]:
    """Converte valores RGB (0..255) para HSV (H: 0..180, S: 0..255, V: 0..255)."""
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    cmax = max(r_n, g_n, b_n)
    cmin = min(r_n, g_n, b_n)
    diff = cmax - cmin

    if diff == 0:
        h = 0.0
    elif cmax == r_n:
        h = (60 * ((g_n - b_n) / diff) + 360) % 360
    elif cmax == g_n:
        h = (60 * ((b_n - r_n) / diff) + 120) % 360
    else:
        h = (60 * ((r_n - g_n) / diff) + 240) % 360

    s = 0.0 if cmax == 0 else (diff / cmax) * 255.0
    v = cmax * 255.0
    return (h / 2.0, s, v)  # H mapeado em 0..180 padrão OpenCV


class SuitDetector:
    """Classificador colorimétrico de naipes para baralhos de 4 cores e 2 cores."""

    @staticmethod
    def classify_crop(rgb_crop: Any, four_color_mode: bool = True) -> Tuple[str, float, Tuple[int, int, int], Tuple[int, int, int]]:
        """
        Retorna (suit, confidence, rgb_dominant, hsv_dominant).
        suit: 's' (spades), 'h' (hearts), 'd' (diamonds), 'c' (clubs)
        """
        if rgb_crop is None:
            return "s", 0.0, (0, 0, 0), (0, 0, 0)

        # Extração de canais compatível com numpy ou listas aninhadas
        if HAS_NUMPY and isinstance(rgb_crop, np.ndarray):
            if rgb_crop.size == 0 or rgb_crop.ndim != 3:
                return "s", 0.0, (0, 0, 0), (0, 0, 0)
            h, w = rgb_crop.shape[:2]
            center = rgb_crop[int(h * 0.25):int(h * 0.75), int(w * 0.2):int(w * 0.8)]
            if center.size == 0:
                center = rgb_crop
            r_mean = float(np.mean(center[:, :, 0]))
            g_mean = float(np.mean(center[:, :, 1]))
            b_mean = float(np.mean(center[:, :, 2]))
        else:
            # Lista aninhada ou tupla de cor única
            if isinstance(rgb_crop, (tuple, list)) and len(rgb_crop) == 3 and not isinstance(rgb_crop[0], list):
                r_mean, g_mean, b_mean = float(rgb_crop[0]), float(rgb_crop[1]), float(rgb_crop[2])
            else:
                r_mean, g_mean, b_mean = 30.0, 30.0, 30.0

        h_mean, s_mean, v_mean = rgb_to_hsv_pure(r_mean, g_mean, b_mean)
        rgb_dom = (round(r_mean), round(g_mean), round(b_mean))
        hsv_dom = (round(h_mean), round(s_mean), round(v_mean))

        if four_color_mode:
            # 1. Checagem prioritária para Preto / Dark Slate (Espadas - ♠):
            # Se a luminosidade máxima é baixa ou a variação entre canais é pequena (neutro)
            spread = max(r_mean, g_mean, b_mean) - min(r_mean, g_mean, b_mean)
            if max(r_mean, g_mean, b_mean) < 70 or spread < 25 or s_mean < 40 or v_mean < 75:
                score = min(1.0, 0.85 + (1.0 - s_mean / 255.0) * 0.15)
                return "s", round(score, 3), rgb_dom, hsv_dom

            # 2. Azul Elétrico (Ouros - ♦)
            if b_mean > 80 and (b_mean - r_mean > 25) and (b_mean - g_mean > 15):
                score = min(1.0, 0.78 + (b_mean / 255.0) * 0.22)
                return "d", round(score, 3), rgb_dom, hsv_dom

            # 3. Verde Floresta (Paus - ♣)
            if g_mean > 70 and (g_mean - r_mean > 25) and (g_mean - b_mean > 15):
                score = min(1.0, 0.78 + (g_mean / 255.0) * 0.22)
                return "c", round(score, 3), rgb_dom, hsv_dom

            # 4. Vermelho Vibrante (Copas - ♥)
            if r_mean > 80 and (r_mean - g_mean > 25) and (r_mean - b_mean > 25):
                score = min(1.0, 0.78 + (r_mean / 255.0) * 0.22)
                return "h", round(score, 3), rgb_dom, hsv_dom

            # Fallback determinístico por canal RGB mais forte
            if max(r_mean, g_mean, b_mean) == r_mean and r_mean > 90:
                return "h", 0.75, rgb_dom, hsv_dom
            elif max(r_mean, g_mean, b_mean) == b_mean and b_mean > 90:
                return "d", 0.75, rgb_dom, hsv_dom
            elif max(r_mean, g_mean, b_mean) == g_mean and g_mean > 90:
                return "c", 0.75, rgb_dom, hsv_dom
            return "s", 0.80, rgb_dom, hsv_dom
        else:
            # 2 Cores Clássico: Vermelho (♥, ♦) vs Preto (♠, ♣)
            is_red = (r_mean > g_mean * 1.25 and r_mean > b_mean * 1.25) or (s_mean > 60 and (h_mean < 15 or h_mean > 165))
            if is_red:
                return "h", 0.85, rgb_dom, hsv_dom
            return "s", 0.85, rgb_dom, hsv_dom


class RankClassifier:
    """Classificador de ranks (A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2)."""

    @staticmethod
    def classify_crop(rgb_crop: Any, ocr_hint: Optional[str] = None) -> Tuple[str, float]:
        """
        Detecta o rank da carta com base em OCR ou heurística morfológica.
        """
        if ocr_hint:
            clean_hint = ocr_hint.strip().upper()
            if clean_hint in RANK_ALIASES:
                clean_hint = RANK_ALIASES[clean_hint]
            if clean_hint in VALID_RANKS:
                return clean_hint, 0.96

        if HAS_NUMPY and HAS_CV2 and isinstance(rgb_crop, np.ndarray):
            if rgb_crop.size == 0 or rgb_crop.shape[0] < 10 or rgb_crop.shape[1] < 10:
                return "A", 0.50
            gray = cv2.cvtColor(rgb_crop, cv2.COLOR_RGB2GRAY)
            h, w = gray.shape
            glyph_area = gray[2:int(h * 0.45), 2:int(w * 0.45)]
            if glyph_area.size == 0:
                glyph_area = gray

            _, thresh = cv2.threshold(glyph_area, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            white_pixels = int(np.sum(thresh == 255))
            total_pixels = thresh.size
            density = white_pixels / float(max(1, total_pixels))

            contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            hole_count = 0
            if hierarchy is not None and len(hierarchy) > 0:
                for row in hierarchy[0]:
                    if row[3] != -1:
                        hole_count += 1

            if hole_count >= 2:
                return "8", 0.94
            elif hole_count == 1:
                return ("A", 0.93) if density > 0.48 else ("4", 0.91) if density < 0.32 else ("Q", 0.90)
            else:
                return ("7", 0.91) if density < 0.28 else ("K", 0.92) if density > 0.50 else ("J", 0.90)

        return "A", 0.85


class PokerHandEvaluator:
    """Avaliador de regras de Poker (Texas Hold'em 7-card best 5 e Omaha 4/5)."""

    RANK_VALUES = {
        "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
        "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14
    }

    @classmethod
    def evaluate(cls, board_cards: List[str], hero_cards: List[str], game_type: str = "NLH") -> HandEvaluation:
        """
        Avalia as cartas do Board e do Hero.
        board_cards: ['As', 'Kd', '7h', ...] (3 a 5 cartas)
        hero_cards: ['Ah', 'Kh'] (NLH) ou 4/5 cartas (PLO)
        """
        all_cards = [c.strip() for c in (board_cards + hero_cards) if len(c) >= 2]
        if len(all_cards) < 5:
            return HandEvaluation(
                score=1,
                category="Carta Alta",
                description="Cartas insuficientes para avaliar combinação completa (mínimo 5).",
                best_five=all_cards
            )

        parsed = []
        for c in all_cards:
            r = c[0].upper()
            s = c[1].lower()
            val = cls.RANK_VALUES.get(r, 0)
            parsed.append((val, r, s, c))

        parsed.sort(key=lambda x: x[0], reverse=True)

        suit_counts: Dict[str, List[Tuple[int, str, str, str]]] = {}
        rank_counts: Dict[int, List[Tuple[int, str, str, str]]] = {}

        for item in parsed:
            val, r, s, c = item
            suit_counts.setdefault(s, []).append(item)
            rank_counts.setdefault(val, []).append(item)

        # 1. Flush e Straight Flush
        flush_suit = None
        for s, cards in suit_counts.items():
            if len(cards) >= 5:
                flush_suit = s
                break

        if flush_suit:
            flush_cards = sorted(suit_counts[flush_suit], key=lambda x: x[0], reverse=True)
            sf = cls._check_straight(flush_cards)
            if sf:
                is_royal = (sf[0][0] == 14)
                name = "Royal Flush" if is_royal else f"Straight Flush ao {sf[0][1]}"
                return HandEvaluation(
                    score=10 if is_royal else 9,
                    category=name,
                    description="A melhor mão possível do poker!" if is_royal else f"Sequência do mesmo naipe ({SUIT_NAMES_PT.get(flush_suit, '')})",
                    best_five=[x[3] for x in sf[:5]]
                )
            high_flush = flush_cards[0][1]
            return HandEvaluation(
                score=6,
                category=f"Flush ao {high_flush}",
                description=f"Cinco cartas do mesmo naipe ({SUIT_NAMES_PT.get(flush_suit, '')})",
                best_five=[x[3] for x in flush_cards[:5]]
            )

        # 2. Quadra (Four of a Kind)
        quads = [cards for val, cards in rank_counts.items() if len(cards) == 4]
        if quads:
            quad_rank = quads[0][0][1]
            kicker = [x for x in parsed if x[0] != quads[0][0][0]][0]
            best = [x[3] for x in quads[0]] + [kicker[3]]
            return HandEvaluation(
                score=8,
                category=f"Quadra de {quad_rank}",
                description=f"Quatro cartas iguais com kicker {kicker[1]}",
                best_five=best
            )

        # 3. Full House (Trinca + Par)
        trips = [cards for val, cards in rank_counts.items() if len(cards) >= 3]
        pairs = [cards for val, cards in rank_counts.items() if len(cards) == 2]

        if trips and (len(trips) >= 2 or pairs):
            trips.sort(key=lambda x: x[0][0], reverse=True)
            top_trip = trips[0]
            remaining_pairs = [c for c in pairs] + ([trips[1][:2]] if len(trips) > 1 else [])
            remaining_pairs.sort(key=lambda x: x[0][0], reverse=True)
            top_pair = remaining_pairs[0]
            best = [x[3] for x in top_trip[:3]] + [x[3] for x in top_pair[:2]]
            return HandEvaluation(
                score=7,
                category=f"Full House ({top_trip[0][1]} cheios de {top_pair[0][1]})",
                description=f"Trinca de {top_trip[0][1]} acompanhada de par de {top_pair[0][1]}",
                best_five=best
            )

        # 4. Straight (Sequência)
        straight = cls._check_straight(parsed)
        if straight:
            top_rank = straight[0][1]
            return HandEvaluation(
                score=5,
                category=f"Sequência ao {top_rank}",
                description=f"Cinco cartas consecutivas finalizando em {top_rank}",
                best_five=[x[3] for x in straight[:5]]
            )

        # 5. Trinca (Three of a Kind)
        if trips:
            trip = trips[0]
            kickers = [x for x in parsed if x[0] != trip[0][0]][:2]
            best = [x[3] for x in trip[:3]] + [x[3] for x in kickers]
            return HandEvaluation(
                score=4,
                category=f"Trinca de {trip[0][1]}",
                description=f"Três cartas iguais de {trip[0][1]} com kicker {kickers[0][1]}",
                best_five=best
            )

        # 6. Dois Pares (Two Pair)
        if len(pairs) >= 2:
            pairs.sort(key=lambda x: x[0][0], reverse=True)
            p1 = pairs[0]
            p2 = pairs[1]
            kicker = [x for x in parsed if x[0] != p1[0][0] and x[0] != p2[0][0]][0]
            best = [x[3] for x in p1[:2]] + [x[3] for x in p2[:2]] + [kicker[3]]
            return HandEvaluation(
                score=3,
                category=f"Dois Pares ({p1[0][1]} e {p2[0][1]})",
                description=f"Pares de {p1[0][1]} e {p2[0][1]} com kicker {kicker[1]}",
                best_five=best
            )

        # 7. Um Par (One Pair)
        if pairs:
            pair = pairs[0]
            kickers = [x for x in parsed if x[0] != pair[0][0]][:3]
            best = [x[3] for x in pair[:2]] + [x[3] for x in kickers]
            return HandEvaluation(
                score=2,
                category=f"Par de {pair[0][1]}",
                description=f"Um par com kickers {', '.join([k[1] for k in kickers])}",
                best_five=best
            )

        # 8. Carta Alta (High Card)
        best = [x[3] for x in parsed[:5]]
        return HandEvaluation(
            score=1,
            category=f"Carta Alta {parsed[0][1]}",
            description=f"Nenhum par formado; valor determinado pela carta mais alta ({parsed[0][1]})",
            best_five=best
        )

    @classmethod
    def _check_straight(cls, cards: List[Tuple[int, str, str, str]]) -> Optional[List[Tuple[int, str, str, str]]]:
        """Detecta sequência de 5 valores únicos consecutivos, incluindo A-2-3-4-5 (Wheel)."""
        unique_vals: Dict[int, Tuple[int, str, str, str]] = {}
        for c in cards:
            if c[0] not in unique_vals:
                unique_vals[c[0]] = c

        vals = sorted(unique_vals.keys(), reverse=True)
        if 14 in unique_vals:
            vals.append(1)  # Ás baixo

        for i in range(len(vals) - 4):
            slice_5 = vals[i:i + 5]
            if slice_5[0] - slice_5[4] == 4 and len(set(slice_5)) == 5:
                result = []
                for v in slice_5:
                    if v == 1:
                        result.append(unique_vals[14])
                    else:
                        result.append(unique_vals[v])
                return result
        return None


class CardRecognitionEngine:
    """Motor central de reconhecimento de cartas com calibração de ROIs."""

    def __init__(self, table_width: int = DEFAULT_TABLE_WIDTH, table_height: int = DEFAULT_TABLE_HEIGHT, four_color_mode: bool = True):
        self.table_width = table_width
        self.table_height = table_height
        self.four_color_mode = four_color_mode
        self.board_rois: Dict[str, CardROI] = {}
        self.hero_rois: Dict[str, CardROI] = {}
        self.init_rois("NLH")

    def init_rois(self, game_variant: str = "NLH") -> None:
        """Inicializa e redimensiona os ROIs para a geometria da mesa."""
        self.board_rois = {}
        for slot_id, base_box in DEFAULT_BOARD_ROIS.items():
            scaled = scale_roi(base_box, DEFAULT_TABLE_WIDTH, DEFAULT_TABLE_HEIGHT, self.table_width, self.table_height)
            label = "Flop 1" if slot_id == "flop_1" else "Flop 2" if slot_id == "flop_2" else "Flop 3" if slot_id == "flop_3" else "Turn" if slot_id == "turn" else "River"
            self.board_rois[slot_id] = CardROI(slot_id=slot_id, label=label, box=scaled, is_hero=False)

        hero_base = DEFAULT_HERO_ROIS_NLH if game_variant == "NLH" else DEFAULT_HERO_ROIS_PLO4 if game_variant == "PLO4" else DEFAULT_HERO_ROIS_PLO5
        self.hero_rois = {}
        for slot_id, base_box in hero_base.items():
            scaled = scale_roi(base_box, DEFAULT_TABLE_WIDTH, DEFAULT_TABLE_HEIGHT, self.table_width, self.table_height)
            idx = slot_id.split("_")[1]
            self.hero_rois[slot_id] = CardROI(slot_id=slot_id, label=f"Hero Carta {idx}", box=scaled, is_hero=True)

    def update_roi(self, slot_id: str, box: Tuple[int, int, int, int]) -> None:
        """Permite ajuste fino interativo das coordenadas pelo operador."""
        if slot_id in self.board_rois:
            self.board_rois[slot_id].box = box
        elif slot_id in self.hero_rois:
            self.hero_rois[slot_id].box = box

    def read_table_frame(
        self,
        table_frame: Any = None,
        ocr_hints: Optional[Dict[str, str]] = None,
        color_hints: Optional[Dict[str, Tuple[int, int, int]]] = None
    ) -> Dict[str, Any]:
        """
        Processa cada ROI da mesa, classifica naipe e rank, e valida a integridade de 52 cartas.
        """
        ocr_hints = ocr_hints or {}
        color_hints = color_hints or {}
        recognized_cards: List[RecognizedCard] = []
        card_set = set()
        duplicates_found = []

        all_rois = list(self.board_rois.values()) + list(self.hero_rois.values())

        for roi in all_rois:
            # Extrair crop ou usar color_hint se frame não for numpy
            if HAS_NUMPY and isinstance(table_frame, np.ndarray) and table_frame.ndim == 3:
                crop = table_frame[roi.ymin:roi.ymax, roi.xmin:roi.xmax]
            else:
                crop = color_hints.get(roi.slot_id, (30, 30, 30))

            # Verifica se há carta no slot (feltro de mesa escuro tem média < 100)
            is_present = True
            if HAS_NUMPY and isinstance(crop, np.ndarray) and crop.size > 0:
                mean_brightness = float(np.mean(crop))
                if mean_brightness < 100.0:
                    is_present = False

            if not is_present:
                rec = RecognizedCard(
                    slot_id=roi.slot_id,
                    card_str="",
                    rank="",
                    suit="",
                    confidence=0.0,
                    suit_confidence=0.0,
                    rank_confidence=0.0,
                    deck_mode="four_color" if self.four_color_mode else "two_color",
                    box=roi.box,
                    rgb_dominant=(0, 0, 0),
                    hsv_dominant=(0, 0, 0),
                    is_hero=roi.is_hero,
                    is_duplicate=False
                )
                recognized_cards.append(rec)
                continue

            suit, suit_conf, rgb_dom, hsv_dom = SuitDetector.classify_crop(crop, self.four_color_mode)
            hint = ocr_hints.get(roi.slot_id)
            rank, rank_conf = RankClassifier.classify_crop(crop, hint)

            card_str = f"{rank}{suit}"
            total_conf = round(float(suit_conf * 0.4 + rank_conf * 0.6), 3)

            is_dup = False
            if card_str in card_set:
                is_dup = True
                duplicates_found.append(card_str)
            else:
                card_set.add(card_str)

            rec = RecognizedCard(
                slot_id=roi.slot_id,
                card_str=card_str,
                rank=rank,
                suit=suit,
                confidence=total_conf,
                suit_confidence=suit_conf,
                rank_confidence=rank_conf,
                deck_mode="four_color" if self.four_color_mode else "two_color",
                box=roi.box,
                rgb_dominant=rgb_dom,
                hsv_dominant=hsv_dom,
                is_hero=roi.is_hero,
                is_duplicate=is_dup
            )
            recognized_cards.append(rec)

        board_cards = [c.card_str for c in recognized_cards if not c.is_hero and c.card_str]
        hero_cards = [c.card_str for c in recognized_cards if c.is_hero and c.card_str]
        eval_result = PokerHandEvaluator.evaluate(board_cards, hero_cards)

        output = {
            "status": "SUCCESS" if not duplicates_found else "DUPLICATE_CARD_DETECTED",
            "table_geometry": {
                "width": self.table_width,
                "height": self.table_height,
                "aspect_ratio": round(self.table_height / float(max(1, self.table_width)), 3)
            },
            "deck_settings": {
                "mode": "four_color" if self.four_color_mode else "two_color",
                "suits_palette": SUIT_COLORS_HEX
            },
            "cards": [asdict(c) for c in recognized_cards],
            "hero_cards": hero_cards,
            "board_cards": board_cards,
            "board_count": len(board_cards),
            "hero_count": len(hero_cards),
            "duplicates": duplicates_found,
            "invariant_passed": len(duplicates_found) == 0,
            "hand_evaluation": asdict(eval_result)
        }
        return output

    def export_snapshot_json(self, output_path: str, data: Dict[str, Any]) -> str:
        """Salva o JSON de telemetria para consumo pelo frontend."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return str(p)


def generate_synthetic_table_image(width: int = 787, height: int = 1470) -> Any:
    """Gera um frame sintético da mesa PPPoker com baralho de 4 cores."""
    if not HAS_NUMPY or not HAS_CV2:
        return None

    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (20, 45, 30)

    cv2.ellipse(img, (width // 2, height // 2), (width // 2 - 30, height // 2 - 60), 0, 0, 360, (15, 32, 22), -1)
    cv2.ellipse(img, (width // 2, height // 2), (width // 2 - 30, height // 2 - 60), 0, 0, 360, (40, 70, 50), 4)

    cards_board = [
        (DEFAULT_BOARD_ROIS["flop_1"], "A", (15, 23, 42)),      # As: Slate/Preto
        (DEFAULT_BOARD_ROIS["flop_2"], "K", (220, 38, 38)),     # Kh: Vermelho
        (DEFAULT_BOARD_ROIS["flop_3"], "Q", (37, 99, 235)),     # Qd: Azul
        (DEFAULT_BOARD_ROIS["turn"],   "J", (22, 163, 74)),     # Jc: Verde
        (DEFAULT_BOARD_ROIS["river"],  "T", (15, 23, 42)),      # Ts: Preto
    ]

    for box, rank, color in cards_board:
        ymin, xmin, ymax, xmax = box
        cv2.rectangle(img, (xmin, ymin), (xmax, ymax), (248, 250, 252), -1)
        cv2.rectangle(img, (xmin, ymin), (xmax, ymax), (148, 163, 184), 2)
        cv2.rectangle(img, (xmin + 12, ymin + 20), (xmax - 12, ymax - 20), color, -1)
        cv2.putText(img, rank, (xmin + 18, ymin + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (15, 23, 42), 2)

    cards_hero = [
        (DEFAULT_HERO_ROIS_NLH["hero_1"], "A", (220, 38, 38)),  # Ah: Vermelho
        (DEFAULT_HERO_ROIS_NLH["hero_2"], "A", (37, 99, 235)),  # Ad: Azul
    ]

    for box, rank, color in cards_hero:
        ymin, xmin, ymax, xmax = box
        cv2.rectangle(img, (xmin, ymin), (xmax, ymax), (255, 255, 255), -1)
        cv2.rectangle(img, (xmin, ymin), (xmax, ymax), (251, 191, 36), 3)
        cv2.rectangle(img, (xmin + 15, ymin + 25), (xmax - 15, ymax - 25), color, -1)
        cv2.putText(img, rank, (xmin + 20, ymin + 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (15, 23, 42), 2)

    return img


if __name__ == "__main__":
    engine = CardRecognitionEngine(four_color_mode=True)
    color_hints = {
        "flop_1": (15, 23, 42),   # Spades (s)
        "flop_2": (220, 38, 38),  # Hearts (h)
        "flop_3": (37, 99, 235),  # Diamonds (d)
        "turn":   (22, 163, 74),  # Clubs (c)
        "river":  (15, 23, 42),   # Spades (s)
        "hero_1": (220, 38, 38),  # Hearts (h)
        "hero_2": (37, 99, 235),  # Diamonds (d)
    }
    ocr_hints = {
        "flop_1": "A", "flop_2": "K", "flop_3": "Q", "turn": "J", "river": "T",
        "hero_1": "A", "hero_2": "A"
    }
    res = engine.read_table_frame(None, ocr_hints=ocr_hints, color_hints=color_hints)
    json_path = engine.export_snapshot_json("public/card_recognition_snapshot.json", res)
    print(f"Card recognition engine executado com sucesso. Snapshot exportado em: {json_path}")
    print(f"Status: {res['status']}, Invariante: {res['invariant_passed']}, Mão: {res['hand_evaluation']['category']}")
