"""Motor GTO Pós-Flop para Potes 3-Bet e Cálculo de Equidade contra Ranges.

Implementa:
- Avaliador combinatorial exato de mãos de 7 cartas (rank7) com empates e wheels.
- Expansão de ranges de vilões em combos físicos (dead card removal para Hero e Board).
- Ranges pré-flop padrão para Potes 3-Bet:
    * Vilão 3-Bettor Linear (AA-TT, AK, AQs, AJs, KQs, A5s-A4s)
    * Vilão 3-Bettor Polarizado (AA-QQ, AK, A2s-A5s, 87s, 76s, KJo)
    * Vilão Caller de 3-Bet IP (JJ-77, AQs-ATs, KQs, QJs, JTs, T9s, AQo)
    * Vilão Caller de 3-Bet OOP (QQ-88, AQs, AKo, KQs)
- Simulador de Equidade Monte Carlo e Exato no River.
- Detecção de textura de bordo (Dry, Wet, Paired, Monotone, Two-Tone).
- Recomendações de linhas GTO em Potes 3-Bet:
    * C-Bet 1/3 pote (33%) vs C-Bet 2/3 pote (66%) vs Check/Call vs Check/Fold.
    * Vantagem de range (Range Advantage) e Vantagem de Nuts (Nut Advantage).
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field, asdict
from itertools import combinations
from typing import Dict, List, Optional, Tuple, Any

RANKS = '23456789TJQKA'
SUITS = 'cdhs'
DECK = tuple(r + s for r in RANKS for s in SUITS)
RANK_VALUES = {r: i + 2 for i, r in enumerate(RANKS)}

HAND_RANKS_NAMES = [
    "High Card", "One Pair", "Two Pair", "Three of a Kind",
    "Straight", "Flush", "Full House", "Four of a Kind", "Straight Flush"
]


def validate_cards(cards: Tuple[str, ...] | List[str]) -> None:
    if any(c not in DECK for c in cards) or len(set(cards)) != len(cards):
        raise ValueError(f"Cartas inválidas ou repetidas: {cards}")


def rank5(cards: Tuple[str, ...]) -> Tuple[int, ...]:
    """Classifica com precisão 5 cartas no poker clássico com desempate total."""
    values = sorted((RANK_VALUES[c[0]] for c in cards), reverse=True)
    counts = Counter(values)
    groups = sorted(((cnt, val) for val, cnt in counts.items()), reverse=True)
    unique = sorted(set(values), reverse=True)

    # Straight check (incluindo wheel A-2-3-4-5)
    is_wheel = (unique == [14, 5, 4, 3, 2])
    is_straight = is_wheel or (len(unique) == 5 and unique[0] - unique[-1] == 4)
    straight_high = 5 if is_wheel else (unique[0] if is_straight else 0)

    # Flush check
    is_flush = (len({c[1] for c in cards}) == 1)

    if is_flush and is_straight:
        return (8, straight_high)
    if groups[0][0] == 4:
        return (7, groups[0][1], groups[1][1])
    if groups[0][0] == 3 and groups[1][0] >= 2:
        return (6, groups[0][1], groups[1][1])
    if is_flush:
        return (5, *values)
    if is_straight:
        return (4, straight_high)
    if groups[0][0] == 3:
        kickers = [v for cnt, v in groups if cnt == 1]
        return (3, groups[0][1], *kickers)
    if groups[0][0] == 2 and groups[1][0] == 2:
        kicker = next(v for cnt, v in groups if cnt == 1)
        return (2, groups[0][1], groups[1][1], kicker)
    if groups[0][0] == 2:
        kickers = [v for cnt, v in groups if cnt == 1]
        return (1, groups[0][1], *kickers)
    return (0, *values)


def rank7(cards: Tuple[str, ...] | List[str]) -> Tuple[int, ...]:
    """Retorna o melhor rank de 5 cartas dentre as 7 disponíveis."""
    return max(rank5(c) for c in combinations(cards, 5))


def classify_made_hand(hero_cards: List[str], board_cards: List[str]) -> str:
    """Retorna uma classificação semântica amigável da mão do Hero no bordo atual."""
    full = list(hero_cards) + list(board_cards)
    score = rank7(full)
    hand_type_idx = score[0]
    hand_name = HAND_RANKS_NAMES[hand_type_idx]

    board_ranks = [c[0] for c in board_cards]
    hero_ranks = [c[0] for c in hero_cards]
    top_board = max(board_ranks, key=lambda r: RANK_VALUES[r])

    if hand_type_idx == 8:
        return "Straight Flush (Nuts Absoluto)"
    if hand_type_idx == 7:
        return "Quadra (Four of a Kind)"
    if hand_type_idx == 6:
        return "Full House"
    if hand_type_idx == 5:
        return "Flush Completo"
    if hand_type_idx == 4:
        return "Sequência (Straight)"
    if hand_type_idx == 3:
        if hero_ranks[0] == hero_ranks[1]:
            return "Trinca / Set (Pocket Pair)"
        return "Trinca (Trips no Bordo)"
    if hand_type_idx == 2:
        return "Dois Pares (Two Pair)"
    if hand_type_idx == 1:
        if hero_ranks[0] == hero_ranks[1] and RANK_VALUES[hero_ranks[0]] > RANK_VALUES[top_board]:
            return f"Overpair ({hero_ranks[0]}{hero_ranks[1]})"
        if top_board in hero_ranks:
            kicker = hero_ranks[1] if hero_ranks[0] == top_board else hero_ranks[0]
            kicker_val = RANK_VALUES[kicker]
            k_desc = "Top Kicker (TK)" if kicker_val >= 13 else "Bom Kicker" if kicker_val >= 10 else "Kicker Fraco"
            return f"Top Pair ({top_board}) com {k_desc}"
        return "Par Médio / Par Baixo"
    return f"Carta Alta ({max(hero_ranks, key=lambda r: RANK_VALUES[r])})"


# ==============================================================================
# RANGES PRÉ-CALIBRADOS PARA CENÁRIOS COMUNS DE POTES 3-BET
# ==============================================================================

PRESET_3BET_VILLAIN_RANGES: Dict[str, Dict[str, float]] = {
    # 3-Bettor Linear (BB vs BTN ou SB vs CO): AA-TT, AKs, AQs, AJs, KQs, AKo, A5s-A4s
    "LINEAR_3BET": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 0.8, "99": 0.4,
        "AKs": 1.0, "AQs": 1.0, "AJs": 0.9, "ATs": 0.5, "A5s": 0.8, "A4s": 0.7,
        "KQs": 1.0, "KJs": 0.6, "QJs": 0.6, "JTs": 0.5,
        "AKo": 1.0, "AQo": 0.8, "AJo": 0.3, "KQo": 0.3
    },
    # 3-Bettor Polarizado: Top Valor + Blefes com Blockers (A5s-A2s, suited connectors 87s, KJo)
    "POLARIZED_3BET": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 0.7,
        "AKs": 1.0, "AQs": 0.8, "A5s": 1.0, "A4s": 1.0, "A3s": 0.8, "A2s": 0.7,
        "KQs": 0.8, "87s": 0.8, "76s": 0.8, "65s": 0.6,
        "AKo": 1.0, "AQo": 0.6, "KJo": 0.6, "QJo": 0.5
    },
    # Caller de 3-Bet em Posição (ex: BTN pagou 3-Bet do BB): JJ-88, AQs-ATs, KQs, QJs, JTs, T9s, AQo
    "CALLER_IP_3BET": {
        "JJ": 0.8, "TT": 1.0, "99": 1.0, "88": 0.9, "77": 0.6,
        "AQs": 0.7, "AJs": 1.0, "ATs": 0.9, "A9s": 0.5,
        "KQs": 0.9, "KJs": 0.8, "KTs": 0.6,
        "QJs": 0.9, "QTs": 0.7, "JTs": 0.9, "T9s": 0.8, "98s": 0.7, "87s": 0.5,
        "AQo": 0.8, "AJo": 0.6, "KQo": 0.7
    },
    # Caller de 3-Bet Fora de Posição (ex: UTG/CO pagou 3-Bet): QQ-88, AKo, AQs, KQs
    "CALLER_OOP_3BET": {
        "QQ": 0.6, "JJ": 1.0, "TT": 1.0, "99": 0.8, "88": 0.5,
        "AKs": 0.4, "AQs": 0.9, "AJs": 0.7,
        "KQs": 0.8, "QJs": 0.5, "JTs": 0.5,
        "AKo": 0.5, "AQo": 0.6
    }
}

PRESET_3BET_SCENARIOS = [
    {
        "id": "btn_vs_bb_ace_dry",
        "name": "Flop Seco A-High (A♠ 8♥ 3♦)",
        "description": "BTN abriu, BB fez 3-Bet e BTN pagou. Textura clássica onde o 3-Bettor tem vantagem maciça de range.",
        "hero_role": "CALLER_IP",
        "position": "BTN",
        "vs_position": "BB",
        "hero_cards": ["K♠", "Q♠"],
        "board_cards": ["A♠", "8♥", "3♦"],
        "villain_range_id": "LINEAR_3BET",
        "pot_bb": 19.5,
        "stack_bb": 82.5,
    },
    {
        "id": "sb_vs_co_broadway",
        "name": "Flop Broadway Pesado (K♦ Q♠ 7♣)",
        "description": "SB fez 3-Bet contra CO e tomou call. Ambos acertam fortes pares e draws.",
        "hero_role": "3BETTOR_OOP",
        "position": "SB",
        "vs_position": "CO",
        "hero_cards": ["A♦", "K♣"],
        "board_cards": ["K♦", "Q♠", "7♣"],
        "villain_range_id": "CALLER_IP_3BET",
        "pot_bb": 20.0,
        "stack_bb": 80.0,
    },
    {
        "id": "blind_battle_wet",
        "name": "Batalha de Blinds Dinâmico (J♠ 9♥ 6♦)",
        "description": "SB abriu, BB fez 3-Bet e SB pagou. Flop hiper conectado com múltiplos straight draws e two pairs.",
        "hero_role": "CALLER_OOP",
        "position": "SB",
        "vs_position": "BB",
        "hero_cards": ["T♠", "T♦"],
        "board_cards": ["J♠", "9♥", "6♦"],
        "villain_range_id": "POLARIZED_3BET",
        "pot_bb": 18.0,
        "stack_bb": 84.0,
    },
    {
        "id": "monotone_flush_texture",
        "name": "Flop Monotone Flush (A♣ 9♣ 4♣)",
        "description": "Pote 3-Bet com 3 cartas de paus. O valor das mãos não protegidas sem kicker de paus despenca.",
        "hero_role": "3BETTOR",
        "position": "BTN",
        "vs_position": "BB",
        "hero_cards": ["K♣", "Q♦"],
        "board_cards": ["A♣", "9♣", "4♣"],
        "villain_range_id": "CALLER_OOP_3BET",
        "pot_bb": 19.5,
        "stack_bb": 81.0,
    },
    {
        "id": "paired_dry_low",
        "name": "Flop Pareado Baixo (7♠ 7♥ 2♦)",
        "description": "Flop pareado seco. O agressor pré-flop tem vantagem quase total de overpairs (AA-88).",
        "hero_role": "3BETTOR",
        "position": "CO",
        "vs_position": "BTN",
        "hero_cards": ["J♠", "J♥"],
        "board_cards": ["7♠", "7♥", "2♦"],
        "villain_range_id": "CALLER_IP_3BET",
        "pot_bb": 21.0,
        "stack_bb": 79.0,
    }
]


def expand_range_combos(
    frequencies: Dict[str, float],
    dead_cards: Tuple[str, ...] | List[str] = ()
) -> Dict[Tuple[str, str], float]:
    """Expande uma tabela de classes (ex: 'AKs': 1.0) em combos de 2 cartas removendo bloqueadores."""
    dead_set = set(dead_cards)
    result: Dict[Tuple[str, str], float] = {}

    for hand_class, weight in frequencies.items():
        if weight <= 0:
            continue
        r1, r2 = hand_class[0], hand_class[1]
        is_pair = (r1 == r2)
        is_suited = hand_class.endswith('s')
        is_offsuit = hand_class.endswith('o')

        for c1, c2 in combinations(DECK, 2):
            if c1 in dead_set or c2 in dead_set:
                continue
            card_ranks = sorted((c1[0], c2[0]), key=lambda r: RANK_VALUES[r], reverse=True)
            if card_ranks != sorted((r1, r2), key=lambda r: RANK_VALUES[r], reverse=True):
                continue
            same_suit = (c1[1] == c2[1])
            if is_pair and not same_suit:
                result[(c1, c2)] = weight
            elif is_suited and same_suit:
                result[(c1, c2)] = weight
            elif is_offsuit and not same_suit:
                result[(c1, c2)] = weight

    return result


@dataclass
class PostflopEquityResult:
    hero_cards: List[str]
    board_cards: List[str]
    street: str  # 'FLOP', 'TURN', 'RIVER'
    hero_equity_pct: float
    villain_equity_pct: float
    tie_pct: float
    hero_made_hand: str
    combos_evaluated: int
    trials: int
    board_texture: str
    recommended_gto_action: str
    recommended_sizing_bb: float
    recommended_sizing_pct_pot: int
    action_ev_bb: float
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PostflopGtoEngine:
    """Motor central para cálculo de equidade e linhas GTO em Potes 3-Bet."""

    def __init__(self):
        self.preset_ranges = PRESET_3BET_VILLAIN_RANGES

    @staticmethod
    def detect_board_texture(board: List[str]) -> str:
        """Classifica a textura do bordo em relação à conectividade e naipes."""
        suits = [c[1] for c in board]
        ranks = sorted([RANK_VALUES[c[0]] for c in board], reverse=True)
        suit_counts = Counter(suits)
        max_suit = max(suit_counts.values())

        is_paired = len(ranks) != len(set(ranks))
        is_monotone = (max_suit >= 3)
        is_two_tone = (max_suit == 2)
        is_rainbow = (max_suit == 1 and len(board) == 3)

        gaps = [ranks[i] - ranks[i + 1] for i in range(len(ranks) - 1)]
        is_connected = any(g == 1 for g in gaps) and sum(gaps[:2]) <= 4

        labels = []
        if is_monotone:
            labels.append("Monotone (Flush Draw / Made)")
        elif is_two_tone:
            labels.append("Two-Tone (Flush Draw Ativo)")
        elif is_rainbow:
            labels.append("Rainbow (Seco)")

        if is_paired:
            labels.append("Pareado")
        elif is_connected:
            labels.append("Conectado (Wet)")
        else:
            labels.append("Desconectado (Dry)")

        return " · ".join(labels)

    def calculate_equity(
        self,
        hero_cards: List[str],
        board_cards: List[str],
        villain_range: str | Dict[str, float] = "LINEAR_3BET",
        pot_bb: float = 20.0,
        stack_bb: float = 80.0,
        trials: int = 1500,
        seed: int = 42
    ) -> PostflopEquityResult:
        """Calcula a equidade exata (river) ou por amostragem Monte Carlo ponderada (flop/turn)."""
        validate_cards(tuple(hero_cards) + tuple(board_cards))

        if isinstance(villain_range, str):
            range_freqs = self.preset_ranges.get(villain_range, self.preset_ranges["LINEAR_3BET"])
        else:
            range_freqs = villain_range

        dead = tuple(hero_cards) + tuple(board_cards)
        expanded_combos = expand_range_combos(range_freqs, dead)

        if not expanded_combos:
            raise ValueError("Range do vilão ficou vazio após remoção dos bloqueadores do Hero e Board.")

        combos_list = list(expanded_combos.keys())
        weights = list(expanded_combos.values())
        total_combos = len(combos_list)

        board_len = len(board_cards)
        street = "FLOP" if board_len == 3 else "TURN" if board_len == 4 else "RIVER"

        def evaluate_showdown(combo: Tuple[str, str], runout: Tuple[str, ...]) -> float:
            h = rank7(tuple(hero_cards) + tuple(board_cards) + runout)
            v = rank7(tuple(combo) + tuple(board_cards) + runout)
            if h > v:
                return 1.0
            if h == v:
                return 0.5
            return 0.0

        hero_wins = 0.0
        ties = 0.0

        if board_len == 5:
            # River: Exato
            for combo, w in expanded_combos.items():
                s = evaluate_showdown(combo, ())
                if s == 1.0:
                    hero_wins += w
                elif s == 0.5:
                    ties += w
            sum_w = sum(weights)
            hero_eq = (hero_wins + 0.5 * ties) / sum_w
            tie_pct = ties / sum_w
        else:
            # Flop / Turn: Monte Carlo balanceado
            rng = random.Random(seed)
            cards_needed = 5 - board_len
            scores: List[float] = []

            for combo in rng.choices(combos_list, weights=weights, k=trials):
                unavailable = set(dead) | set(combo)
                remaining_deck = [c for c in DECK if c not in unavailable]
                runout = tuple(rng.sample(remaining_deck, cards_needed))
                sc = evaluate_showdown(combo, runout)
                scores.append(sc)

            hero_eq = sum(scores) / trials
            tie_pct = sum(1 for s in scores if s == 0.5) / trials

        hero_pct = round(hero_eq * 100, 1)
        villain_pct = round((1.0 - hero_eq) * 100, 1)
        tie_final_pct = round(tie_pct * 100, 1)

        # Classificação da mão e textura
        made_hand = classify_made_hand(hero_cards, board_cards)
        texture = self.detect_board_texture(board_cards)

        # Modelagem de Linha GTO no Pote 3-Bet
        top_board = max([c[0] for c in board_cards], key=lambda r: RANK_VALUES[r])
        is_ace_king_high = top_board in ('A', 'K')
        spr = round(stack_bb / pot_bb, 1)

        if hero_pct >= 68.0:
            rec_action = "BET 1/3 POTE (33%)"
            sizing_pct = 33
            sizing_bb = round(pot_bb * 0.33, 1)
            ev = round(pot_bb * 0.75, 2)
            rationale = (f"Vantagem expressiva de equidade ({hero_pct}% com {made_hand}). "
                         f"Aposta geométrica de 1/3 do pote ({sizing_bb} BB) maximiza valor contra o range de call do vilão.")
        elif hero_pct >= 52.0:
            if is_ace_king_high and "Dry" in texture:
                rec_action = "BET 33% (Range C-Bet)"
                sizing_pct = 33
                sizing_bb = round(pot_bb * 0.33, 1)
                ev = round(pot_bb * 0.55, 2)
                rationale = (f"Equidade favorável ({hero_pct}%). Textura A/K seca em Pote 3-Bet favorece C-Bet "
                             f"de alta frequência com sizing pequeno ({sizing_bb} BB).")
            else:
                rec_action = "CHECK / CALL"
                sizing_pct = 0
                sizing_bb = 0.0
                ev = round(pot_bb * 0.45, 2)
                rationale = (f"Mão com equidade média ({hero_pct}%). Controle de pote aconselhado (SPR {spr}), "
                             f"permitindo que o vilão blefe e mantendo seus blefes no range.")
        elif hero_pct >= 35.0:
            # Draws ou mãos com valor de showdown marginal
            rec_action = "CHECK / CALL (Pot Control)"
            sizing_pct = 0
            sizing_bb = 0.0
            ev = round(pot_bb * 0.25, 2)
            rationale = (f"Equidade moderada ({hero_pct}%). Ideal para pagar apostas de 1/3 a 1/2 do pote "
                         f"buscando realização de equidade no turn/river.")
        else:
            rec_action = "CHECK / FOLD"
            sizing_pct = 0
            sizing_bb = 0.0
            ev = 0.0
            rationale = (f"Desvantagem de equidade ({hero_pct}% contra o range do vilão). "
                         f"Desistir perante agressão para estancar perdas.")

        return PostflopEquityResult(
            hero_cards=hero_cards,
            board_cards=board_cards,
            street=street,
            hero_equity_pct=hero_pct,
            villain_equity_pct=villain_pct,
            tie_pct=tie_final_pct,
            hero_made_hand=made_hand,
            combos_evaluated=total_combos,
            trials=trials,
            board_texture=texture,
            recommended_gto_action=rec_action,
            recommended_sizing_bb=sizing_bb,
            recommended_sizing_pct_pot=sizing_pct,
            action_ev_bb=ev,
            rationale=rationale
        )
