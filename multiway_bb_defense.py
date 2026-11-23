"""Defesa MULTIWAY do Big Blind (pre-flop, MTT) -- camada de ESTUDO.

Codifica a aula "Defesa multiway do Big Blind" (transcricao
'Ranges E TEORIAS/Teoria/2026-11-22 21-30-14.txt', partes 1 e 2).

CONTRAINTUITIVO-CHAVE da aula: em pote multiway (um raise + um ou mais calls)
o BB defende MENOS, nao mais -- apesar das melhores pot odds. Motivo: a
realizacao de equidade do BB DESPENCA (OOP, equidade dividida com 2+ ranges
fortes, reverse implied odds). Mais jogadores no pote => FOLDAR MAIS.

FOLD-MORE escala com (todos extraidos da aula):
  (a) n de jogadores no pote (HU ~21% -> 3way CO+BTN ~36% -> 4way ~76%);
  (b) OOP vs IP: se o caller e o SB (BB fica IP sobre ele) defende quase como
      HU; se ha BTN/caller atras (BB OOP) folda muito;
  (c) profundidade: 100bb folda MUITO mais que 25bb (reverse implied; em 25bb
      qualquer top pair/flush draw realiza e segue ao river);
  (d) forca do range dos viloes: UTG+LJ (tight) folda mais que CO+BTN (wide);
      SB capado (sem topo) => defende/squeeze MAIS.

SQUEEZE do BB:
  @100bb range LINEAR (broadways suited c/ nut potential: AJs, KJs, QJs; + um
  pouco de 56s-78s p/ cobrir board). ~12% OOP, ~17% quando IP vs SB capado.
  @25bb POLARIZADO + muito JAM/chove (valor KK+/AQ+ induz via 3bet; o resto --
  Axo em posicao final, pares, blockers A5s/A7o -- vai de JAM).
  Size: ~6x em 100bb (~12bb), ~3.5x em 25bb (~6.6bb). Squeeze MAIS vs SB capado.

PURO / HEURISTICO: sem captura, sem clique, sem estado ao vivo. validated=False
e NUNCA arma/decide sozinho -- e uma camada de estudo gated, igual ao guia
pos-flop. Numeros sao ANCORAS da aula interpoladas; marque como a validar.

LIGACAO com o que ja existe:
  - multiway_equity.py aplica -12% (relativo) de equity por vilao EXTRA no
    POS-FLOP. Este modulo e o par PRE-FLOP: fold-more por jogador extra. O
    incremento 'wide' usa exatamente MULTIWAY_PENALTY_PER_EXTRA (0.12), ou seja
    a aula CONFIRMA/CALIBRA a guarda existente (vilao wide extra ~ +12% fold).
  - preflop_advisor.py ja marca spots multiway como validated=False /
    multiway_approx ("direcao multiway = mais apertado") e trata squeeze curto
    como 3bet-JAM. Este modulo QUANTIFICA esse "mais apertado" e descreve o
    perfil do squeeze (linear@deep / polar+jam@short); nao conflita.
"""

try:
    from multiway_equity import MULTIWAY_PENALTY_PER_EXTRA  # 0.12
except Exception:  # pragma: no cover - fallback se import falhar
    MULTIWAY_PENALTY_PER_EXTRA = 0.12

VALIDATED = False  # camada de estudo; NUNCA executa ao vivo

# --- ancoras de fold (fracao do range foldado), extraidas da aula ---
FOLD_HU_25 = 0.21          # BB vs CO HU, 25bb (linha 22)
FOLD_HU_100 = 0.30         # BB vs CO HU, 100bb (linha 95)
# incremento de fold por jogador EXTRA (alem de hero + 1 raiser), por forca:
FOLD_INC_PER_EXTRA = {
    "wide": MULTIWAY_PENALTY_PER_EXTRA,  # 0.12  (CO+BTN: 36%@25 / 40%@100)
    "tight": 0.28,                       # UTG+LJ: ~60%@100 (3way)
    "capped": 0.07,                      # SB capado => defende mais
}
FOLD_INC_DEFAULT = 0.15
FOLD_SATURATION = 0.75     # cada jogador extra adicional soma menos (4way sub-linear)

# --- ancoras de squeeze ---
SQUEEZE_FREQ_WIDE_DEEP = 0.12            # CO+BTN 100bb (linha 374)
SQUEEZE_STRENGTH_MULT = {"wide": 1.0, "capped": 1.40, "tight": 0.58}
SQUEEZE_SIZE_SHORT = 6.6                 # ~3.5x em 25bb (linha 461)
SQUEEZE_SIZE_DEEP = 12.0                 # ~6x em 100bb (linha 429)
SHORT_STACK_MAX = 40                     # <= isto = regime "curto" (jam/polar)

_RANK = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
         "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}

# broadways suited com nut potential que lideram o squeeze linear @deep
_SUITED_NUT = {"AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "KTs", "QJs", "QTs", "JTs"}


# ----------------------------- parsing de mao -----------------------------
def parse_hand(hand):
    """'A8o'/'KJs'/'88'/'QTo' -> (hi, lo, suited, pair). hi>=lo em rank."""
    h = (hand or "").strip()
    if len(h) < 2:
        raise ValueError("mao invalida: %r" % hand)
    r1, r2 = _RANK[h[0]], _RANK[h[1]]
    pair = r1 == r2
    suited = (not pair) and h[2:3].lower() == "s"
    hi, lo = max(r1, r2), min(r1, r2)
    return hi, lo, suited, pair


def is_short(stack_bb):
    try:
        return float(stack_bb) <= SHORT_STACK_MAX
    except (TypeError, ValueError):
        return False


# ------------------------- macro: fold-more scaling -------------------------
def _base_hu_fold(stack_bb):
    try:
        s = float(stack_bb)
    except (TypeError, ValueError):
        s = 25.0
    t = max(0.0, min(1.0, (s - 25.0) / (100.0 - 25.0)))
    return FOLD_HU_25 + (FOLD_HU_100 - FOLD_HU_25) * t


def estimated_fold_freq(n_players, stack_bb, opp_strength, hero_rel_position):
    """Fracao do range que o BB folda, ancorada na aula.

    HU -> base (21%@25bb .. 30%@100bb). IP (caller = SB, BB em posicao) ->
    defende ~como HU. OOP multiway -> soma incremento por jogador extra, maior
    quanto mais tight o range dos viloes; cada extra adicional soma menos.
    """
    base = _base_hu_fold(stack_bb)
    extra = max(0, int(n_players) - 2)  # jogadores alem de hero + 1 raiser
    if extra == 0:
        return round(base, 3)
    if hero_rel_position == "IP":
        # BB tem posicao sobre o unico caller (SB): realiza quase como HU
        return round(base, 3)
    inc = FOLD_INC_PER_EXTRA.get(opp_strength, FOLD_INC_DEFAULT)
    total = base
    for i in range(extra):
        total += inc * (FOLD_SATURATION ** i)
    return round(min(0.95, total), 3)


# --------------------------- macro: perfil squeeze ---------------------------
def squeeze_profile(stack_bb):
    """'polarized_jam' em stacks curtos (<=40bb) / 'linear' em deep."""
    return "polarized_jam" if is_short(stack_bb) else "linear"


def squeeze_freq_est(stack_bb, opp_strength, hero_rel_position):
    """Frequencia de squeeze do BB. Maior vs capado / quando IP, menor vs tight.
    (~12% wide, ~17% capado/IP, ~7% tight, da aula.) Magnitude ~estavel por
    stack; o que muda e o PERFIL (linear vs polar+jam)."""
    f = SQUEEZE_FREQ_WIDE_DEEP * SQUEEZE_STRENGTH_MULT.get(opp_strength, 1.0)
    return round(min(0.5, f), 3)


def squeeze_size_bb(stack_bb):
    """Size do squeeze em bb: ~6.6 em 25bb .. ~12 em 100bb."""
    try:
        s = float(stack_bb)
    except (TypeError, ValueError):
        s = 25.0
    t = max(0.0, min(1.0, (s - 25.0) / (100.0 - 25.0)))
    return round(SQUEEZE_SIZE_SHORT + (SQUEEZE_SIZE_DEEP - SQUEEZE_SIZE_SHORT) * t, 1)


# -------------------------- classificador de linha --------------------------
def classify_line(hand, stack_bb, opp_strength, hero_rel_position, n_players=3):
    """Retorna (line, style). line in {'fold','call','aggressive','study'};
    style in {None,'squeeze_linear','squeeze_polar','jam'}.

    'aggressive' = squeeze/3bet/jam (familia agressiva; no curto 3bet e jam se
    fundem). 'study' = marginal/incerto -> o modulo ABSTEM (nunca chuta).
    """
    hi, lo, suited, pair = parse_hand(hand)
    short = is_short(stack_bb)
    deep = not short

    def agg():
        if deep:
            return "aggressive", "squeeze_linear"
        if premium:
            return "aggressive", "squeeze_polar"
        return "aggressive", "jam"

    premium = pair and hi >= 12          # QQ, KK, AA
    premium = premium or (hi == 14 and lo in (13, 12))  # AKo/AKs, AQo/AQs

    # R1: valor premium -> sempre agressivo (squeeze; induz no curto)
    if premium:
        return agg()

    axo_small = (hi == 14 and not suited and not pair and lo <= 9)  # A2o..A9o

    if short:
        # R2: Axo em posicao final (25bb) -> JAM
        if axo_small:
            return agg()
        # R2b: 25bb vs ranges tight -> Q9o tambem prefere JAM (de pao)
        if opp_strength == "tight" and not suited and not pair and hi == 12 and lo == 9:
            return agg()
        # R3: Ax suited (wheel/blocker) no curto -> JAM
        if hi == 14 and suited:
            return agg()
        # R4: pares medios no curto -> JAM (QQ+ ja saiu em R1)
        if pair and 7 <= hi <= 11:
            return agg()
        # R5: KTo/KJo vs SB capado no curto -> JAM
        if (opp_strength == "capped" and not suited and not pair
                and hi == 13 and lo >= 10):
            return agg()
    else:  # deep
        # R6: broadway suited c/ nut potential -> squeeze linear
        if (hand[:2] + ("s" if suited else "")) in _SUITED_NUT:
            return agg()
        # R7: suited connectors (54s..T9s) -> cobertura de board
        if suited and (hi - lo) <= 1 and 5 <= lo and hi <= 10:
            return agg()
        # R8: vs SB capado em deep, amplia o valor/blocker
        if opp_strength == "capped":
            if not suited and not pair and hi >= 13 and lo >= 10:   # ATo+/KJo+ (hi A ou K)
                return agg()
            if not suited and not pair and hi == 14 and lo >= 10:   # ATo/AJo
                return agg()
            if suited and hi >= 12:                                 # blocker suited alto (Q5s)
                return agg()
            if pair and hi >= 8:                                    # 88+
                return agg()
        # R9: vs ranges tight em deep, quase tudo que nao e agressivo FOLDA
        if opp_strength == "tight":
            return "fold", None

    # R10: defesa IP no curto (BB IP sobre o SB) -- call largo, folda so o lixo
    if short and hero_rel_position == "IP" and opp_strength in ("capped", "wide"):
        if suited:
            return "call", None
        if hi == 13:                       # qualquer K-high offsuit
            return "call", None
        if hi >= 10 and lo >= 8:           # offsuit broadway c/ kicker decente
            return "call", None
        if (hi - lo) <= 1 and lo >= 7:     # connector offsuit alto
            return "call", None
        return "fold", None

    # R11: incerto -> estudo (abstem; nunca chuta ao vivo)
    return "study", None


def recommend(stack_bb, opp_strength, hero_rel_position, n_players=3, hand=None):
    """Recomendacao completa (macro + linha da mao). validated=False sempre."""
    res = dict(
        validated=VALIDATED,
        fold_freq_est=estimated_fold_freq(n_players, stack_bb, opp_strength,
                                          hero_rel_position),
        squeeze=dict(profile=squeeze_profile(stack_bb),
                     freq_est=squeeze_freq_est(stack_bb, opp_strength,
                                               hero_rel_position),
                     size_bb=squeeze_size_bb(stack_bb)),
        direction="tighter_multiway",  # alinhado a preflop_advisor (mais apertado)
    )
    if hand is not None:
        line, style = classify_line(hand, stack_bb, opp_strength,
                                     hero_rel_position, n_players)
        res["line"] = line
        res["style"] = style
    return res


# mapeia a acao das fixtures p/ a 'line' do classificador
def action_to_line(action):
    if action in ("squeeze", "jam"):
        return "aggressive"
    return action  # 'fold' / 'call'
