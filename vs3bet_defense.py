"""DEFESA CONTRA 3-BET pré-flop (MTT) — camada HEURÍSTICA de AJUSTE/ESTUDO (advisory).

Codifica a aula de vídeo (curso Reg-Life, transcrição 'Teoria/2026-11-22 21-56-14.txt').
É uma CAMADA DE AJUSTE sobre as ranges pré-flop (que são a FONTE DA VERDADE —
[[nvt-ranges-fonte-da-verdade]]): NÃO substitui o pack validado, NÃO arma, NÃO clica,
NÃO decide sozinho. validated=False -> puro gate de estudo. O chamador usa como
leitura/segunda opinião ao lado do `spot='vs_3bet'` do preflop_advisor.

As TRÊS REGRAS DE OURO da aula (linhas 66/77 do txt):
  1) SIZE: quanto MAIOR o 3bet enfrentado, MAIS fold. As piores mãos do range de flat
     (a "borda") caem primeiro. Ex.: K9s defende vs 3.5x mas folda vs 8bb (~4x); A8s/A9s/
     ATs a borda folda quando a size sobe (linhas 196-216).
  2) LINEAR vs POLARIZADO (composição do range de 3bet do VILÃO):
     - vs LINEAR (3bet forte/estreito, posições iniciais): defende APERTADO. Offsuit
       broadways (KQo, KJo, AJo, QJo) e suited fracas dominadas (K9s, Q9s, QTs, J9s, A8s-)
       FOLDAM — dominadas até pela parte fraca do range linear (linhas 11-47).
     - vs POLARIZADO (blinds / BTN cold-3bet, com parte polar MUITO fraca): defende LARGO.
       T9s, QJo, QTo, JTo, ATo, A9o, K4s, K5s passam a FLAT porque dominam a parte polar
       ruim (linhas 26-64, 253-262).
  3) POSIÇÃO: IP = defende MAIS largo (realiza melhor a equidade). OOP vs LINEAR = pior
     caso (linhas 48-71).

FLAT privilegia SUITED (flopabilidade) e PARES (não foldam vs 3bet; nut potential,
especialmente DEEP STACK — linhas 72-75, 274-293).

4-BET (linhas 81-117): VALOR (QQ+, AK) + bluffs COMPLEMENTARES que negam equidade
(ATs/KTs vs linear; A6s/A7s/ATo/AQo margens vs polar/deep).

4-BET JAM / all-in (linhas 118-371): existe MAIS em stack CURTO (<50bb, ainda mais <40bb),
OOP (compensa perder o flat), POSIÇÕES FINAIS, e vs quem dá 3bet-fold de mãos piores.
PARES 22-TT são ótimo jam vs 3bet POLARIZADO das blinds (fold equity). TG-vs-TG tem POUCO
jam (vilão paga range curto); CO-vs-BTN tem mais.

NOTA: tudo aqui é HEURÍSTICA por categoria de mão, a validar contra o pack e ao vivo.
Hands mistas (flat/4bet) recebem a ação PRIMÁRIA da aula p/ o spot.
"""

VALIDATED = False   # LEI: camada de estudo. NUNCA arma/clica/decide sozinho.

# As três regras de ouro, em texto, p/ exibição e teste.
GOLDEN_RULES = (
    "SIZE: maior 3bet enfrentado => mais fold (a borda do range de flat cai primeiro).",
    "LINEAR vs POLAR: vs linear defende apertado (offsuit broadways e suited fracas foldam, "
    "dominadas); vs polar defende largo (dominam a parte polar muito fraca).",
    "POSICAO: IP defende mais largo; OOP vs linear e o pior caso.",
)

# Ordem de ação PÓS-FLOP (cedo -> tarde). Mais tarde = mais IP.
_POSTFLOP_ORDER = {'SB': 0, 'BB': 1, 'UTG': 2, 'UTG1': 3, 'UTG2': 4,
                   'LJ': 5, 'HJ': 6, 'CO': 7, 'BTN': 8}
_LATE = frozenset({'CO', 'BTN', 'SB'})       # posições "finais" (dinâmica de jam)
_BLINDS = frozenset({'SB', 'BB'})

BIG_SIZE_X = 4.0        # >= 4x o open = size GRANDE que derruba a borda do flat (regra 1)
SHORT_BB = 50           # < 50bb = curto (começa a haver 4bet-jam)
VERY_SHORT_BB = 40      # < 40bb = muito curto (jam forte)
DEEP_BB = 80            # >= 80bb = deep (pares/suited de nut potential, flat largo)

_RANKVAL = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10, '9': 9, '8': 8, '7': 7,
            '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}


def _parse_hand(hand):
    """'AKs'/'T9o'/'55' -> {hi,lo,suited,pair,gap} ou None (notação de 13x13, 'T'=10)."""
    if not isinstance(hand, str) or len(hand) < 2:
        return None
    r1, r2 = _RANKVAL.get(hand[0].upper()), _RANKVAL.get(hand[1].upper())
    if r1 is None or r2 is None:
        return None
    hi, lo = max(r1, r2), min(r1, r2)
    pair = (r1 == r2)
    suited = (not pair) and hand[-1].lower() == 's'
    return dict(hi=hi, lo=lo, suited=suited, pair=pair, gap=hi - lo)


def is_ip(hero_pos, villain_pos):
    """Hero está EM POSIÇÃO pós-flop vs o vilão? (age depois). Empate/posição desconhecida
    -> OOP (conservador). Usado p/ a regra 3 quando o chamador não passa is_ip."""
    a = _POSTFLOP_ORDER.get(hero_pos)
    b = _POSTFLOP_ORDER.get(villain_pos)
    if a is None or b is None:
        return False
    return a > b


def _is_premium(h):
    """Valor forte de 4bet/commit: QQ, KK, AA, AK (s/o)."""
    if h['pair'] and h['lo'] >= 12:
        return True                              # QQ, KK, AA
    return h['hi'] == 14 and h['lo'] == 13       # AKs, AKo


def _tier(h):
    """Categoria grosseira da mão p/ o roteamento heurístico."""
    if _is_premium(h):
        return 'premium'
    if h['pair']:
        return 'pair'                            # 22..JJ,TT
    if h['suited']:
        if h['hi'] >= 10 and h['lo'] >= 10:
            return 'suited_broadway'             # JTs,QTs,QJs,KTs,KJs,KQs,ATs,AJs,AQs
        if h['hi'] == 14:
            return 'ax_suited'                   # A2s-A9s
        if h['hi'] == 13:
            return 'kx_suited_low'               # K2s-K9s
        return 'suited_other'                    # T9s,98s,Q9s,J9s,...
    if h['hi'] >= 10 and h['lo'] >= 10:
        return 'offsuit_broadway'                # KQo,KJo,KTo,QJo,QTo,JTo,ATo,AJo,AQo
    if h['hi'] == 14:
        return 'offsuit_ax'                      # A9o-A2o
    return 'trash'


def _dominated_by_weak_linear(h):
    """Suited que a PARTE FRACA de um range LINEAR já domina -> folda mesmo em size normal
    (regra 2, vs linear). Cobre K9s-, QTs/Q9s-, J9s-, e A8s- (kicker baixo). Linhas 20-47,
    212 do txt."""
    if not h['suited']:
        return False
    hi, lo = h['hi'], h['lo']
    if hi == 13 and lo <= 9:        # K9s e abaixo
        return True
    if hi == 12 and lo <= 10:       # QTs, Q9s e abaixo
        return True
    if hi == 11 and lo <= 9:        # J9s e abaixo
        return True
    if hi == 14 and lo <= 8:        # A8s e abaixo (dominadas pelos Ax do linear)
        return True
    return False


# Flats que SOBREVIVEM a uma size GRANDE (regra 1): só pares, premium e os suited de topo.
_BIG_SURVIVOR_SUITED = frozenset({'AQs', 'KQs'})


def advise(hero_pos, villain_pos, stack_bb, villain_3bet_size_x, villain_range_type, hand,
           is_ip_override=None):
    """Recomendação HEURÍSTICA (advisory) de defesa vs 3bet para UM spot.

    Retorna dict com `recommended` in {'fold','call','4bet','jam'}, os `factors` que a
    aula pondera, `validated`=False e `advisory_only`=True. NUNCA arma.
    """
    h = _parse_hand(hand)
    if h is None:
        return dict(status='SKIP', hand=hand, recommended=None,
                    reason='UNPARSEABLE_HAND', validated=False, advisory_only=True)

    rtype = (villain_range_type or '').lower()
    linear = (rtype == 'linear')
    polar = (rtype == 'polar')
    ip = is_ip(hero_pos, villain_pos) if is_ip_override is None else bool(is_ip_override)
    try:
        size_x = float(villain_3bet_size_x)
    except (TypeError, ValueError):
        size_x = 3.0
    try:
        stack = float(stack_bb)
    except (TypeError, ValueError):
        stack = 100.0

    big = size_x >= BIG_SIZE_X
    short = stack < SHORT_BB
    very_short = stack < VERY_SHORT_BB
    deep = stack >= DEEP_BB
    # Jam fino (bluff/thin value) tem fold equity: vs range polar OU confronto de
    # posições finais. TG-vs-TG (UTG vs UTG, linear) NÃO -> vilão paga range curto.
    thin_jam_ok = polar or (hero_pos in _LATE and villain_pos in _LATE)
    tier = _tier(h)

    factors = dict(tier=tier, is_ip=ip, size_x=size_x, big_size=big, stack_bb=stack,
                   short=short, very_short=very_short, deep=deep,
                   range_type=rtype, thin_jam_ok=thin_jam_ok)

    def out(action, reason):
        return dict(status='ADVICE', hand=hand, hero_pos=hero_pos, villain_pos=villain_pos,
                    recommended=action, range_type=rtype, factors=factors, reason=reason,
                    validated=False, advisory_only=True,
                    note='HEURISTICA DE ESTUDO (camada de ajuste sobre o pack). NAO ARMA.')

    # 1) VALOR PREMIUM (QQ+, AK): nunca folda. Commit (jam) se muito curto, senão 4bet valor.
    if tier == 'premium':
        if very_short:
            return out('jam', 'PREMIUM_COMMIT_SHORT')
        return out('4bet', 'PREMIUM_VALUE_4BET')

    # 2) PARES (22..TT): nunca foldam vs 3bet. Jam fino quando CURTO e há fold equity
    #    (polar/posição final); senão FLAT (nut potential, especialmente deep).
    if tier == 'pair':
        if short and thin_jam_ok:
            return out('jam', 'PAIR_4BET_JAM_SHORT_FOLD_EQUITY')
        return out('call', 'PAIR_FLAT_NUT_POTENTIAL' + ('_DEEP' if deep else ''))

    # 3) 4-BET-BLUFF que NEGA EQUIDADE (quando a size não é grande):
    #    - Ax-suited de kicker baixo (A5s-A7s) vs range que 3beta leve (polar), deepish.
    #    - Offsuit A-broadway (ATo/AQo) OOP: performa mal como flat no 3bet pot -> 4bet
    #      (deep) ou JAM (curto, com fold equity).
    if not big:
        if tier == 'ax_suited' and h['lo'] in (5, 6, 7) and polar and not short:
            return out('4bet', 'AX_SUITED_4BET_BLUFF_VS_POLAR')
        if tier == 'offsuit_broadway' and h['hi'] == 14 and not ip:
            if short and thin_jam_ok:
                return out('jam', 'OFFSUIT_ABROADWAY_OOP_JAM_SHORT')
            if deep:
                return out('4bet', 'OFFSUIT_ABROADWAY_OOP_4BET_DEEP')
            return out('fold', 'OFFSUIT_ABROADWAY_OOP_FOLD')

    # 4) SIZE GRANDE: cai a borda do flat. Só pares/premium (já tratados) e suited de topo
    #    sobrevivem; o resto folda (regra 1).
    if big and hand not in _BIG_SURVIVOR_SUITED:
        return out('fold', 'BIG_SIZE_FOLD_MARGINAL')

    # 5) FLATS (suited privilegiado por flopabilidade; offsuit broadway é o divisor
    #    linear/polar).
    if tier in ('suited_broadway', 'ax_suited', 'kx_suited_low', 'suited_other'):
        if linear and _dominated_by_weak_linear(h):
            return out('fold', 'SUITED_DOMINATED_VS_LINEAR')
        return out('call', 'SUITED_FLAT' + ('_VS_POLAR' if polar else ''))

    if tier == 'offsuit_broadway':
        if linear:
            return out('fold', 'OFFSUIT_BROADWAY_FOLD_VS_LINEAR')
        # vs POLAR: IP defende largo; OOP só o topo (KQo/A-broadway), resto folda (regra 3).
        if ip:
            return out('call', 'OFFSUIT_BROADWAY_CALL_IP_VS_POLAR')
        if h['hi'] >= 13:
            return out('call', 'OFFSUIT_BROADWAY_TOP_CALL_OOP_VS_POLAR')
        return out('fold', 'OFFSUIT_BROADWAY_OOP_VS_POLAR_FOLD')

    if tier == 'offsuit_ax':
        if polar and ip:
            return out('call', 'OFFSUIT_AX_CALL_IP_VS_POLAR')
        return out('fold', 'OFFSUIT_AX_FOLD')

    return out('fold', 'TRASH_FOLD')


def advise_spot(spot):
    """Conveniência: aceita um dict de fixture {hero_pos,villain_pos,stack_bb,
    villain_3bet_size_x,villain_range_type,hand}."""
    return advise(spot.get('hero_pos'), spot.get('villain_pos'), spot.get('stack_bb'),
                  spot.get('villain_3bet_size_x'), spot.get('villain_range_type'),
                  spot.get('hand'), is_ip_override=spot.get('is_ip'))
