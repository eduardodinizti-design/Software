"""C-bet de RIVER em posição contra o BB (bet flop + bet turn + bet river) — curso Reg-Life
(aula CBET River, 19/11). Codifica a POLARIZAÇÃO MÁXIMA do river IP e o VALOR RELATIVO.

Princípios (IP, agressor, linha bet-bet-bet):
  • Range MÁXIMO POLARIZADO: só aposta as MELHORES (valor) e as PIORES (blefe) — NUNCA mão
    média. O range chega FILTRADO (bet flop+turn) -> muita mão forte -> os blefes vão a
    frequência altíssima (até 100% das piores que NÃO bloqueiam o fold do vilão).
  • VALOR RELATIVO: a carta de river reseta o valor. River que COMPLETA DRAWS (flush/
    sequência) derruba two pair/overpair/top pair (deixam de ser valor -> check); o piso de
    valor sobe p/ trinca/sequência/flush+. River BLANK: top pair seco volta a ser valor.
  • SIZE por vantagem de nuts: nuts -> apostas gigantes/overbet/all-in (quanto maior, mais
    EV); forte-não-nuts -> aposta GRANDE mas MENOR que all-in; médio -> check; IP não tem
    blocking bet (aposta pequena) — ou grande, ou check.
  • BLOQUEADORES mandam no blefe: blefa as piores que NÃO bloqueiam o range de fold do
    vilão; mão que bloqueia o fold dele (ex.: segura o flush-draw que ele foldaria) = blefe
    RUIM -> check. (Seleção fina por combo fica como refino; aqui tratamos por categoria.)

PURO: sem captura, sem clique. Advisory + promoção de DISCIPLINA DE VALOR (não value-beta
mão que perdeu valor relativo em river que completou draws)."""

# Piso de valor do river. Em river que COMPLETOU draws, só trinca/sequência/flush+ são valor.
_VALUE_DRAWY = ('set', 'trips', 'straight', 'flush', 'full_house', 'quads', 'straight_flush')
# Em river BLANK/seco, top pair e acima são valor.
_VALUE_DRY = _VALUE_DRAWY + ('two_pair', 'overpair', 'top_pair')
# Nuts (vantagem p/ overbet/all-in).
_NUTS = ('full_house', 'quads', 'straight_flush')
_BLUFF_MADE = (None, 'air', 'overcards')


def is_draw_complete(bclass):
    """True se o board de river completou flush/sequência ou é muito coordenado (straightish
    >= 4) — derruba o valor relativo das mãos de 1-2 pares."""
    return bool(bclass.get('flush_possible') or bclass.get('straight_on_board')
                or (bclass.get('straightish') or 0) >= 4)


def river_value_ok(made, bclass):
    """A mão feita é VALOR p/ apostar no river, dado o board? (piso sobe se completou draws.)"""
    floor = _VALUE_DRAWY if is_draw_complete(bclass) else _VALUE_DRY
    return made in floor


def river_tier(made, draws, bclass):
    """Gaveta do river: 'value' (aposta grande) / 'bluff' (piores, frequência alta) /
    'check' (valor relativo médio, sem valor de aposta nem de blefe)."""
    if river_value_ok(made, bclass):
        return 'value'
    if made in _BLUFF_MADE:
        return 'bluff'
    return 'check'


def river_size_hint(made, bclass):
    """Lean de SIZE do river (nossa política: valor grande; nuts libera overbet/all-in):
    'overbet' (nuts) / 'big' (valor não-nuts) / 'none'."""
    if made in _NUTS:
        return 'overbet'
    if river_value_ok(made, bclass):
        return 'big'
    return 'none'
