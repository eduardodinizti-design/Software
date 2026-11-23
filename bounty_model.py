"""Modelo de BOUNTY PKO compartilhado (Suprema + PPPoker). Platform-neutral e PURO.

O bounty é moeda de PRÊMIO/buy-in, NÃO fichas de stack. Pra usar numa decisão de poker a cabeça
precisa virar EQUIVALENTE em fichas de stack, via o STACK INICIAL: num PKO 50/50 a metade-prêmio
((1-hf)·buyin) "compra" 1 stack inicial, então uma cabeça FRESCA (hf·buyin) vale
starting_stack·hf/(1-hf) fichas de stack; em BB = isso / bb_chips.

É a BASE (cabeça fresca em BB) que o call-off do advisor escala pelo bounty do vilão
(scale_bounty_bb: base × bounty_vilão/bounty_base). Ver [[nvt-suprema-pko-bounty]].
"""
from __future__ import annotations


def base_bb_from_structure(starting_stack, bb_chips, head_fraction=0.5):
    """Cabeça FRESCA (0 KO) em BB-equivalente = starting_stack·hf/(1-hf) / bb_chips.
    hf: 0.5 PKO (default), 0.75 super-PKO, 0.5 KO. None se faltar dado (nunca estima)."""
    ss = starting_stack if isinstance(starting_stack, (int, float)) else None
    bb = bb_chips if isinstance(bb_chips, (int, float)) else None
    hf = head_fraction if isinstance(head_fraction, (int, float)) else None
    if not (ss and ss > 0) or not (bb and bb > 0) or not (hf and 0 < hf < 1):
        return None
    return round(ss * hf / (1.0 - hf) / bb, 4)
