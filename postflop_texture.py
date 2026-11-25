"""Textura do board -> TAMANHO de aposta pós-flop (Pós-flop Avançado, curso Reg-Life do
Eduardo — [[nvt-teoria-reg-life-corpus]]). Regra prática destilada do solver:

  • Board ALTO (T+) ou PAREADO, seco -> o agressor pré-flop tem vantagem de RANGE/nuts ->
    RANGE-BET PEQUENO (1/3), apostando largo.
  • Board BAIXO (<=9) NÃO-pareado, seco -> POLARIZA GRANDE (2/3): valor + ar apostam
    grande; mãos MÉDIAS dão check (a frequência já é tratada no advisor: média = check).
  • Board MOLHADO (flush/seq possível) -> aposta GRANDE p/ proteger / negar equidade.

Lema do capítulo: 'vantagem de RANGE -> FREQUÊNCIA; vantagem de NUTS -> TAMANHO.'
CLAMPADO ao nosso slider (1/3, 1/2, 2/3) — 'grande' NUNCA é overbet cru; o geométrico fica
a cargo do postflop_sizing ([[nvt-posflop-sizes-nosso-slider]]). PURO: sem captura/clique.
"""

SMALL, MEDIUM, BIG = 1.0 / 3.0, 0.5, 2.0 / 3.0


# Equity buckets (Pós-flop Avançado): blocos de equidade p/ ler força de range/nuts.
#   nuts   >=90%  (trincas+)           strong 80-90% (overpairs/2-par)
#   value  70-80% (top pairs)          medium 60-70% (pares do meio)   weak <60%
_BUCKETS = (('nuts', 0.90), ('strong', 0.80), ('value', 0.70), ('medium', 0.60))


def equity_bucket(equity):
    """Bucket de equidade do hero (Pós-flop Avançado). None passthrough (sem range)."""
    if not isinstance(equity, (int, float)):
        return None
    for name, lo in _BUCKETS:
        if equity >= lo:
            return name
    return 'weak'


def polarizes(bclass):
    """Board de estratégia POLARIZADA para o AGRESSOR (baixo <=9 não-pareado): só valor
    forte + ar apostam GRANDE; mãos MÉDIAS (top pair fino etc.) dão CHECK — controle de
    pote (Pós-flop Avançado: 'não apostamos todo o range', check ~50%)."""
    return bclass.get('high_rank', 0) <= 9 and not bclass.get('paired')


def nuts_holder(bclass, *, hero_is_aggressor):
    """Vantagem de NUTS do ponto de vista do HERO: 'hero' / 'villain' / 'neutral'
    (aproxima ranges padrão PFR vs defensor). É METADADO honesto p/ caveat/auditoria;
    não dita o size sozinho (o size vem da estrutura do board)."""
    high = bclass.get('high_rank', 0) >= 12            # Q+ (broadway)
    low = bclass.get('high_rank', 0) <= 9
    paired = bool(bclass.get('paired'))
    connected = bclass.get('straightish', 0) >= 3
    if high and not paired:
        holder = 'pfr'                                 # overpairs/broadways do PFR
    elif (low and connected) or (paired and not high):
        holder = 'caller'                              # seq/2-pares/trincas do range largo
    else:
        return 'neutral'
    if hero_is_aggressor is None:
        return 'neutral'
    me = 'pfr' if hero_is_aggressor else 'caller'
    return 'hero' if holder == me else 'villain'


DEEP_SPR = 4.0      # SPR a partir do qual o regime é DEEP (≈40bb+ em pote de raise simples)


def bet_plan(bclass, *, is_strong, has_strong_draw, hero_is_aggressor=None, spr=None):
    """Plano de TAMANHO p/ uma aposta pós-flop: {fraction, lean, nuts, rationale}.
    `fraction` já no vocabulário do slider (1/3, 1/2 ou 2/3). `lean` é a intenção
    (range_small / polarized_big / protect_big / semi_bluff) p/ caveat e p/ a frequência.

    `spr` (opcional) ativa o regime DEEP (c-bet vs BB deep, Reg-Life): mão feita FORTE em
    board DINÂMICO deep CONTROLA o pote (não infla mão vulnerável p/ um river gigante);
    DRAW robusto deep em board conectado INFLA (vira nut-range no futuro); board seco-seguro
    deep mantém grande. Sem spr (ou short) = regime atual (aposta a equidade pronta)."""
    flush = bool(bclass.get('flush_possible'))
    straightish = bclass.get('straightish', 0)
    high_or_paired = bclass.get('high_rank', 0) >= 10 or bool(bclass.get('paired'))
    # board ALTO/pareado vence a falsa-conexão da RODA do Ás (A-2...); só é molhado de
    # verdade com flush OU 4 cartas de sequência real.
    truly_wet = flush or straightish >= 4
    nuts = nuts_holder(bclass, hero_is_aggressor=hero_is_aggressor)

    if has_strong_draw and not is_strong:
        frac = BIG if (truly_wet or not high_or_paired) else MEDIUM
        lean = 'semi_bluff'
        rat = 'semi-blefe: grande em board polar/molhado, médio em board de range-bet'
    elif flush:
        frac, lean = BIG, 'protect_big'
        rat = 'board com flush possível: aposta grande p/ proteger e negar equidade'
    elif high_or_paired and straightish < 4:
        frac, lean = SMALL, 'range_small'
        rat = 'board alto/pareado seco: PFR com vantagem de range -> range-bet pequeno'
    elif straightish >= 3:
        frac, lean = BIG, 'protect_big'
        rat = 'board conectado: aposta grande p/ proteger e negar equidade (nuts conta)'
    else:   # baixo não-pareado seco
        frac, lean = BIG, 'polarized_big'
        rat = 'board baixo não-pareado: polariza grande (valor+ar); média dá check'
    # --- Regime DEEP (c-bet vs BB deep, Reg-Life): a profundidade muda o size ---
    deep = isinstance(spr, (int, float)) and spr >= DEEP_SPR
    dynamic = flush or straightish >= 3
    if deep and is_strong and dynamic and frac == BIG:
        # mão feita forte em board dinâmico deep se DETERIORA no runout -> controla o pote
        # (não infla uma mão vulnerável p/ um river gigante). Overbet só em board seco-seguro.
        frac, lean = MEDIUM, 'deep_control'
        rat = 'deep: mão feita em board dinâmico -> controla o pote (não infla vulnerável)'
    elif deep and has_strong_draw and not is_strong and dynamic:
        # draw ROBUSTO deep (vira nut-range no futuro) -> infla já p/ maximizar o river.
        frac, lean = BIG, 'deep_robust_draw'
        rat = 'deep: draw robusto em board conectado -> infla p/ o nut-range futuro'
    return dict(fraction=frac, lean=lean, nuts=nuts, rationale=rat)
