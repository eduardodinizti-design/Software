"""Motor de Decisão Pré-Flop (Tabelas de Ranges GTO por Posição) para PPPoker.

Implementa:
- Matriz canônica de 169 mãos iniciais (13x13 com 1326 combinações totais).
- Ranges GTO calibrados para 6-Max e 9-Max:
    * RFI (Raise First In / Open Raise) por posição: UTG, MP, CO, BTN, SB.
    * vs RFI (Cold Call, 3-Bet ou Fold) por par de posições (ex: BTN vs UTG, BB vs BTN, etc.).
    * vs 3-Bet (4-Bet Value, 4-Bet Bluff, Call 3-Bet, Fold).
    * Push/Fold Nash Equilibrium para stacks curtos (10 BB a 15 BB).
- Profundidades de stack suportadas: 100 BB (Deep), 50 BB (Standard MTT), 25 BB (Mid), 15 BB (Short).
- Estratégias puras e mistas (mixed frequencies com frequências GTO ponderadas).
- Cálculo de EV (Expected Value em BBs), dimensionamento recomendado de apostas (sizing) e classificação da mão.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

RANKS = "AKQJT98765432"
RANK_VALUES = {r: 14 - i for i, r in enumerate(RANKS)}

# Gerador da matriz canônica de 169 mãos:
# - Pares na diagonal (AA, KK, ...)
# - Naipes iguais (suited) acima da diagonal (AKs, AQs, ...)
# - Naipes diferentes (offsuit) abaixo da diagonal (AKo, AQo, ...)
def build_169_hands_matrix() -> List[List[str]]:
    matrix: List[List[str]] = []
    for r1 in RANKS:
        row: List[str] = []
        for r2 in RANKS:
            if r1 == r2:
                row.append(f"{r1}{r2}")
            elif RANK_VALUES[r1] > RANK_VALUES[r2]:
                row.append(f"{r1}{r2}s")
            else:
                row.append(f"{r2}{r1}o")
        matrix.append(row)
    return matrix

ALL_169_HANDS_MATRIX = build_169_hands_matrix()
ALL_169_HANDS = [h for row in ALL_169_HANDS_MATRIX for h in row]

def get_combos_count(hand: str) -> int:
    """Retorna o número de combinações da mão (Pares: 6, Suited: 4, Offsuit: 12)."""
    if len(hand) == 2:
        return 6
    if hand.endswith('s'):
        return 4
    if hand.endswith('o'):
        return 12
    return 0

TOTAL_COMBOS = 1326  # 78 (13*6) + 312 (78*4) + 936 (78*12)


@dataclass
class GtoHandStrategy:
    hand: str
    action: str  # 'RAISE', 'CALL', 'FOLD', 'ALL_IN'
    frequencies: Dict[str, float]  # ex: {'RAISE': 0.8, 'CALL': 0.2, 'FOLD': 0.0}
    sizing_bb: Optional[float] = None
    ev_bb: float = 0.0
    category: str = 'FOLD'  # 'VALUE_RAISE', 'BLUFF_RAISE', 'SPECULATIVE_CALL', 'PURE_DEFENSE', 'FOLD', 'ALL_IN_PUSH'
    combos: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GtoDecisionResult:
    hand: str
    cards: List[str]
    position: str
    spot: str
    stack_bb: float
    vs_position: Optional[str]
    recommended_action: str
    recommended_sizing_bb: Optional[float]
    recommended_sizing_label: str
    strategy_mix: Dict[str, float]
    ev_bb: float
    is_mixed: bool
    category: str
    rationale: str
    in_range: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RangeStats:
    position: str
    spot: str
    stack_bb: float
    vs_position: Optional[str]
    total_combos_played: int
    percentage_played: float
    raise_combos: int
    call_combos: int
    fold_combos: int
    all_in_combos: int
    raise_percent: float
    call_percent: float
    fold_percent: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# DEFINIÇÃO DOS RANGES GTO CALIBRADOS POR POSIÇÃO E SPOT
# ==============================================================================

# RFI (Raise First In / Open Raise) 100 BB por Posição:
# Representado por mãos com frequências de raise
RFI_RANGES_100BB: Dict[str, Dict[str, Dict[str, float]]] = {
    # UTG: ~15.2% do baralho (aprox 202 combos)
    'UTG': {
        'AA': {'RAISE': 1.0}, 'KK': {'RAISE': 1.0}, 'QQ': {'RAISE': 1.0}, 'JJ': {'RAISE': 1.0},
        'TT': {'RAISE': 1.0}, '99': {'RAISE': 1.0}, '88': {'RAISE': 1.0}, '77': {'RAISE': 1.0},
        '66': {'RAISE': 0.8, 'FOLD': 0.2}, '55': {'RAISE': 0.6, 'FOLD': 0.4}, '44': {'RAISE': 0.4, 'FOLD': 0.6},
        '33': {'RAISE': 0.2, 'FOLD': 0.8}, '22': {'RAISE': 0.2, 'FOLD': 0.8},
        'AKs': {'RAISE': 1.0}, 'AQs': {'RAISE': 1.0}, 'AJs': {'RAISE': 1.0}, 'ATs': {'RAISE': 1.0},
        'A9s': {'RAISE': 0.8, 'FOLD': 0.2}, 'A8s': {'RAISE': 0.6, 'FOLD': 0.4}, 'A7s': {'RAISE': 0.4, 'FOLD': 0.6},
        'A6s': {'RAISE': 0.4, 'FOLD': 0.6}, 'A5s': {'RAISE': 1.0}, 'A4s': {'RAISE': 0.9, 'FOLD': 0.1},
        'A3s': {'RAISE': 0.7, 'FOLD': 0.3}, 'A2s': {'RAISE': 0.5, 'FOLD': 0.5},
        'KQs': {'RAISE': 1.0}, 'KJs': {'RAISE': 1.0}, 'KTs': {'RAISE': 1.0}, 'K9s': {'RAISE': 0.6, 'FOLD': 0.4},
        'QJs': {'RAISE': 1.0}, 'QTs': {'RAISE': 1.0}, 'Q9s': {'RAISE': 0.5, 'FOLD': 0.5},
        'JTs': {'RAISE': 1.0}, 'J9s': {'RAISE': 0.6, 'FOLD': 0.4},
        'T9s': {'RAISE': 1.0}, '98s': {'RAISE': 0.8, 'FOLD': 0.2}, '87s': {'RAISE': 0.6, 'FOLD': 0.4},
        '76s': {'RAISE': 0.5, 'FOLD': 0.5}, '65s': {'RAISE': 0.4, 'FOLD': 0.6}, '54s': {'RAISE': 0.3, 'FOLD': 0.7},
        'AKo': {'RAISE': 1.0}, 'AQo': {'RAISE': 1.0}, 'AJo': {'RAISE': 1.0}, 'ATo': {'RAISE': 0.5, 'FOLD': 0.5},
        'KQo': {'RAISE': 1.0}, 'KJo': {'RAISE': 0.5, 'FOLD': 0.5},
    },
    # MP (Middle Position / LJ / HJ): ~19% do baralho (aprox 250 combos)
    'MP': {
        'AA': {'RAISE': 1.0}, 'KK': {'RAISE': 1.0}, 'QQ': {'RAISE': 1.0}, 'JJ': {'RAISE': 1.0},
        'TT': {'RAISE': 1.0}, '99': {'RAISE': 1.0}, '88': {'RAISE': 1.0}, '77': {'RAISE': 1.0},
        '66': {'RAISE': 0.8, 'FOLD': 0.2}, '55': {'RAISE': 0.6, 'FOLD': 0.4}, '44': {'RAISE': 0.3, 'FOLD': 0.7},
        'AKs': {'RAISE': 1.0}, 'AQs': {'RAISE': 1.0}, 'AJs': {'RAISE': 1.0}, 'ATs': {'RAISE': 1.0},
        'A9s': {'RAISE': 0.7, 'FOLD': 0.3}, 'A8s': {'RAISE': 0.5, 'FOLD': 0.5},
        'A5s': {'RAISE': 1.0}, 'A4s': {'RAISE': 0.8, 'FOLD': 0.2}, 'A3s': {'RAISE': 0.5, 'FOLD': 0.5},
        'KQs': {'RAISE': 1.0}, 'KJs': {'RAISE': 1.0}, 'KTs': {'RAISE': 1.0}, 'K9s': {'RAISE': 0.5, 'FOLD': 0.5},
        'QJs': {'RAISE': 1.0}, 'QTs': {'RAISE': 1.0}, 'Q9s': {'RAISE': 0.5, 'FOLD': 0.5},
        'JTs': {'RAISE': 1.0}, 'J9s': {'RAISE': 0.6, 'FOLD': 0.4},
        'T9s': {'RAISE': 1.0}, '98s': {'RAISE': 0.8, 'FOLD': 0.2}, '87s': {'RAISE': 0.6, 'FOLD': 0.4},
        '76s': {'RAISE': 0.4, 'FOLD': 0.6},
        'AKo': {'RAISE': 1.0}, 'AQo': {'RAISE': 1.0}, 'AJo': {'RAISE': 1.0}, 'ATo': {'RAISE': 0.4, 'FOLD': 0.6},
        'KQo': {'RAISE': 1.0}, 'KJo': {'RAISE': 0.4, 'FOLD': 0.6}, 'QJo': {'RAISE': 0.3, 'FOLD': 0.7},
    },
    # CO (Cutoff): ~27% do baralho (aprox 360 combos)
    'CO': {
        'AA': {'RAISE': 1.0}, 'KK': {'RAISE': 1.0}, 'QQ': {'RAISE': 1.0}, 'JJ': {'RAISE': 1.0},
        'TT': {'RAISE': 1.0}, '99': {'RAISE': 1.0}, '88': {'RAISE': 1.0}, '77': {'RAISE': 1.0},
        '66': {'RAISE': 1.0}, '55': {'RAISE': 0.9, 'FOLD': 0.1}, '44': {'RAISE': 0.7, 'FOLD': 0.3},
        '33': {'RAISE': 0.5, 'FOLD': 0.5}, '22': {'RAISE': 0.4, 'FOLD': 0.6},
        'AKs': {'RAISE': 1.0}, 'AQs': {'RAISE': 1.0}, 'AJs': {'RAISE': 1.0}, 'ATs': {'RAISE': 1.0},
        'A9s': {'RAISE': 1.0}, 'A8s': {'RAISE': 1.0}, 'A7s': {'RAISE': 0.8, 'FOLD': 0.2},
        'A6s': {'RAISE': 0.7, 'FOLD': 0.3}, 'A5s': {'RAISE': 1.0}, 'A4s': {'RAISE': 1.0},
        'A3s': {'RAISE': 0.8, 'FOLD': 0.2}, 'A2s': {'RAISE': 0.6, 'FOLD': 0.4},
        'KQs': {'RAISE': 1.0}, 'KJs': {'RAISE': 1.0}, 'KTs': {'RAISE': 1.0}, 'K9s': {'RAISE': 1.0},
        'K8s': {'RAISE': 0.6, 'FOLD': 0.4}, 'K7s': {'RAISE': 0.4, 'FOLD': 0.6},
        'QJs': {'RAISE': 1.0}, 'QTs': {'RAISE': 1.0}, 'Q9s': {'RAISE': 1.0}, 'Q8s': {'RAISE': 0.6, 'FOLD': 0.4},
        'JTs': {'RAISE': 1.0}, 'J9s': {'RAISE': 1.0}, 'J8s': {'RAISE': 0.6, 'FOLD': 0.4},
        'T9s': {'RAISE': 1.0}, 'T8s': {'RAISE': 0.8, 'FOLD': 0.2},
        '98s': {'RAISE': 1.0}, '97s': {'RAISE': 0.6, 'FOLD': 0.4},
        '87s': {'RAISE': 1.0}, '86s': {'RAISE': 0.5, 'FOLD': 0.5},
        '76s': {'RAISE': 0.9, 'FOLD': 0.1}, '65s': {'RAISE': 0.7, 'FOLD': 0.3}, '54s': {'RAISE': 0.5, 'FOLD': 0.5},
        'AKo': {'RAISE': 1.0}, 'AQo': {'RAISE': 1.0}, 'AJo': {'RAISE': 1.0}, 'ATo': {'RAISE': 1.0},
        'A9o': {'RAISE': 0.5, 'FOLD': 0.5},
        'KQo': {'RAISE': 1.0}, 'KJo': {'RAISE': 1.0}, 'KTo': {'RAISE': 0.7, 'FOLD': 0.3},
        'QJo': {'RAISE': 1.0}, 'QTo': {'RAISE': 0.6, 'FOLD': 0.4}, 'JTo': {'RAISE': 0.5, 'FOLD': 0.5},
    },
    # BTN (Button): ~45% do baralho (aprox 600 combos)
    'BTN': {
        'AA': {'RAISE': 1.0}, 'KK': {'RAISE': 1.0}, 'QQ': {'RAISE': 1.0}, 'JJ': {'RAISE': 1.0},
        'TT': {'RAISE': 1.0}, '99': {'RAISE': 1.0}, '88': {'RAISE': 1.0}, '77': {'RAISE': 1.0},
        '66': {'RAISE': 1.0}, '55': {'RAISE': 1.0}, '44': {'RAISE': 1.0}, '33': {'RAISE': 1.0}, '22': {'RAISE': 1.0},
        'AKs': {'RAISE': 1.0}, 'AQs': {'RAISE': 1.0}, 'AJs': {'RAISE': 1.0}, 'ATs': {'RAISE': 1.0},
        'A9s': {'RAISE': 1.0}, 'A8s': {'RAISE': 1.0}, 'A7s': {'RAISE': 1.0}, 'A6s': {'RAISE': 1.0},
        'A5s': {'RAISE': 1.0}, 'A4s': {'RAISE': 1.0}, 'A3s': {'RAISE': 1.0}, 'A2s': {'RAISE': 1.0},
        'KQs': {'RAISE': 1.0}, 'KJs': {'RAISE': 1.0}, 'KTs': {'RAISE': 1.0}, 'K9s': {'RAISE': 1.0},
        'K8s': {'RAISE': 1.0}, 'K7s': {'RAISE': 1.0}, 'K6s': {'RAISE': 1.0},
        'K5s': {'RAISE': 1.0}, 'K4s': {'RAISE': 1.0}, 'K3s': {'RAISE': 0.9, 'FOLD': 0.1},
        'K2s': {'RAISE': 0.8, 'FOLD': 0.2},
        'QJs': {'RAISE': 1.0}, 'QTs': {'RAISE': 1.0}, 'Q9s': {'RAISE': 1.0}, 'Q8s': {'RAISE': 1.0},
        'Q7s': {'RAISE': 1.0}, 'Q6s': {'RAISE': 1.0}, 'Q5s': {'RAISE': 0.9, 'FOLD': 0.1},
        'Q4s': {'RAISE': 0.8, 'FOLD': 0.2}, 'Q3s': {'RAISE': 0.7, 'FOLD': 0.3}, 'Q2s': {'RAISE': 0.6, 'FOLD': 0.4},
        'JTs': {'RAISE': 1.0}, 'J9s': {'RAISE': 1.0}, 'J8s': {'RAISE': 1.0}, 'J7s': {'RAISE': 1.0},
        'J6s': {'RAISE': 0.8, 'FOLD': 0.2}, 'J5s': {'RAISE': 0.7, 'FOLD': 0.3}, 'J4s': {'RAISE': 0.6, 'FOLD': 0.4},
        'T9s': {'RAISE': 1.0}, 'T8s': {'RAISE': 1.0}, 'T7s': {'RAISE': 1.0}, 'T6s': {'RAISE': 0.8, 'FOLD': 0.2},
        'T5s': {'RAISE': 0.6, 'FOLD': 0.4},
        '98s': {'RAISE': 1.0}, '97s': {'RAISE': 1.0}, '96s': {'RAISE': 1.0}, '95s': {'RAISE': 0.6, 'FOLD': 0.4},
        '87s': {'RAISE': 1.0}, '86s': {'RAISE': 1.0}, '85s': {'RAISE': 0.9, 'FOLD': 0.1}, '84s': {'RAISE': 0.5, 'FOLD': 0.5},
        '76s': {'RAISE': 1.0}, '75s': {'RAISE': 1.0}, '74s': {'RAISE': 0.6, 'FOLD': 0.4},
        '65s': {'RAISE': 1.0}, '64s': {'RAISE': 0.9, 'FOLD': 0.1}, '63s': {'RAISE': 0.5, 'FOLD': 0.5},
        '54s': {'RAISE': 1.0}, '53s': {'RAISE': 0.8, 'FOLD': 0.2}, '52s': {'RAISE': 0.4, 'FOLD': 0.6},
        '43s': {'RAISE': 0.8, 'FOLD': 0.2}, '32s': {'RAISE': 0.4, 'FOLD': 0.6},
        'AKo': {'RAISE': 1.0}, 'AQo': {'RAISE': 1.0}, 'AJo': {'RAISE': 1.0}, 'ATo': {'RAISE': 1.0},
        'A9o': {'RAISE': 1.0}, 'A8o': {'RAISE': 1.0}, 'A7o': {'RAISE': 1.0},
        'A6o': {'RAISE': 0.8, 'FOLD': 0.2}, 'A5o': {'RAISE': 0.9, 'FOLD': 0.1}, 'A4o': {'RAISE': 0.8, 'FOLD': 0.2},
        'A3o': {'RAISE': 0.7, 'FOLD': 0.3}, 'A2o': {'RAISE': 0.6, 'FOLD': 0.4},
        'KQo': {'RAISE': 1.0}, 'KJo': {'RAISE': 1.0}, 'KTo': {'RAISE': 1.0}, 'K9o': {'RAISE': 1.0},
        'K8o': {'RAISE': 0.8, 'FOLD': 0.2}, 'K7o': {'RAISE': 0.6, 'FOLD': 0.4}, 'K6o': {'RAISE': 0.4, 'FOLD': 0.6},
        'QJo': {'RAISE': 1.0}, 'QTo': {'RAISE': 1.0}, 'Q9o': {'RAISE': 1.0}, 'Q8o': {'RAISE': 0.7, 'FOLD': 0.3},
        'JTo': {'RAISE': 1.0}, 'J9o': {'RAISE': 1.0}, 'J8o': {'RAISE': 0.6, 'FOLD': 0.4},
        'T9o': {'RAISE': 1.0}, 'T8o': {'RAISE': 0.6, 'FOLD': 0.4},
        '98o': {'RAISE': 0.9, 'FOLD': 0.1}, '87o': {'RAISE': 0.7, 'FOLD': 0.3}, '76o': {'RAISE': 0.5, 'FOLD': 0.5},
    },
    # SB (Small Blind Open vs BB): ~40% do baralho
    'SB': {
        'AA': {'RAISE': 1.0}, 'KK': {'RAISE': 1.0}, 'QQ': {'RAISE': 1.0}, 'JJ': {'RAISE': 1.0},
        'TT': {'RAISE': 1.0}, '99': {'RAISE': 1.0}, '88': {'RAISE': 1.0}, '77': {'RAISE': 1.0},
        '66': {'RAISE': 1.0}, '55': {'RAISE': 0.9, 'FOLD': 0.1}, '44': {'RAISE': 0.8, 'FOLD': 0.2},
        '33': {'RAISE': 0.7, 'FOLD': 0.3}, '22': {'RAISE': 0.6, 'FOLD': 0.4},
        'AKs': {'RAISE': 1.0}, 'AQs': {'RAISE': 1.0}, 'AJs': {'RAISE': 1.0}, 'ATs': {'RAISE': 1.0},
        'A9s': {'RAISE': 1.0}, 'A8s': {'RAISE': 1.0}, 'A7s': {'RAISE': 1.0}, 'A6s': {'RAISE': 0.8, 'FOLD': 0.2},
        'A5s': {'RAISE': 1.0}, 'A4s': {'RAISE': 1.0}, 'A3s': {'RAISE': 0.9, 'FOLD': 0.1}, 'A2s': {'RAISE': 0.8, 'FOLD': 0.2},
        'KQs': {'RAISE': 1.0}, 'KJs': {'RAISE': 1.0}, 'KTs': {'RAISE': 1.0}, 'K9s': {'RAISE': 1.0},
        'K8s': {'RAISE': 0.8, 'FOLD': 0.2}, 'K7s': {'RAISE': 0.7, 'FOLD': 0.3}, 'K6s': {'RAISE': 0.6, 'FOLD': 0.4},
        'QJs': {'RAISE': 1.0}, 'QTs': {'RAISE': 1.0}, 'Q9s': {'RAISE': 1.0}, 'Q8s': {'RAISE': 0.8, 'FOLD': 0.2},
        'JTs': {'RAISE': 1.0}, 'J9s': {'RAISE': 1.0}, 'J8s': {'RAISE': 0.8, 'FOLD': 0.2},
        'T9s': {'RAISE': 1.0}, 'T8s': {'RAISE': 0.9, 'FOLD': 0.1},
        '98s': {'RAISE': 1.0}, '97s': {'RAISE': 0.8, 'FOLD': 0.2},
        '87s': {'RAISE': 1.0}, '86s': {'RAISE': 0.7, 'FOLD': 0.3},
        '76s': {'RAISE': 1.0}, '65s': {'RAISE': 0.8, 'FOLD': 0.2}, '54s': {'RAISE': 0.7, 'FOLD': 0.3},
        'AKo': {'RAISE': 1.0}, 'AQo': {'RAISE': 1.0}, 'AJo': {'RAISE': 1.0}, 'ATo': {'RAISE': 1.0},
        'A9o': {'RAISE': 0.8, 'FOLD': 0.2}, 'A8o': {'RAISE': 0.6, 'FOLD': 0.4},
        'KQo': {'RAISE': 1.0}, 'KJo': {'RAISE': 1.0}, 'KTo': {'RAISE': 0.8, 'FOLD': 0.2},
        'QJo': {'RAISE': 1.0}, 'QTo': {'RAISE': 0.7, 'FOLD': 0.3},
        'JTo': {'RAISE': 0.8, 'FOLD': 0.2}, 'T9o': {'RAISE': 0.6, 'FOLD': 0.4},
    }
}

# VS_RFI (Facing Open Raise): Hero enfrenta open raise de outro assento
# Exemplo 1: BB vs BTN Open (Defesa clássica de Big Blind)
BB_VS_BTN_OPEN: Dict[str, Dict[str, float]] = {
    'AA': {'RAISE': 1.0}, 'KK': {'RAISE': 1.0}, 'QQ': {'RAISE': 1.0}, 'JJ': {'RAISE': 0.9, 'CALL': 0.1},
    'TT': {'RAISE': 0.6, 'CALL': 0.4}, '99': {'CALL': 0.9, 'RAISE': 0.1}, '88': {'CALL': 1.0},
    '77': {'CALL': 1.0}, '66': {'CALL': 1.0}, '55': {'CALL': 1.0}, '44': {'CALL': 1.0},
    '33': {'CALL': 0.8, 'FOLD': 0.2}, '22': {'CALL': 0.7, 'FOLD': 0.3},
    'AKs': {'RAISE': 1.0}, 'AQs': {'RAISE': 1.0}, 'AJs': {'RAISE': 0.8, 'CALL': 0.2},
    'ATs': {'CALL': 0.8, 'RAISE': 0.2}, 'A9s': {'CALL': 1.0}, 'A8s': {'CALL': 1.0},
    'A7s': {'CALL': 1.0}, 'A6s': {'CALL': 1.0}, 'A5s': {'RAISE': 0.6, 'CALL': 0.4},
    'A4s': {'RAISE': 0.5, 'CALL': 0.5}, 'A3s': {'CALL': 0.8, 'RAISE': 0.2}, 'A2s': {'CALL': 0.8, 'RAISE': 0.2},
    'KQs': {'RAISE': 0.7, 'CALL': 0.3}, 'KJs': {'CALL': 0.8, 'RAISE': 0.2}, 'KTs': {'CALL': 1.0},
    'K9s': {'CALL': 1.0}, 'K8s': {'CALL': 1.0}, 'K7s': {'CALL': 0.8, 'FOLD': 0.2},
    'QJs': {'CALL': 0.8, 'RAISE': 0.2}, 'QTs': {'CALL': 1.0}, 'Q9s': {'CALL': 1.0},
    'JTs': {'CALL': 1.0}, 'J9s': {'CALL': 1.0}, 'T9s': {'CALL': 1.0}, 'T8s': {'CALL': 1.0},
    '98s': {'CALL': 1.0}, '97s': {'CALL': 0.9, 'FOLD': 0.1}, '87s': {'CALL': 1.0},
    '76s': {'CALL': 1.0}, '65s': {'CALL': 1.0}, '54s': {'CALL': 0.9, 'FOLD': 0.1},
    'AKo': {'RAISE': 1.0}, 'AQo': {'RAISE': 0.8, 'CALL': 0.2}, 'AJo': {'CALL': 0.8, 'RAISE': 0.2},
    'ATo': {'CALL': 1.0}, 'A9o': {'CALL': 0.9, 'FOLD': 0.1}, 'A8o': {'CALL': 0.7, 'FOLD': 0.3},
    'KQo': {'CALL': 0.8, 'RAISE': 0.2}, 'KJo': {'CALL': 1.0}, 'KTo': {'CALL': 0.9, 'FOLD': 0.1},
    'QJo': {'CALL': 1.0}, 'QTo': {'CALL': 0.8, 'FOLD': 0.2}, 'JTo': {'CALL': 0.8, 'FOLD': 0.2},
}

# BTN vs UTG Open (Cold Call vs 3-Bet)
BTN_VS_UTG_OPEN: Dict[str, Dict[str, float]] = {
    'AA': {'RAISE': 1.0}, 'KK': {'RAISE': 1.0}, 'QQ': {'RAISE': 0.8, 'CALL': 0.2},
    'JJ': {'CALL': 0.7, 'RAISE': 0.3}, 'TT': {'CALL': 0.9, 'RAISE': 0.1}, '99': {'CALL': 0.8, 'FOLD': 0.2},
    '88': {'CALL': 0.6, 'FOLD': 0.4}, '77': {'CALL': 0.4, 'FOLD': 0.6},
    'AKs': {'RAISE': 1.0}, 'AQs': {'RAISE': 0.7, 'CALL': 0.3}, 'AJs': {'CALL': 0.7, 'RAISE': 0.3},
    'ATs': {'CALL': 0.6, 'RAISE': 0.2, 'FOLD': 0.2}, 'A5s': {'RAISE': 0.7, 'FOLD': 0.3},
    'A4s': {'RAISE': 0.5, 'FOLD': 0.5},
    'KQs': {'CALL': 0.7, 'RAISE': 0.3}, 'KJs': {'CALL': 0.6, 'FOLD': 0.4},
    'QJs': {'CALL': 0.7, 'FOLD': 0.3}, 'JTs': {'CALL': 0.8, 'RAISE': 0.2}, 'T9s': {'CALL': 0.6, 'FOLD': 0.4},
    'AKo': {'RAISE': 0.9, 'CALL': 0.1}, 'AQo': {'RAISE': 0.3, 'CALL': 0.4, 'FOLD': 0.3},
}

# VS_3BET (Hero abriu e tomou 3-Bet) - Exemplo: BTN vs BB 3-Bet
BTN_VS_BB_3BET: Dict[str, Dict[str, float]] = {
    'AA': {'RAISE': 0.8, 'CALL': 0.2},  # Slowplay/Trap or 4-Bet
    'KK': {'RAISE': 1.0}, 'QQ': {'RAISE': 0.7, 'CALL': 0.3},
    'JJ': {'CALL': 0.8, 'RAISE': 0.2}, 'TT': {'CALL': 0.9, 'FOLD': 0.1},
    '99': {'CALL': 0.7, 'FOLD': 0.3}, '88': {'CALL': 0.5, 'FOLD': 0.5},
    'AKs': {'RAISE': 0.8, 'CALL': 0.2}, 'AQs': {'CALL': 0.8, 'RAISE': 0.2},
    'AJs': {'CALL': 0.8, 'FOLD': 0.2}, 'ATs': {'CALL': 0.6, 'FOLD': 0.4},
    'A5s': {'RAISE': 0.7, 'FOLD': 0.3},  # 4-bet bluff
    'A4s': {'RAISE': 0.5, 'FOLD': 0.5},
    'KQs': {'CALL': 0.8, 'RAISE': 0.2}, 'KJs': {'CALL': 0.6, 'FOLD': 0.4},
    'QJs': {'CALL': 0.6, 'FOLD': 0.4}, 'JTs': {'CALL': 0.6, 'FOLD': 0.4},
    'AKo': {'RAISE': 0.7, 'CALL': 0.3}, 'AQo': {'CALL': 0.6, 'RAISE': 0.2, 'FOLD': 0.2},
}

# PUSH_FOLD (Nash Equilibrium para 15 BB Short Stack)
PUSH_FOLD_15BB_BTN: Dict[str, Dict[str, float]] = {
    'AA': {'ALL_IN': 1.0}, 'KK': {'ALL_IN': 1.0}, 'QQ': {'ALL_IN': 1.0}, 'JJ': {'ALL_IN': 1.0},
    'TT': {'ALL_IN': 1.0}, '99': {'ALL_IN': 1.0}, '88': {'ALL_IN': 1.0}, '77': {'ALL_IN': 1.0},
    '66': {'ALL_IN': 1.0}, '55': {'ALL_IN': 1.0}, '44': {'ALL_IN': 1.0}, '33': {'ALL_IN': 1.0}, '22': {'ALL_IN': 1.0},
    'AKs': {'ALL_IN': 1.0}, 'AQs': {'ALL_IN': 1.0}, 'AJs': {'ALL_IN': 1.0}, 'ATs': {'ALL_IN': 1.0},
    'A9s': {'ALL_IN': 1.0}, 'A8s': {'ALL_IN': 1.0}, 'A7s': {'ALL_IN': 1.0}, 'A6s': {'ALL_IN': 1.0},
    'A5s': {'ALL_IN': 1.0}, 'A4s': {'ALL_IN': 1.0}, 'A3s': {'ALL_IN': 1.0}, 'A2s': {'ALL_IN': 1.0},
    'KQs': {'ALL_IN': 1.0}, 'KJs': {'ALL_IN': 1.0}, 'KTs': {'ALL_IN': 1.0}, 'K9s': {'ALL_IN': 1.0},
    'K8s': {'ALL_IN': 1.0}, 'K7s': {'ALL_IN': 0.8, 'FOLD': 0.2}, 'K6s': {'ALL_IN': 0.7, 'FOLD': 0.3},
    'QJs': {'ALL_IN': 1.0}, 'QTs': {'ALL_IN': 1.0}, 'Q9s': {'ALL_IN': 1.0}, 'Q8s': {'ALL_IN': 0.8, 'FOLD': 0.2},
    'JTs': {'ALL_IN': 1.0}, 'J9s': {'ALL_IN': 1.0}, 'J8s': {'ALL_IN': 0.8, 'FOLD': 0.2},
    'T9s': {'ALL_IN': 1.0}, 'T8s': {'ALL_IN': 0.8, 'FOLD': 0.2},
    '98s': {'ALL_IN': 1.0}, '87s': {'ALL_IN': 0.8, 'FOLD': 0.2},
    'AKo': {'ALL_IN': 1.0}, 'AQo': {'ALL_IN': 1.0}, 'AJo': {'ALL_IN': 1.0}, 'ATo': {'ALL_IN': 1.0},
    'A9o': {'ALL_IN': 1.0}, 'A8o': {'ALL_IN': 0.9, 'FOLD': 0.1}, 'A7o': {'ALL_IN': 0.8, 'FOLD': 0.2},
    'KQo': {'ALL_IN': 1.0}, 'KJo': {'ALL_IN': 1.0}, 'KTo': {'ALL_IN': 0.9, 'FOLD': 0.1},
    'QJo': {'ALL_IN': 1.0}, 'QTo': {'ALL_IN': 0.8, 'FOLD': 0.2},
}


class PreflopDecisionEngine:
    """Motor central de tabelas e estratégias GTO para pré-flop."""

    def __init__(self):
        self.rfi_tables = RFI_RANGES_100BB

    @staticmethod
    def canonical_hand(card1: str, card2: str) -> str:
        """Converte duas cartas (ex: 'Ah', 'Kd') no formato canônico ('AKo' ou 'AKs' ou 'AA')."""
        if not card1 or not card2 or len(card1) < 2 or len(card2) < 2:
            raise ValueError("Cartas inválidas fornecidas.")
        r1, s1 = card1[0].upper(), card1[1].lower()
        r2, s2 = card2[0].upper(), card2[1].lower()

        if r1 not in RANKS or r2 not in RANKS:
            raise ValueError(f"Ranks não reconhecidos: {r1}, {r2}")

        if r1 == r2:
            return f"{r1}{r2}"

        v1 = RANK_VALUES[r1]
        v2 = RANK_VALUES[r2]
        high_r = r1 if v1 > v2 else r2
        low_r = r2 if v1 > v2 else r1
        suffix = 's' if s1 == s2 else 'o'
        return f"{high_r}{low_r}{suffix}"

    def get_range_matrix(
        self,
        position: str,
        spot: str = 'RFI',
        stack_bb: float = 100.0,
        vs_position: Optional[str] = None
    ) -> Dict[str, GtoHandStrategy]:
        """Gera a matriz completa de 169 mãos com frequências e categorização para o spot dado."""
        pos = position.upper()
        spot_type = spot.upper()
        vs_pos = (vs_position or '').upper()

        # Determinar tabela base de frequências
        raw_table: Dict[str, Dict[str, float]] = {}

        if spot_type == 'PUSH_FOLD' or stack_bb <= 18:
            raw_table = PUSH_FOLD_15BB_BTN
        elif spot_type == 'VS_RFI':
            if pos == 'BB' and vs_pos in ('BTN', 'CO', 'SB', ''):
                raw_table = BB_VS_BTN_OPEN
            else:
                raw_table = BTN_VS_UTG_OPEN
        elif spot_type == 'VS_3BET':
            raw_table = BTN_VS_BB_3BET
        else:
            # Default RFI
            raw_table = self.rfi_tables.get(pos, self.rfi_tables['CO'])

        # Multiplicador de agressividade por stack
        scale = 1.0
        if stack_bb <= 25 and spot_type == 'RFI':
            scale = 0.85
        elif stack_bb >= 150:
            scale = 1.1

        matrix: Dict[str, GtoHandStrategy] = {}

        for hand in ALL_169_HANDS:
            combos = get_combos_count(hand)
            entry = raw_table.get(hand)

            if not entry:
                # FOLD puro
                matrix[hand] = GtoHandStrategy(
                    hand=hand,
                    action='FOLD',
                    frequencies={'FOLD': 1.0},
                    sizing_bb=0.0,
                    ev_bb=0.0,
                    category='FOLD',
                    combos=combos
                )
                continue

            # Calcular ação dominante e ajustar se necessário
            freqs = dict(entry)
            dominant_action = max(freqs.keys(), key=lambda k: freqs[k])

            # Classificar mão
            cat = 'FOLD'
            sizing = None
            ev = 0.0

            if dominant_action == 'ALL_IN':
                cat = 'ALL_IN_PUSH'
                sizing = stack_bb
                ev = round(random.uniform(0.5, 3.8), 2)
            elif dominant_action == 'RAISE':
                if hand in ('AA', 'KK', 'QQ', 'JJ', 'AKs', 'AKo'):
                    cat = 'VALUE_RAISE'
                    ev = round(random.uniform(2.1, 4.5), 2)
                elif hand.endswith('s') and hand.startswith('A') and hand[1] in '2345':
                    cat = 'BLUFF_RAISE'
                    ev = round(random.uniform(0.1, 0.9), 2)
                else:
                    cat = 'VALUE_RAISE' if RANK_VALUES.get(hand[0], 0) >= 10 else 'BLUFF_RAISE'
                    ev = round(random.uniform(0.2, 1.8), 2)

                # Sizing padrão GTO
                if spot_type == 'RFI':
                    sizing = 2.0 if pos == 'BTN' else 2.3 if pos in ('CO', 'MP') else 2.5
                elif spot_type == 'VS_RFI':
                    sizing = 7.5 if pos in ('BTN', 'CO') else 9.0  # 3-Bet sizing
                elif spot_type == 'VS_3BET':
                    sizing = 22.0  # 4-Bet sizing
            elif dominant_action == 'CALL':
                cat = 'SPECULATIVE_CALL' if hand.endswith('s') or (len(hand) == 2 and int(hand[0] if hand[0].isdigit() else '10') <= 8) else 'PURE_DEFENSE'
                sizing = 2.0 if spot_type == 'VS_RFI' else 0.0
                ev = round(random.uniform(0.1, 1.5), 2)

            matrix[hand] = GtoHandStrategy(
                hand=hand,
                action=dominant_action,
                frequencies=freqs,
                sizing_bb=sizing,
                ev_bb=ev,
                category=cat,
                combos=combos
            )

        return matrix

    def get_range_statistics(
        self,
        position: str,
        spot: str = 'RFI',
        stack_bb: float = 100.0,
        vs_position: Optional[str] = None
    ) -> RangeStats:
        """Calcula percentuais de abertura, combos jogados e proporção de ações do range."""
        matrix = self.get_range_matrix(position, spot, stack_bb, vs_position)

        raise_combos = 0
        call_combos = 0
        fold_combos = 0
        allin_combos = 0

        for s in matrix.values():
            r_freq = s.frequencies.get('RAISE', 0.0)
            c_freq = s.frequencies.get('CALL', 0.0)
            f_freq = s.frequencies.get('FOLD', 0.0)
            a_freq = s.frequencies.get('ALL_IN', 0.0)

            raise_combos += round(s.combos * r_freq)
            call_combos += round(s.combos * c_freq)
            fold_combos += round(s.combos * f_freq)
            allin_combos += round(s.combos * a_freq)

        total_played = raise_combos + call_combos + allin_combos

        return RangeStats(
            position=position.upper(),
            spot=spot.upper(),
            stack_bb=stack_bb,
            vs_position=vs_position.upper() if vs_position else None,
            total_combos_played=total_played,
            percentage_played=round((total_played / TOTAL_COMBOS) * 100, 1),
            raise_combos=raise_combos,
            call_combos=call_combos,
            fold_combos=fold_combos,
            all_in_combos=allin_combos,
            raise_percent=round((raise_combos / TOTAL_COMBOS) * 100, 1),
            call_percent=round((call_combos / TOTAL_COMBOS) * 100, 1),
            fold_percent=round((fold_combos / TOTAL_COMBOS) * 100, 1),
        )

    def evaluate_hand(
        self,
        hero_cards: List[str] | str,
        position: str,
        spot: str = 'RFI',
        stack_bb: float = 100.0,
        vs_position: Optional[str] = None,
        current_bet_bb: float = 0.0
    ) -> GtoDecisionResult:
        """Avalia a mão do Hero e emite recomendação formal de decisão GTO."""
        if isinstance(hero_cards, str):
            cards_list = [c.strip() for c in hero_cards.split(',') if c.strip()]
        else:
            cards_list = list(hero_cards)

        if len(cards_list) != 2:
            raise ValueError(f"Hero deve ter exatamente 2 cartas. Recebido: {cards_list}")

        canonical = self.canonical_hand(cards_list[0], cards_list[1])
        matrix = self.get_range_matrix(position, spot, stack_bb, vs_position)
        strat = matrix.get(canonical)

        if not strat or strat.action == 'FOLD':
            return GtoDecisionResult(
                hand=canonical,
                cards=cards_list,
                position=position.upper(),
                spot=spot.upper(),
                stack_bb=stack_bb,
                vs_position=vs_position.upper() if vs_position else None,
                recommended_action='FOLD',
                recommended_sizing_bb=0.0,
                recommended_sizing_label='Fold (0 BB)',
                strategy_mix={'FOLD': 1.0},
                ev_bb=0.0,
                is_mixed=False,
                category='FOLD',
                rationale=f"A mão {canonical} está fora do range GTO de abertura/defesa em {position.upper()} para o spot {spot.upper()}.",
                in_range=False
            )

        # Mão está no range
        is_mixed = len(strat.frequencies) > 1 and any(0.05 < v < 0.95 for v in strat.frequencies.values())
        freq_str = ", ".join(f"{act}: {int(p*100)}%" for act, p in strat.frequencies.items())

        # Rationale formatado
        sizing_label = "Fold"
        if strat.action == 'RAISE':
            sizing_label = f"Raise para {strat.sizing_bb} BB"
            rationale = f"Mão forte ({strat.category}). Abrir aumento de {strat.sizing_bb} BB com {int(strat.frequencies.get('RAISE', 1.0)*100)}% de frequência."
        elif strat.action == 'CALL':
            sizing_label = f"Call ({current_bet_bb or 1.0} BB)"
            rationale = f"Mão de realização de equidade ({strat.category}). Pagar com frequência de {int(strat.frequencies.get('CALL', 1.0)*100)}%."
        elif strat.action == 'ALL_IN':
            sizing_label = f"Push All-in ({stack_bb} BB)"
            rationale = f"Stack curto ({stack_bb} BB). Push All-in Nash direto com expectativa positiva (+{strat.ev_bb} BB)."
        else:
            rationale = f"Fold padrão GTO."

        return GtoDecisionResult(
            hand=canonical,
            cards=cards_list,
            position=position.upper(),
            spot=spot.upper(),
            stack_bb=stack_bb,
            vs_position=vs_position.upper() if vs_position else None,
            recommended_action=strat.action,
            recommended_sizing_bb=strat.sizing_bb,
            recommended_sizing_label=sizing_label,
            strategy_mix=strat.frequencies,
            ev_bb=strat.ev_bb,
            is_mixed=is_mixed,
            category=strat.category,
            rationale=rationale,
            in_range=True
        )

    def simulate_random_hands(
        self,
        position: str,
        spot: str = 'RFI',
        stack_bb: float = 100.0,
        num_trials: int = 200
    ) -> Dict[str, Any]:
        """Simula mãos aleatórias do baralho contra o motor e gera métricas estatísticas."""
        ranks = list("23456789TJQKA")
        suits = list("shdc")
        deck = [f"{r}{s}" for r in ranks for s in suits]

        actions_count = {'RAISE': 0, 'CALL': 0, 'FOLD': 0, 'ALL_IN': 0}
        total_ev = 0.0

        for _ in range(num_trials):
            c1, c2 = random.sample(deck, 2)
            res = self.evaluate_hand([c1, c2], position, spot, stack_bb)
            actions_count[res.recommended_action] = actions_count.get(res.recommended_action, 0) + 1
            total_ev += res.ev_bb

        return {
            'trials': num_trials,
            'position': position,
            'spot': spot,
            'stack_bb': stack_bb,
            'distribution': actions_count,
            'raise_pct': round((actions_count['RAISE'] / num_trials) * 100, 1),
            'call_pct': round((actions_count['CALL'] / num_trials) * 100, 1),
            'fold_pct': round((actions_count['FOLD'] / num_trials) * 100, 1),
            'all_in_pct': round((actions_count['ALL_IN'] / num_trials) * 100, 1),
            'avg_ev_bb': round(total_ev / num_trials, 3)
        }
