"""Testes do decodificador de cartas do PPPoker. RANK confirmado ao vivo; naipe = palpite."""
import ppp_cards
from ppp_cards import (decode_card, decode_cards, rank_of, suit_of, is_valid,
                       encode_card, set_suit_map, RANKS)


def test_rank_arithmetic_confirmed():
    # valores REAIS capturados ao vivo (HandCardRSP): 779 e 1038
    assert rank_of(779) == 11 and suit_of(779) == 3     # J, naipe 3
    assert rank_of(1038) == 14 and suit_of(1038) == 4   # A, naipe 4
    assert decode_card(779)[0] == 'J'
    assert decode_card(1038)[0] == 'A'


def test_all_ranks():
    for r, ch in RANKS.items():
        card = 1 * 256 + r
        assert decode_card(card)[0] == ch


def test_zero_and_invalid_are_none():
    assert decode_card(0) is None       # 0 = sem carta
    assert decode_card(None) is None
    assert decode_card(1) is None       # rank 1 inválido
    assert is_valid(0) is False


def test_decode_cards_skips_empty():
    # mão do herói com card3..6 = 0 (só 2 cartas) -> só 2 saem
    assert len(decode_cards([779, 1038, 0, 0, 0, 0])) == 2


def test_roundtrip_encode_decode():
    for card in (779, 1038, 256 + 2, 2 * 256 + 10):
        assert encode_card(decode_card(card)) == card


def test_set_suit_map_live_correction():
    # simula confirmar ao vivo um mapa diferente
    try:
        set_suit_map({1: 'c', 2: 'd', 3: 'h', 4: 's'}, confirmed=True)
        assert ppp_cards.suit_confirmed() is True
        assert decode_card(779) == 'Jh'    # naipe 3 -> h nesse mapa
        assert decode_card(1038) == 'As'   # naipe 4 -> s
    finally:
        set_suit_map({1: 's', 2: 'h', 3: 'd', 4: 'c'}, confirmed=False)  # restaura default
