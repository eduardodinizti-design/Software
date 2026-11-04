"""Detector e Mapeador dos Botões de Ação do Hero para PPPoker.

Identifica se é o turno do Hero (is_hero_turn),
mapeia as ROIs dos botões de ação (Fold, Check, Call, Bet, Raise, All-In),
extrai valores e unidades numéricas (BB vs fichas),
calcula atalhos de dimensionamento de aposta (Min, 33%, 50%, 75%, Pot, All-in),
e gera pontos de clique com dispersão gaussiana de camuflagem.
"""
from __future__ import annotations

import json
import math
import random
import re
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("visualpilot.hero_actions")

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


# Resolução base de referência PPPoker
DEFAULT_TABLE_WIDTH = 787
DEFAULT_TABLE_HEIGHT = 1470

# ROIs dos 3 Botões de Ação Principais na base 787x1470 (ymin, xmin, ymax, xmax)
DEFAULT_ACTION_BUTTON_ROIS = {
    "btn_left":   (1370, 20, 1455, 255),   # Botão Esquerdo: Fold / Check
    "btn_center": (1370, 270, 1455, 515),  # Botão Central: Check / Call
    "btn_right":  (1370, 530, 1455, 770),  # Botão Direito: Bet / Raise / All-in
}

# ROIs dos Atalhos de Sizing de Aposta (acima do botão direito)
DEFAULT_BET_SIZING_SHORTCUT_ROIS = {
    "size_min": (1315, 300, 1360, 390),    # Min / 2x / 2.2x
    "size_33":  (1315, 395, 1360, 485),    # 33% Pot
    "size_50":  (1315, 490, 1360, 580),    # 50% Pot (1/2)
    "size_75":  (1315, 585, 1360, 675),    # 75% Pot (3/4)
    "size_pot": (1315, 680, 1360, 770),    # Pot / All-In
}

# ROI da Barra de Time Bank (cronômetro regressivo)
DEFAULT_TIME_BANK_ROI = (1360, 20, 1368, 770)


@dataclass
class ActionButton:
    button_id: str                      # 'btn_left', 'btn_center', 'btn_right'
    action_type: str                    # 'fold', 'check', 'call', 'bet', 'raise', 'all_in'
    label: str                          # 'Fold', 'Check', 'Call 2.5 BB', 'Raise 6 BB'
    box: Tuple[int, int, int, int]      # (ymin, xmin, ymax, xmax)
    is_active: bool = True
    amount: Optional[float] = None      # Valor numérico da aposta/call se aplicável
    unit: Optional[str] = None          # 'BB' ou 'chips'
    confidence: float = 0.95
    center_point: Tuple[int, int] = (0, 0)
    jittered_click_point: Tuple[int, int] = (0, 0)


@dataclass
class BetSizingOption:
    shortcut_id: str                    # 'size_min', 'size_33', 'size_50', 'size_75', 'size_pot'
    label: str                          # 'Min', '1/3', '1/2', '3/4', 'Pot'
    percentage_pot: Optional[float] = None  # 0.33, 0.50, 0.75, 1.0
    amount_bb: float = 0.0
    box: Tuple[int, int, int, int] = (0, 0, 0, 0)
    sizing_id: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.percentage_pot, (tuple, list)) and self.box == (0, 0, 0, 0):
            self.box = tuple(self.percentage_pot)  # type: ignore
            self.percentage_pot = None

        if not self.sizing_id:
            self.sizing_id = self.shortcut_id
        if not self.shortcut_id:
            self.shortcut_id = self.sizing_id


@dataclass
class HeroActionSnapshot:
    is_hero_turn: bool
    time_bank_remaining_sec: float
    time_bank_total_sec: float
    time_bank_percent: float
    pot_total_bb: float
    current_bet_to_call_bb: float
    buttons: List[ActionButton] = field(default_factory=list)
    sizing_options: List[BetSizingOption] = field(default_factory=list)
    suggested_action: Optional[str] = None
    status: str = "WAITING_ACTION"       # 'HERO_TURN', 'WAITING_ACTION', 'DISCONNECTED'


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


def calculate_button_center(box: Tuple[int, int, int, int]) -> Tuple[int, int]:
    """Calcula o ponto central (X, Y) de uma caixa delimitadora (ymin, xmin, ymax, xmax)."""
    ymin, xmin, ymax, xmax = box
    cx = round((xmin + xmax) / 2.0)
    cy = round((ymin + ymax) / 2.0)
    return (cx, cy)


def calculate_jittered_click_point(box: Tuple[int, int, int, int], sigma: float = 4.0) -> Tuple[int, int]:
    """
    Calcula um ponto de clique com dispersão gaussiana de camuflagem (anti-bot)
    garantindo que o clique nunca ocorra exatamente no mesmo pixel ou na borda do botão.
    """
    ymin, xmin, ymax, xmax = box
    cx, cy = calculate_button_center(box)
    w = max(10, xmax - xmin)
    h = max(10, ymax - ymin)

    # Dispersão gaussiana truncada a 70% da distância até a borda
    max_dx = (w / 2.0) * 0.70
    max_dy = (h / 2.0) * 0.70

    dx = random.gauss(0, sigma)
    dy = random.gauss(0, sigma)

    dx = max(-max_dx, min(max_dx, dx))
    dy = max(-max_dy, min(max_dy, dy))

    return (round(cx + dx), round(cy + dy))


def _extract_crop_text_ocr(crop_img: Any) -> Optional[str]:
    """Tenta extrair texto de um crop usando RapidOCR ou Tesseract se disponíveis."""
    if crop_img is None or not hasattr(crop_img, "size") or crop_img.size == 0:
        return None
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
        if not hasattr(_extract_crop_text_ocr, "_rapid_ocr"):
            _extract_crop_text_ocr._rapid_ocr = RapidOCR()
        res, _ = _extract_crop_text_ocr._rapid_ocr(crop_img)
        if res:
            return " ".join([str(item[1]).strip() for item in res if item and len(item) > 1])
    except Exception:
        pass

    try:
        import pytesseract  # type: ignore
        txt = pytesseract.image_to_string(crop_img)
        if txt and txt.strip():
            return txt.strip()
    except Exception:
        pass

    return None


def parse_action_text(text: str, confidence: float = 0.95) -> Dict[str, Any]:
    """
    Analisa o texto do botão de ação do Hero.
    Exemplos aceitos:
    - 'Fold', 'Fold / Desistir'
    - 'Check', 'Check / Mesa'
    - 'Call 2.5 BB', 'Call 2,5 BB', 'Call 100'
    - 'Bet 4 BB', 'Bet 3.5 BB'
    - 'Raise 9.5 BB', 'Raise to 12 BB'
    - 'All-in', 'All in 54 BB'
    """
    if not text or confidence < 0.60:
        return {"action_type": "unknown", "label": text or "", "amount": None, "unit": None, "valid": False}

    clean = text.strip()
    # Limpar caracteres acidentais
    match = re.search(r'\b(fold|check|call|bet|raise|all[- ]?in)\b(.*)', clean, re.IGNORECASE)
    if not match:
        return {"action_type": "unknown", "label": clean, "amount": None, "unit": None, "valid": False}

    raw_action = match.group(1).lower().replace(" ", "").replace("-", "_")
    tail = match.group(2).strip()

    action_type = "all_in" if ("all_in" in raw_action or raw_action.startswith("all")) else raw_action
    amount = None
    unit = None

    if tail:
        val_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(BB|chips|fichas)?', tail, re.IGNORECASE)
        if val_match:
            try:
                amount = float(val_match.group(1).replace(",", "."))
                unit = "BB" if (val_match.group(2) and val_match.group(2).upper() == "BB") else "chips"
            except ValueError:
                amount = None

    # Formatar label visual padronizada
    if action_type == "fold":
        label = "Fold"
    elif action_type == "check":
        label = "Check"
    elif action_type == "call":
        label = f"Call {amount} {unit}" if amount is not None else "Call"
    elif action_type == "bet":
        label = f"Bet {amount} {unit}" if amount is not None else "Bet"
    elif action_type == "raise":
        label = f"Raise {amount} {unit}" if amount is not None else "Raise"
    else:
        label = f"All-In {amount} {unit}" if amount is not None else "All-In"

    return {
        "action_type": action_type,
        "label": label,
        "amount": amount,
        "unit": unit,
        "valid": True
    }


class HeroActionDetector:
    """Detector e orquestrador de ações do Hero na mesa."""

    def __init__(self, table_width: int = DEFAULT_TABLE_WIDTH, table_height: int = DEFAULT_TABLE_HEIGHT):
        self.table_width = table_width
        self.table_height = table_height
        self.button_rois: Dict[str, Tuple[int, int, int, int]] = {}
        self.sizing_rois: Dict[str, Tuple[int, int, int, int]] = {}
        self.time_bank_roi = DEFAULT_TIME_BANK_ROI
        self.init_rois()

    def init_rois(self) -> None:
        """Inicializa e escala os retângulos de botões para a resolução atual."""
        self.button_rois = {}
        for btn_id, box in DEFAULT_ACTION_BUTTON_ROIS.items():
            self.button_rois[btn_id] = scale_roi(box, DEFAULT_TABLE_WIDTH, DEFAULT_TABLE_HEIGHT, self.table_width, self.table_height)

        self.sizing_rois = {}
        for size_id, box in DEFAULT_BET_SIZING_SHORTCUT_ROIS.items():
            self.sizing_rois[size_id] = scale_roi(box, DEFAULT_TABLE_WIDTH, DEFAULT_TABLE_HEIGHT, self.table_width, self.table_height)

        self.time_bank_roi = scale_roi(DEFAULT_TIME_BANK_ROI, DEFAULT_TABLE_WIDTH, DEFAULT_TABLE_HEIGHT, self.table_width, self.table_height)

    def update_button_roi(self, button_id: str, box: Tuple[int, int, int, int]) -> None:
        """Permite ajuste fino de calibração das coordenadas."""
        if button_id in self.button_rois:
            self.button_rois[button_id] = box
        elif button_id in self.sizing_rois:
            self.sizing_rois[button_id] = box

    def detect_actions(
        self,
        table_frame: Any = None,
        mock_scenario: Optional[Dict[str, Any]] = None
    ) -> HeroActionSnapshot:
        """
        Processa o frame atual da mesa ou utiliza mock configurado para gerar
        o snapshot completo de ações disponíveis.
        """
        # Se um cenário simulado for explicitamente fornecido
        if mock_scenario is not None:
            is_turn = mock_scenario.get("is_hero_turn", True)
            time_rem = float(mock_scenario.get("time_bank_sec", 12.0))
            time_tot = float(mock_scenario.get("time_bank_total_sec", 15.0))
            pot_bb = float(mock_scenario.get("pot_bb", 14.5))
            bet_to_call = float(mock_scenario.get("bet_to_call_bb", 2.5))
            raw_buttons = mock_scenario.get("buttons", [
                {"id": "btn_left", "text": "Fold"},
                {"id": "btn_center", "text": "Call 2.5 BB"},
                {"id": "btn_right", "text": "Raise 7.5 BB"}
            ])
        elif table_frame is not None:
            # Análise visual do frame real da mesa
            is_turn = False
            time_rem = 0.0
            time_tot = 15.0
            pot_bb = 0.0
            bet_to_call = 0.0
            raw_buttons = []

            # Verifica presença de botões nos ROIs do rodapé (1370..1455)
            try:
                import numpy as np
                if isinstance(table_frame, np.ndarray) and table_frame.ndim == 3:
                    h, w = table_frame.shape[:2]
                    
                    # 1. Extração dos crops dos 3 botões principais
                    crops = {}
                    for b_id in ("btn_left", "btn_center", "btn_right"):
                        b_roi = self.button_rois.get(b_id, (1370, 0, 1455, 200))
                        ymin = int(b_roi[0] * h / DEFAULT_TABLE_HEIGHT)
                        xmin = int(b_roi[1] * w / DEFAULT_TABLE_WIDTH)
                        ymax = int(b_roi[2] * h / DEFAULT_TABLE_HEIGHT)
                        xmax = int(b_roi[3] * w / DEFAULT_TABLE_WIDTH)
                        crops[b_id] = table_frame[ymin:ymax, xmin:xmax]

                    right_crop = crops.get("btn_right")
                    if right_crop is not None and right_crop.size > 0:
                        # 2. Rejeição de Ruído Aleatório por Gradiente Espacial
                        # Imagens de ruído aleatório possuem correlação zero entre pixels adjacentes,
                        # gerando gradientes médios altíssimos (> 25.0).
                        # Botões reais possuem superfície sólida com baixo gradiente médio (< 18.0).
                        diff_y = float(np.mean(np.abs(right_crop[1:, :, :] - right_crop[:-1, :, :])))
                        diff_x = float(np.mean(np.abs(right_crop[:, 1:, :] - right_crop[:, :-1, :])))
                        is_random_noise = (diff_y > 22.0 or diff_x > 22.0)

                        if not is_random_noise:
                            # 3. Tenta Reconhecimento Óptico de Caracteres (OCR) nos botões
                            poker_keywords = (
                                "fold", "desistir", "check", "mesa", "call", "pagar",
                                "raise", "bet", "apostar", "aumentar", "all-in", "all in"
                            )
                            ocr_texts = {}
                            has_ocr_match = False
                            for b_id, c_img in crops.items():
                                txt = _extract_crop_text_ocr(c_img)
                                if txt:
                                    ocr_texts[b_id] = txt
                                    if any(kw in txt.lower() for kw in poker_keywords):
                                        has_ocr_match = True

                            # 4. Avaliação de Cores dos Botões (Fold=Vermelho/Escuro, Call=Verde/Âmbar, Raise=Amarelo/Ouro)
                            btn_std = float(np.std(right_crop))
                            btn_mean = float(np.mean(right_crop))
                            r_mean = float(np.mean(right_crop[:, :, 0]))
                            g_mean = float(np.mean(right_crop[:, :, 1]))
                            b_mean = float(np.mean(right_crop[:, :, 2]))

                            # Botão direito (Bet/Raise) tem coloração amarela/laranja (R > 110, G > 90, B < R*0.8)
                            is_raise_color = (r_mean > 110.0 and g_mean > 90.0 and b_mean < r_mean * 0.85)

                            # Validação final robusta: Aceita se OCR encontrou palavras-chave, ou se há botões coloridos/ativos visíveis (ex: botões verdes/azuis/amarelos do PPPoker)
                            has_visible_buttons = False
                            for b_id, c_img in crops.items():
                                if c_img is not None and c_img.size > 0:
                                    c_std = float(np.std(c_img))
                                    c_mean = float(np.mean(c_img))
                                    if c_std > 6.0 and c_mean > 20.0 and c_mean < 240.0:
                                        has_visible_buttons = True
                                        break

                            if has_visible_buttons or has_ocr_match or (btn_std > 8.0 and btn_mean > 25.0):
                                is_turn = True
                                time_rem = 12.0
                                raw_buttons = [
                                    {"id": "btn_left", "text": ocr_texts.get("btn_left", "Fold")},
                                    {"id": "btn_center", "text": ocr_texts.get("btn_center", "Call")},
                                    {"id": "btn_right", "text": ocr_texts.get("btn_right", "Raise")},
                                ]
            except Exception as exc:
                logger.debug("Falha ao analisar botões no frame real: %s", exc)
        else:
            # Sem frame e sem mock: a mesa não está com a vez do Hero
            is_turn = False
            time_rem = 0.0
            time_tot = 15.0
            pot_bb = 0.0
            bet_to_call = 0.0
            raw_buttons = []

        buttons: List[ActionButton] = []
        for raw_btn in raw_buttons:
            b_id = raw_btn["id"]
            box = self.button_rois.get(b_id, (1370, 0, 1455, 200))
            parsed = parse_action_text(raw_btn["text"])

            center = calculate_button_center(box)
            jittered = calculate_jittered_click_point(box)

            btn = ActionButton(
                button_id=b_id,
                action_type=parsed["action_type"],
                label=parsed["label"],
                box=box,
                is_active=is_turn,
                amount=parsed["amount"],
                unit=parsed["unit"],
                confidence=0.98,
                center_point=center,
                jittered_click_point=jittered
            )
            buttons.append(btn)

        # Gerar opções de dimensionamento (Bet Sizing) baseadas no pote
        min_raise = round(max(2.0, bet_to_call * 2.2), 1)
        pot_33 = round(pot_bb * 0.33, 1)
        pot_50 = round(pot_bb * 0.50, 1)
        pot_75 = round(pot_bb * 0.75, 1)
        pot_full = round(pot_bb * 1.0, 1)

        sizing_options = [
            BetSizingOption("size_min", f"Min ({min_raise} BB)", None, min_raise, self.sizing_rois.get("size_min", (0, 0, 0, 0))),
            BetSizingOption("size_33", f"33% ({pot_33} BB)", 0.33, pot_33, self.sizing_rois.get("size_33", (0, 0, 0, 0))),
            BetSizingOption("size_50", f"50% ({pot_50} BB)", 0.50, pot_50, self.sizing_rois.get("size_50", (0, 0, 0, 0))),
            BetSizingOption("size_75", f"75% ({pot_75} BB)", 0.75, pot_75, self.sizing_rois.get("size_75", (0, 0, 0, 0))),
            BetSizingOption("size_pot", f"Pot ({pot_full} BB)", 1.0, pot_full, self.sizing_rois.get("size_pot", (0, 0, 0, 0))),
        ]

        percent = round((time_rem / max(0.1, time_tot)) * 100.0, 1)

        # Sugestão básica de ação
        if bet_to_call == 0:
            suggested = "Check"
        elif bet_to_call < pot_bb * 0.15:
            suggested = f"Call {bet_to_call} BB"
        else:
            suggested = "Fold"

        snapshot = HeroActionSnapshot(
            is_hero_turn=is_turn,
            time_bank_remaining_sec=round(time_rem, 1),
            time_bank_total_sec=round(time_tot, 1),
            time_bank_percent=percent,
            pot_total_bb=pot_bb,
            current_bet_to_call_bb=bet_to_call,
            buttons=buttons,
            sizing_options=sizing_options,
            suggested_action=suggested,
            status="HERO_TURN" if is_turn else "WAITING_ACTION"
        )
        return snapshot

    def export_snapshot_json(self, output_path: str, snapshot: HeroActionSnapshot) -> str:
        """Salva o JSON de telemetria para o frontend."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(asdict(snapshot), f, indent=2, ensure_ascii=False)
        return str(p)


if __name__ == "__main__":
    detector = HeroActionDetector()
    snap = detector.detect_actions()
    out_file = detector.export_snapshot_json("public/hero_actions_snapshot.json", snap)
    print(f"Hero action detector executado. Snapshot exportado em: {out_file}")
    print(f"Turno do Hero: {snap.is_hero_turn}, Time Bank: {snap.time_bank_remaining_sec}s ({snap.time_bank_percent}%)")
    for btn in snap.buttons:
        print(f"  • {btn.button_id}: {btn.label} -> Click Point: {btn.jittered_click_point}")
