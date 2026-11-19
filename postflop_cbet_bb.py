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


def cbet_check_category(bclass):
    """Categoria de board em que o PFR IP vs BB NÃO c-beta range (checa mais). None = board
    de c-bet range (aposta pequena em alta frequência). Prioridade: flush > pareado > seq."""
    if not isinstance(bclass, dict):
        return None
    high = bclass.get('high_rank', 0)
    paired = bool(bclass.get('paired'))
    straightish = bclass.get('straightish', 0)
    monotone = (bclass.get('texture') == 'monotone') or bclass.get('flush_count', 0) >= 3
    if high == 14 and monotone:
        return 'ace_high_monotone'
    if monotone:
        return 'monotone'
    if paired and high <= 10:                 # pareado no meio/baixo
        return 'mid_paired'
    if (not paired) and high <= 9 and straightish >= 3:
        return 'low_connected'
    return None


def is_danger_board(bclass):
    """True se é board de perigo (checar mais) p/ o PFR IP vs BB."""
    return cbet_check_category(bclass) in _DANGER


def is_cbet_range_board(bclass):
    """True se é board de c-bet range (apostar pequeno em alta frequência)."""
    return cbet_check_category(bclass) is None
