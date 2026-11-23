"""GROUND TRUTH do decode da Suprema contra showdowns REAIS ([[nvt-suprema-cartas-maior-59]]).

Trava o `suprema_state.decode_card` contra o dump capturado ao vivo: para CADA showdown,
decodifica `game_result.lightcards` (os 5 do jogo vencedor) com o decode VIVO e exige que a
categoria da mão case com `game_result.patterns`. Foi isto que provou o esquema real
(rank=code%16, suit=code//16) e refutou o antigo rank*4+suit (31/31 showdowns). Se alguém
reverter o decode, este teste quebra. Pula se o dump não estiver presente.
"""
import os
from collections import Counter

import pytest

from suprema_state import decode_card
from crack_suprema_cards import iter_events, segment_hands, _as_card_lists

DUMP = os.path.join(os.path.dirname(__file__), "logs", "suprema_raw", "suprema_2026-11-21.jsonl")

_RVAL = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
         'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}


def _category(cards):
    """Categoria de poker de 5 cartas decodificadas ('9s', 'Ah', ...). Nome igual ao patterns
    da Suprema; 'Two pair' cobre o 'Two pairs' deles (só o plural difere)."""
    ranks = sorted((_RVAL[c[0]] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    counts = sorted(Counter(ranks).values(), reverse=True)
    uniq = sorted(set(ranks))
    is_flush = len(set(suits)) == 1 and len(cards) == 5
    is_straight = len(uniq) == 5 and (uniq[-1] - uniq[0] == 4 or set(uniq) == {14, 2, 3, 4, 5})
    if is_straight and is_flush:
        return "Straight flush"
    if counts[0] == 4:
        return "Four of a kind"
    if counts[0] == 3 and counts[1] == 2:
        return "Full house"
    if is_flush:
        return "Flush"
    if is_straight:
        return "Straight"
    if counts[0] == 3:
        return "Three of a kind"
    if counts[0] == 2 and counts[1] == 2:
        return "Two pair"
    if counts[0] == 2:
        return "One pair"
    return "High card"


def _norm(pat):
    return "Two pair" if pat == "Two pairs" else pat


def _showdowns():
    if not os.path.exists(DUMP):
        pytest.skip(f"dump ausente: {DUMP}")
    out = []
    for hand in segment_hands(list(iter_events(DUMP))):
        for m in hand:
            if m.get("event") != "gameover":
                continue
            gr = (m.get("data") or {}).get("game_result") or {}
            pats = gr.get("patterns") or []
            lights = _as_card_lists(gr.get("lightcards"))
            for light, pat in zip(lights, pats):
                if len(light) == 5:
                    out.append((light, pat))
    return out


def test_tem_showdowns_suficientes():
    assert len(_showdowns()) >= 25   # a sessão 21/11 tem 31 jogos de 5 cartas


def test_decode_vivo_bate_todos_os_patterns():
    """CADA mão vencedora decodificada com o decode VIVO tem a categoria do patterns real."""
    falhas = []
    for light, pat in _showdowns():
        cards = [decode_card(c) for c in light]
        assert all(cards), (light, cards)          # nada de '??' num showdown
        cat = _category(cards)
        if cat != _norm(pat):
            falhas.append((light, cards, cat, pat))
    assert not falhas, falhas
