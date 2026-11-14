"""Ajustes pós-flop EXPLORATÓRIOS — 3 conceitos portados do estudo do VisualPilot 2.0.

A camada de conselho (`postflop_advisor`) já cobre força da mão, outs/draws, pot odds,
MDF, SPR, implied odds, penalidade multiway e exploit de HUD. Faltavam três conceitos
de estudo que este módulo adiciona como PRIMITIVAS PURAS e testáveis:

  1) SIZING GEOMÉTRICO multi-street — a fração de pote que, repetida a cada rua
     restante, coloca todo o stack efetivo no pote no river (constrói o pote em `n`
     ruas sem apostas fracionadas que vazam fold equity). `s = ((1+2·SPR)^(1/n)-1)/2`.
  2) SCARE CARD — a carta de turn/river que completa flush/sequência, pareia o board
     ou é overcard. Sinal de perigo para mãos de 1 par (o vilão pode ter melhorado).
  3) POOL-UNDERBLUFF no MDF — no pool da Evolution, linhas passivas que viram agressão
     pesada (ou overbets) são SUB-BLEFADAS; o MDF teórico é descontado (×0.75) para não
     defender largo demais contra um range que quase nunca blefa.

PURO: sem captura, sem clique. NÃO altera `execution_allowed` (segue False) nem a
execução ao vivo. Alimenta o advisor (metadados + caveats) e o auditor de leaks
(`leak_audit.py`). Os pesos são de ESTUDO, conservadores, não saída de solver.
"""

# ---- 1) Sizing geométrico ---------------------------------------------------
GEO_MIN_PCT = 20.0     # piso de size (abaixo disso não vale a pena apostar)
GEO_MAX_PCT = 250.0    # teto de overbet geométrico
_STREET_REMAINING = {'FLOP': 3, 'TURN': 2, 'RIVER': 1}


def remaining_streets(street):
    """Ruas de aposta restantes a partir de `street` (FLOP=3, TURN=2, RIVER=1)."""
    return _STREET_REMAINING.get(str(street).upper())


def geometric_bet_pct(spr, streets):
    """Fração do pote (em %) que, repetida por `streets` ruas, compromete o stack no
    river. `s = ((1+2·SPR)^(1/n)-1)/2`. Limitada a [GEO_MIN_PCT, GEO_MAX_PCT].

    None quando SPR<=0 ou streets<=0 (sem pote/stack ou sem ruas a jogar)."""
    if not isinstance(spr, (int, float)) or not isinstance(streets, int):
        return None
    if spr <= 0 or streets <= 0:
        return None
    s = ((1 + 2 * spr) ** (1.0 / streets) - 1) / 2.0
    return round(min(max(s * 100.0, GEO_MIN_PCT), GEO_MAX_PCT), 1)


def geometric_street_plan(spr, street, pot_bb, stack_bb):
    """Plano de aposta rua-a-rua com size geométrico constante. Lista de dicts
    {street, pot_before, bet_pct, bet_bb}. Cada aposta cresce o pote em 2×bet (o vilão
    paga) e é limitada pelo stack atrás. Vazio quando faltam dados ou sem ruas."""
    n = remaining_streets(street)
    if n is None or not isinstance(pot_bb, (int, float)) or pot_bb <= 0:
        return []
    if not isinstance(stack_bb, (int, float)) or stack_bb <= 0:
        return []
    pct = geometric_bet_pct(spr, n)
    if pct is None:
        return []
    names = ['FLOP', 'TURN', 'RIVER']
    start = names.index(str(street).upper())
    plan = []
    pot, stack = float(pot_bb), float(stack_bb)
    for st in names[start:]:
        bet = min(stack, round(pot * pct / 100.0, 1))
        eff_pct = round(bet / pot * 100.0, 1) if pot > 0 else 0.0
        plan.append(dict(street=st, pot_before=round(pot, 1),
                         bet_pct=eff_pct if bet > 0 else 0.0, bet_bb=round(bet, 1)))
        pot += bet * 2
        stack = max(0.0, stack - bet)
        if stack <= 0:
            break
    return plan


# ---- 2) Scare card ----------------------------------------------------------
# Penalidade de equidade de ESTUDO por tipo de scare, para o AUDITOR graduar mãos de
# valor fino (1 par) quando a carta completa um draw. NÃO é aplicada à equity de Monte
# Carlo do advisor (lá o board já entra no cálculo -> dupla contagem). Referência VP2.0.
SCARE_PENALTY = dict(flush_completes=11, straight_completes=10, board_pairs=8, overcard=9)
_DANGER_KINDS = ('flush_possible', 'straight_on_board', 'board_paired')


def _board_ranks(board):
    rank = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
            '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}
    return [rank[str(c)[0].upper()] for c in board]


def scare_present(board_class, street):
    """Sinal de perigo (state-based) a partir da textura do board no TURN/RIVER:
    flush possível, sequência no board ou board pareado. No flop retorna ausente
    (ainda vêm cartas). Dict {present, kinds}."""
    if str(street).upper() not in ('TURN', 'RIVER') or not isinstance(board_class, dict):
        return dict(present=False, kinds=[])
    kinds = []
    if board_class.get('flush_possible'):
        kinds.append('flush_possible')
    if board_class.get('straight_on_board'):
        kinds.append('straight_on_board')
    if board_class.get('paired'):
        kinds.append('board_paired')
    return dict(present=bool(kinds), kinds=kinds)


def scare_from_transition(prev_board, new_board):
    """O que a carta recém-virada (turn/river) fez ao board, comparando o board ANTES e
    DEPOIS. Usa `classify_board` por dentro. Retorna uma das chaves de `SCARE_PENALTY`
    ('flush_completes'/'straight_completes'/'board_pairs'/'overcard') ou 'brick'.

    Prioridade: completar flush > completar sequência > parear o board > overcard."""
    from postflop_eval import classify_board
    try:
        before = classify_board(prev_board) if prev_board and len(prev_board) >= 3 else None
        after = classify_board(new_board)
    except (ValueError, KeyError, TypeError):
        return 'brick'
    if after.get('flush_possible') and not (before and before.get('flush_possible')):
        return 'flush_completes'
    if after.get('straight_on_board') and not (before and before.get('straight_on_board')):
        return 'straight_completes'
    if after.get('paired') and not (before and before.get('paired')):
        return 'board_pairs'
    if before:
        prev_max = max(_board_ranks(prev_board))
        new_ranks = _board_ranks(new_board)
        if new_ranks and max(new_ranks) > prev_max:
            return 'overcard'
    return 'brick'


# ---- 3) Pool-underbluff no MDF ----------------------------------------------
POOL_UNDERBLUFF_FACTOR = 0.75    # desconto do MDF teórico no pool que sub-blefa


def pool_adjusted_mdf(mdf, *, passive_turned_aggressive=False, overbet=False):
    """MDF ajustado ao pool: desconta ×0.75 quando o vilão passou de passivo a
    agressivo na rua (linha que o field sub-blefa) OU fez overbet. Senão, MDF intacto.
    None passthrough."""
    if mdf is None:
        return None
    if passive_turned_aggressive or overbet:
        return round(mdf * POOL_UNDERBLUFF_FACTOR, 4)
    return round(mdf, 4)
