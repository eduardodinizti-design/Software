"""Decodificador de CARTAS do PPPoker (int do protobuf -> 'Qh').

Encoding confirmado ao vivo (17/11, HandCardRSP/RoundStartBRC via IL2CPP):
    card = naipe * 256 + rank
    naipe = card >> 8   (1..4)
    rank  = card & 0xFF (2..14; 11=J 12=Q 13=K 14=A)
Ex.: 779 = 3*256+11 = rank J, naipe 3 ; 1038 = 4*256+14 = rank A, naipe 4.

RANK está CONFIRMADO. O MAPA DE NAIPE (1..4) foi CONFIRMADO ao vivo em 20/11/2026
comparando o board do protobuf com a tela (deck de 4 cores do PPPoker: ♠ preto, ♥
vermelho, ♦ azul, ♣ verde). Evidência (SMALL PKO, research/ppp_il2cpp/suitsample_*.png):
    idx 1 = ♦ (3♦ azul) | idx 2 = ♣ (9♣ verde) | idx 3 = ♥ (Q♥ vermelho) | idx 4 = ♠ (A♠ preto)
"""
from __future__ import annotations

RANKS = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9',
         10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}

# CONFIRMADO ao vivo 20/11/2026 (board protobuf x tela; ver docstring/evidência).
SUIT_MAP = {1: 'd', 2: 'c', 3: 'h', 4: 's'}
_SUIT_CONFIRMED = True


def suit_confirmed() -> bool:
    return _SUIT_CONFIRMED


def set_suit_map(mapping, confirmed=True):
    """Fixa o mapa de naipe depois de confirmar ao vivo (ex.: {1:'c',2:'d',3:'h',4:'s'})."""
    global SUIT_MAP, _SUIT_CONFIRMED
    SUIT_MAP = dict(mapping)
    _SUIT_CONFIRMED = bool(confirmed)


def rank_of(card: int) -> int:
    return int(card) & 0xFF


def suit_of(card: int) -> int:
    return int(card) >> 8


def is_valid(card) -> bool:
    try:
        c = int(card)
    except (TypeError, ValueError):
        return False
    return c > 0 and rank_of(c) in RANKS and suit_of(c) in SUIT_MAP


def decode_card(card) -> str | None:
    """int -> 'Qh'. Devolve None se inválido/vazio (ex.: 0 = sem carta)."""
    if not is_valid(card):
        return None
    c = int(card)
    return RANKS[rank_of(c)] + SUIT_MAP[suit_of(c)]


def decode_cards(cards) -> list[str]:
    """Lista de ints -> lista de 'Qh', pulando os inválidos/0."""
    out = []
    for c in (cards or []):
        s = decode_card(c)
        if s:
            out.append(s)
    return out


def encode_card(text: str) -> int:
    """'Qh' -> int (inverso; útil p/ testes e p/ confirmar o mapa de naipe)."""
    text = text.strip()
    rank_c, suit_c = text[:-1], text[-1]
    rank = next(k for k, v in RANKS.items() if v == rank_c.upper())
    suit = next(k for k, v in SUIT_MAP.items() if v == suit_c.lower())
    return suit * 256 + rank
