"""C-bet do AGRESSOR (PFR) IP contra o BIG BLIND em pote de raise simples (série de aulas
'Teoria para c-bet vs BB', Reg-Life/Eduardo — [[nvt-teoria-reg-life-corpus]]).

Lição central: contra o range AMPLO do BB, o PFR c-beta numa frequência ALTÍSSIMA (UTG vs
BB ~86%, BTN vs BB ~70%, 20bb ~90%) com size PEQUENO (≈20% pote / 1bb) como padrão. A aula
é sobre QUAIS boards NÃO c-betar 100% — as texturas em que o range de defesa do BB tem
vantagem de nuts. Fora delas, c-bet range (pequeno).

BOARDS DE PERIGO (checar mais / não c-betar range):
  • low_connected      — 3 cartas baixas conectadas (642, 567, 985): BB acerta seq/2-par.
  • mid_paired         — pareado no meio/baixo (774, 55x): BB tem mais trincas (nuts).
  • ace_high_monotone  — A-alto monotone: BB tem muito mais flush que o PFR.
  • monotone           — 3 do mesmo naipe: alerta de flush do BB.
PURO: classifica a textura; não captura, não clica.
"""

_DANGER = ('low_connected', 'mid_paired', 'ace_high_monotone', 'monotone')
# Perigo por FLUSH (monotone) depende de profundidade: só vale deep. Short/vs-humano
# aposta 100% (aula 20-02-16/18-46-13: "A-high monotone só se deep ≥60bb").
_FLUSH_DANGER = ('ace_high_monotone', 'monotone')
DEEP_BB = 60.0


def cbet_check_category(bclass, stack_bb=None):
    """Categoria de board em que o PFR IP vs BB NÃO c-beta range (checa mais). None = board
    de c-bet range (aposta pequena em alta frequência). Prioridade: flush > pareado > seq.

    `stack_bb` (opcional): quando dado, o perigo de FLUSH (monotone/A-high monotone) só vale
    DEEP (≥60bb) — short/vs-humano aposta 100%. Sem stack_bb = comportamento antigo (perigo
    sempre), p/ não regredir chamadas existentes."""
    if not isinstance(bclass, dict):
        return None
    high = bclass.get('high_rank', 0)
    paired = bool(bclass.get('paired'))
    straightish = bclass.get('straightish', 0)
    monotone = (bclass.get('texture') == 'monotone') or bclass.get('flush_count', 0) >= 3
    cat = None
    if high == 14 and monotone:
        cat = 'ace_high_monotone'
    elif monotone:
        cat = 'monotone'
    elif paired and high <= 10:               # pareado no meio/baixo
        cat = 'mid_paired'
    elif (not paired) and high <= 9 and straightish >= 3:
        cat = 'low_connected'
    # stack-gate do perigo de flush: short -> c-beta (não é perigo)
    if cat in _FLUSH_DANGER and isinstance(stack_bb, (int, float)) and stack_bb < DEEP_BB:
        return None
    return cat


def is_danger_board(bclass, stack_bb=None):
    """True se é board de perigo (checar mais) p/ o PFR IP vs BB."""
    return cbet_check_category(bclass, stack_bb) in _DANGER


def is_cbet_range_board(bclass, stack_bb=None):
    """True se é board de c-bet range (apostar pequeno em alta frequência)."""
    return cbet_check_category(bclass, stack_bb) is None


# --- Frequência de c-bet por POSIÇÃO do abridor + STACK (série 'Teoria c-bet vs BB') ---
# Cai de UTG (range forte/estreito) a BTN (range amplo) porque o range enfraquece.
# Números citados: UTG ~86%; IP inicial 90%@20bb / 85%@40bb; BTN 70%@20bb / 75%@40bb / 70%@100bb.
_EARLY = ('UTG', 'UTG+1', 'UTG+2', 'EP', 'EARLY')
_MID = ('LJ', 'HJ', 'MP', 'MP1', 'MP2', 'CO', 'MIDDLE')
_LATE = ('BTN', 'BU', 'BUTTON')


def _pos_group(position):
    pos = (position or '').upper().strip()
    if pos in _EARLY:
        return 'early'
    if pos in _LATE:
        return 'late'
    if pos in _MID:
        return 'mid'
    return None


def cbet_freq_vs_bb(position, stack_bb=None):
    """Frequência TEÓRICA de c-bet do PFR IP vs BB (pote single-raised HU), por posição do
    ABRIDOR e stack. ADVISORY (sinaliza o lean de frequência; não executa — a decisão por
    mão made/draws/equity segue). Retorna dict(freq, group, basis) ou None se a posição não
    for reconhecida. 'mid' é interpolado [geral] (os vídeos não dão número exato de CO/MP)."""
    g = _pos_group(position)
    if g is None:
        return None
    s = stack_bb if isinstance(stack_bb, (int, float)) else 40.0
    if g == 'early':
        freq = 0.90 if s <= 25 else 0.85     # UTG ~86%; 90%@20bb, 85%@40bb+
    elif g == 'late':
        freq = 0.70 if s <= 25 else (0.75 if s <= 60 else 0.70)   # BTN 70/75/70
    else:  # mid — entre early e late (sem número citado)
        freq = 0.80
    return dict(freq=round(freq, 2), group=g,
                basis='teoria c-bet vs BB: freq por posição+stack (early>mid>late)')
