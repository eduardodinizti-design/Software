"""Penalidade de equidade multiway + bloqueio de c-bet blefe (pós-flop).

Em pote multi-way a equity do hero contra VÁRIOS ranges é menor que contra um só,
e a fold equity de um blefe colapsa. Este módulo:
  - aplica um REDUTOR de equity por vilão EXTRA (-12% relativo por vilão além do
    primeiro) em potes multi-way;
  - BLOQUEIA blefes de c-bet quando há MAIS DE 2 oponentes.

PURO: sem captura nem clique; só matemática de ajuste. Usado pelo
`postflop_advisor.py` (camada exploratória; não executa ao vivo).
"""

MULTIWAY_PENALTY_PER_EXTRA = 0.12     # -12% (relativo) de equity por vilão além do 1º
CBET_BLUFF_MAX_OPPONENTS = 2          # acima disso, blefe de c-bet é bloqueado


def extra_villains(opponents):
    """Vilões ALÉM do primeiro (0 em pote HU). Entrada inválida -> 0."""
    try:
        return max(0, int(opponents) - 1)
    except (TypeError, ValueError):
        return 0


def apply_multiway_penalty(equity, opponents, *, per_extra=MULTIWAY_PENALTY_PER_EXTRA):
    """Reduz a equity em `per_extra` (relativo) por vilão extra. HU (1 opp) -> sem
    mudança. None -> None. Resultado em [0, equity]."""
    if equity is None:
        return None
    extra = extra_villains(opponents)
    if extra == 0:
        return equity
    return max(0.0, equity * max(0.0, 1.0 - per_extra * extra))


def penalty_pct(opponents, *, per_extra=MULTIWAY_PENALTY_PER_EXTRA):
    """Percentual total de redução aplicado (0 em HU). Ex.: 2 opp -> 12, 3 -> 24."""
    return round(min(1.0, per_extra * extra_villains(opponents)) * 100)


def cbet_bluff_blocked(opponents, *, max_opponents=CBET_BLUFF_MAX_OPPONENTS):
    """True quando um BLEFE de c-bet deve ser bloqueado (mais de `max_opponents`
    oponentes) — a fold equity colapsa multi-way."""
    try:
        return int(opponents) > int(max_opponents)
    except (TypeError, ValueError):
        return False


def count_opponents(table_state):
    """Nº de oponentes ativos (assentos != hero com mão/ocupação lida) numa leitura,
    ou None quando não dá p/ contar."""
    seats = (table_state or {}).get('seats') or {}
    n = 0
    for key, s in seats.items():
        if key == 'hero' or not isinstance(s, dict):
            continue
        if s.get('in_hand') is True or s.get('occupied') is True or s.get('stack_bb') is not None:
            n += 1
    return n or None
