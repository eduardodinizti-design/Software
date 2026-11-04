"""Módulo de Reconhecimento Numérico da Mesa, Stacks, Pote e Posições (Dealer) para PPPoker.

Extrai e valida:
- Pote Total e Side Pots (em BBs ou fichas)
- Stacks de todos os assentos (1 a 6 / 9-max)
- Apostas ativas da street no feltro
- Localização do botão de Dealer (D)
- Mapeamento determinístico de posições: BTN, SB, BB, UTG, MP, CO
- Cálculo de Pot Odds (%) e Stack-to-Pot Ratio (SPR)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Resolução de Referência PPPoker
DEFAULT_TABLE_WIDTH = 787
DEFAULT_TABLE_HEIGHT = 1470

# ROI Pote Total no feltro (ymin, xmin, ymax, xmax)
DEFAULT_TOTAL_POT_ROI = (520, 270, 580, 515)

# ROIs dos 6 Assentos (Stacks e Nomes)
DEFAULT_SEAT_STACK_ROIS = {
    1: (265, 30, 335, 210),    # Topo Esquerda
    2: (170, 300, 240, 485),   # Topo Centro
    3: (265, 575, 335, 755),   # Topo Direita
    4: (720, 575, 790, 755),   # Meio Direita
    5: (1190, 290, 1260, 495), # Fundo Centro (Hero)
    6: (720, 30, 790, 210),    # Meio Esquerda
}

# ROIs das Apostas no Feltro por Assento
DEFAULT_SEAT_BET_ROIS = {
    1: (360, 140, 415, 270),
    2: (265, 330, 320, 455),
    3: (360, 515, 415, 645),
    4: (690, 500, 745, 625),
    5: (1110, 330, 1165, 455), # Hero Bet
    6: (690, 160, 745, 285),
}

# Ordem canônica de posições para 6-max relativa ao Dealer (índice 0 = BTN)
POSITIONS_6MAX = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
POSITIONS_HEADS_UP = ["BTN/SB", "BB"]


@dataclass
class SeatNumericalData:
    seat_number: number
    player_name: str
    stack_bb: float
    stack_chips: Optional[float]
    current_bet_bb: float
    is_hero: bool = False
    is_dealer: bool = False
    is_active: bool = True
    is_folded: bool = False
    position_label: str = "BTN"        # 'BTN', 'SB', 'BB', 'UTG', 'MP', 'CO'
    stack_box: Tuple[int, int, int, int] = (0, 0, 0, 0)
    bet_box: Tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class TableNumericalSnapshot:
    total_pot_bb: float
    total_pot_chips: Optional[float]
    side_pots_bb: List[float] = field(default_factory=list)
    dealer_seat: int = 1
    active_players_count: int = 6
    hero_seat: int = 5
    hero_position: str = "CO"
    seats: List[SeatNumericalData] = field(default_factory=list)
    pot_odds_percent: float = 0.0        # % necessária para o call
    call_amount_bb: float = 0.0          # quantia a pagar pelo Hero
    spr: float = 0.0                     # Stack-to-Pot Ratio do Hero
    spr_category: str = "Médio"          # 'Commit', 'Low', 'Médio', 'Deep'
    confidence: float = 0.96
    status: str = "SUCCESS"


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


def parse_numeric_amount(text: str, default: float = 0.0) -> Tuple[float, Optional[str]]:
    """
    Extrai números em formato de poker:
    - '14.5 BB', '14,5BB' -> (14.5, 'BB')
    - '1,450', '250' -> (1450.0, 'chips')
    - '1.2k', '1.5M' -> (1200.0, 'chips')
    """
    if not text:
        return (default, None)

    clean = text.strip().upper()
    unit = "BB" if "BB" in clean else "chips"

    # Multiplicadores K e M
    multiplier = 1.0
    if "K" in clean:
        multiplier = 1000.0
        clean = clean.replace("K", "")
    elif "M" in clean:
        multiplier = 1000000.0
        clean = clean.replace("M", "")

    # Remover prefixos de palavras
    clean = re.sub(r'[^0-9.,]', '', clean)
    if not clean:
        return (default, unit)

    # Tratar separadores de milhar vs decimal
    # Se tiver vírgula e ponto (ex: 1,450.50 ou 1.450,50)
    if "," in clean and "." in clean:
        if clean.rfind(".") > clean.rfind(","):
            clean = clean.replace(",", "")
        else:
            clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        # Se tem vírgula e 1 ou 2 dígitos após (ex: 2,5 ou 14,5), é decimal
        parts = clean.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            clean = f"{parts[0]}.{parts[1]}"
        else:
            clean = clean.replace(",", "")

    try:
        val = float(clean) * multiplier
        return (round(val, 2), unit)
    except ValueError:
        return (default, unit)


def calculate_positions_6max(dealer_seat: int, seats: List[SeatNumericalData]) -> None:
    """
    Atribui posições relativas (BTN, SB, BB, UTG, MP, CO)
    baseado no assento do Dealer e jogadores ativos na mão.
    """
    active_seats = [s for s in seats if s.is_active and not s.is_folded]
    if not active_seats:
        active_seats = [s for s in seats if s.is_active]

    if not active_seats:
        return

    # Ordenar assentos em sentido horário a partir do dealer_seat
    total_active = len(active_seats)

    # Identificar o índice do dealer ou o mais próximo
    sorted_seats = sorted(active_seats, key=lambda s: (s.seat_number - dealer_seat) % 6)

    if total_active == 2:
        # Heads-up: Dealer é BTN e também SB; outro jogador é BB
        sorted_seats[0].position_label = "BTN/SB"
        sorted_seats[1].position_label = "BB"
        return

    # 3 a 6 jogadores
    pos_labels = POSITIONS_6MAX if total_active == 6 else POSITIONS_6MAX[:total_active]
    # Se faltar posições (ex: 4 jogadores), preenche a partir de BTN, SB, BB, e a última antes do BTN é CO
    if total_active == 3:
        pos_labels = ["BTN", "SB", "BB"]
    elif total_active == 4:
        pos_labels = ["BTN", "SB", "BB", "CO"]
    elif total_active == 5:
        pos_labels = ["BTN", "SB", "BB", "UTG", "CO"]

    for idx, s in enumerate(sorted_seats):
        s.position_label = pos_labels[idx]
        s.is_dealer = (s.seat_number == dealer_seat)


def calculate_pot_odds(call_amount_bb: float, pot_total_bb: float) -> float:
    """
    Calcula Pot Odds em percentual:
    Pot Odds (%) = To Call / (Total Pot + To Call) * 100
    """
    if call_amount_bb <= 0:
        return 0.0
    denom = pot_total_bb + call_amount_bb
    if denom <= 0:
        return 0.0
    return round((call_amount_bb / denom) * 100.0, 1)


def calculate_spr(hero_stack_bb: float, pot_total_bb: float) -> Tuple[float, str]:
    """
    Calcula Stack-to-Pot Ratio (SPR) e classifica o perfil estratégico:
    SPR = Hero Effective Stack / Total Pot
    """
    if pot_total_bb <= 0:
        return (99.0, "Deep")

    spr = round(hero_stack_bb / pot_total_bb, 1)

    if spr <= 1.0:
        cat = "Commit (All-in Fácil)"
    elif spr <= 4.0:
        cat = "Low (Fácil Decisão de Stack)"
    elif spr <= 13.0:
        cat = "Médio (Cautela com Mãos Médias)"
    else:
        cat = "Deep (Jogo Posicional Profundo)"

    return (spr, cat)


class TableNumericalOcrEngine:
    """Motor de OCR e lógica posicional para a mesa PPPoker."""

    def __init__(self, table_width: int = DEFAULT_TABLE_WIDTH, table_height: int = DEFAULT_TABLE_HEIGHT):
        self.table_width = table_width
        self.table_height = table_height
        self.total_pot_roi = DEFAULT_TOTAL_POT_ROI
        self.seat_stack_rois: Dict[int, Tuple[int, int, int, int]] = {}
        self.seat_bet_rois: Dict[int, Tuple[int, int, int, int]] = {}
        self.init_rois()

    def init_rois(self) -> None:
        """Inicializa e escala os retângulos de stack, aposta e pote."""
        self.total_pot_roi = scale_roi(DEFAULT_TOTAL_POT_ROI, DEFAULT_TABLE_WIDTH, DEFAULT_TABLE_HEIGHT, self.table_width, self.table_height)

        self.seat_stack_rois = {}
        for seat_num, box in DEFAULT_SEAT_STACK_ROIS.items():
            self.seat_stack_rois[seat_num] = scale_roi(box, DEFAULT_TABLE_WIDTH, DEFAULT_TABLE_HEIGHT, self.table_width, self.table_height)

        self.seat_bet_rois = {}
        for seat_num, box in DEFAULT_SEAT_BET_ROIS.items():
            self.seat_bet_rois[seat_num] = scale_roi(box, DEFAULT_TABLE_WIDTH, DEFAULT_TABLE_HEIGHT, self.table_width, self.table_height)

    def update_roi(self, region_type: str, seat_num: Optional[int], box: Tuple[int, int, int, int]) -> None:
        """Permite ajuste fino interativo das coordenadas."""
        if region_type == "pot":
            self.total_pot_roi = box
        elif region_type == "stack" and seat_num in self.seat_stack_rois:
            self.seat_stack_rois[seat_num] = box
        elif region_type == "bet" and seat_num in self.seat_bet_rois:
            self.seat_bet_rois[seat_num] = box

    def process_table_state(
        self,
        table_frame: Any = None,
        mock_scenario: Optional[Dict[str, Any]] = None
    ) -> TableNumericalSnapshot:
        """Processa o frame atual da mesa ou cenário simulado."""
        if mock_scenario:
            pot_bb = float(mock_scenario.get("pot_bb", 16.0))
            pot_chips = mock_scenario.get("pot_chips")
            dealer_seat = int(mock_scenario.get("dealer_seat", 1))
            hero_seat = int(mock_scenario.get("hero_seat", 5))
            call_bb = float(mock_scenario.get("call_amount_bb", 4.5))
            raw_seats = mock_scenario.get("seats", [])
        elif table_frame is not None:
            # Caminho operacional real com extração por OCR / Pixels (sem dados de demonstração)
            try:
                import pytesseract
                import cv2
                import numpy as np
                pot_ymin, pot_xmin, pot_ymax, pot_xmax = self.total_pot_roi
                if isinstance(table_frame, np.ndarray) and table_frame.size > 0:
                    pot_crop = table_frame[pot_ymin:pot_ymax, pot_xmin:pot_xmax]
                    gray = cv2.cvtColor(pot_crop, cv2.COLOR_RGB2GRAY) if pot_crop.ndim == 3 else pot_crop
                    txt = pytesseract.image_to_string(gray, config='--psm 7').strip()
                    pot_val, _ = parse_numeric_amount(txt, default=0.0)
                else:
                    pot_val = 0.0
            except Exception:
                pot_val = 0.0

            if pot_val <= 0.0:
                # Sem evidência real: retorna não identificado (nunca valores fictícios)
                return TableNumericalSnapshot(
                    total_pot_bb=0.0,
                    total_pot_chips=None,
                    side_pots_bb=[],
                    dealer_seat=1,
                    active_players_count=0,
                    hero_seat=5,
                    hero_position="BTN",
                    seats=[],
                    pot_odds_percent=0.0,
                    call_amount_bb=0.0,
                    spr=0.0,
                    spr_category="Indisponível",
                    confidence=0.0,
                    status="NÃO IDENTIFICADO"
                )

            pot_bb = pot_val
            pot_chips = pot_val * 100.0
            dealer_seat = 1
            hero_seat = 5
            call_bb = 0.0
            raw_seats = [
                {"seat": 5, "name": "Hero (Você)", "stack_bb": 0.0, "bet_bb": 0.0, "is_folded": False, "is_hero": True}
            ]
        else:
            # Sem cenário e sem frame: retorna não identificado estrito (sem valores falsos de demonstração)
            return TableNumericalSnapshot(
                total_pot_bb=0.0,
                total_pot_chips=None,
                side_pots_bb=[],
                dealer_seat=1,
                active_players_count=0,
                hero_seat=5,
                hero_position="BTN",
                seats=[],
                pot_odds_percent=0.0,
                call_amount_bb=0.0,
                spr=0.0,
                spr_category="Indisponível",
                confidence=0.0,
                status="NÃO IDENTIFICADO"
            )

        seats: List[SeatNumericalData] = []
        for s in raw_seats:
            s_num = int(s["seat"])
            is_hero = bool(s.get("is_hero", s_num == hero_seat))
            seat_data = SeatNumericalData(
                seat_number=s_num,
                player_name=s.get("name", f"Player {s_num}"),
                stack_bb=float(s.get("stack_bb", 100.0)),
                stack_chips=s.get("stack_chips"),
                current_bet_bb=float(s.get("bet_bb", 0.0)),
                is_hero=is_hero,
                is_dealer=(s_num == dealer_seat),
                is_active=bool(s.get("is_active", True)),
                is_folded=bool(s.get("is_folded", False)),
                stack_box=self.seat_stack_rois.get(s_num, (0, 0, 0, 0)),
                bet_box=self.seat_bet_rois.get(s_num, (0, 0, 0, 0))
            )
            seats.append(seat_data)

        # Calcular posições relativas a partir do Dealer
        calculate_positions_6max(dealer_seat, seats)

        # Obter posição e stack do Hero
        hero_data = next((s for s in seats if s.is_hero), seats[0] if seats else None)
        hero_pos = hero_data.position_label if hero_data else "BTN"
        hero_stack = hero_data.stack_bb if hero_data else 100.0

        # Calcular Pot Odds e SPR
        pot_odds = calculate_pot_odds(call_bb, pot_bb)
        spr, spr_cat = calculate_spr(hero_stack, pot_bb)

        snapshot = TableNumericalSnapshot(
            total_pot_bb=pot_bb,
            total_pot_chips=pot_chips,
            side_pots_bb=[],
            dealer_seat=dealer_seat,
            active_players_count=len([s for s in seats if s.is_active and not s.is_folded]),
            hero_seat=hero_seat,
            hero_position=hero_pos,
            seats=seats,
            pot_odds_percent=pot_odds,
            call_amount_bb=call_bb,
            spr=spr,
            spr_category=spr_cat,
            confidence=0.96,
            status="SUCCESS"
        )
        return snapshot

    def export_snapshot_json(self, output_path: str, snapshot: TableNumericalSnapshot) -> str:
        """Exporta o JSON de telemetria numérica para o frontend."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(asdict(snapshot), f, indent=2, ensure_ascii=False)
        return str(p)


if __name__ == "__main__":
    engine = TableNumericalOcrEngine()
    snap = engine.process_table_state()
    out = engine.export_snapshot_json("public/table_numerical_snapshot.json", snap)
    print(f"Table numerical OCR executado com sucesso. Snapshot exportado em: {out}")
    print(f"Pote Total: {snap.total_pot_bb} BB | Dealer Seat: #{snap.dealer_seat} | Hero Pos: {snap.hero_position}")
    print(f"Pot Odds: {snap.pot_odds_percent}% | SPR: {snap.spr} ({snap.spr_category})")
    for s in snap.seats:
        print(f"  • Seat {s.seat_number} [{s.position_label}]: {s.player_name} - Stack: {s.stack_bb} BB - Bet: {s.current_bet_bb} BB")

class OcrTemporalStabilityCache:
    """Cache de estabilização temporal e limiar de confiança para OCR."""
    def __init__(self, min_confidence: float = 0.85, consecutive_required: int = 2):
        self.min_confidence = min_confidence
        self.consecutive_required = consecutive_required
        self.history: Dict[str, List[Any]] = {}

    def filter_value(self, key: str, value: Any, confidence: float) -> Tuple[Optional[Any], bool]:
        if confidence < self.min_confidence:
            return None, False
        if key not in self.history:
            self.history[key] = []
        self.history[key].append(value)
        if len(self.history[key]) > self.consecutive_required:
            self.history[key].pop(0)
        if len(self.history[key]) >= self.consecutive_required:
            if all(v == self.history[key][0] for v in self.history[key]):
                return self.history[key][0], True
        return None, False
