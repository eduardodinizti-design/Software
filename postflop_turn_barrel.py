"""Barril de TURN em posição contra o BB (second barrel) — curso Reg-Life (aula c-bet vs
BB, 19/11). Codifica a HEURÍSTICA POLARIZADA de second barrel e os tipos de carta de turn.

As DUAS PERGUNTAS-GUIA (define a gaveta da mão):
  VALOR  -> a mão é forte p/ apostar turn E na MAIORIA dos rivers (out limpo), tomando call
            de mãos piores? Se sim, aposta (polo forte: bet-bet).
  BLEFE  -> a mão faz uma mão MELHOR foldar (nega/cuida equidade RELEVANTE — 60-70%, não
            20-30%) e desbloqueia o fold do vilão? Se sim, aposta (polo fraco).
  MEIO   -> boa equidade, mas NÃO é value de river e NÃO faz melhor foldar -> CHECK
            (controle de pote + pagar o probe/bluff do river). "Betar turn pra dar check
            river não existe": ou vale turn+river, ou é blefe que nega, ou é check.

TIPOS DE CARTA DE TURN (5, estratégias/sizes diferentes): dobra top/meio/baixo, completa
flush, completa sequência, overcard (> maior do flop) e blank. Range-bet no flop -> barril
~50%; flop NÃO range-bet (board já filtrado, range mais forte) -> barril MAIS alto. Cartas
altas que formam draws (T/J/Q) barrelam mais; baixa/meio (3/9) menos.

Exploratório/advisory: classifica gaveta + tipo de carta + lean de frequência/size; NÃO
reescreve a decisão do advisor (made/draws/textura/equity já decidem). Serve p/ alinhar a
polarização, auditar e, depois, dirigir a execução. PURO: sem captura, sem clique."""
from postflop_eval import _cards

VALUE, BLUFF, MIDDLE = 'value', 'bluff', 'middle'

# Mãos fortes o bastante p/ valor turn+river (mesmo _STRONG do advisor, sem top_pair: o top
# pair é borderline — o advisor já separa valor fino de check).
_VALUE_MADE = ('set', 'trips', 'two_pair', 'overpair', 'straight', 'flush',
               'full_house', 'quads', 'straight_flush')
# Showdown value sem valor de river (gaveta do meio): pares médios/fracos e top pair fraco.
_MIDDLE_MADE = ('top_pair', 'second_pair', 'third_pair', 'low_pair', 'underpair')


def barrel_tier(made, draws):
    """Gaveta do barril de turn p/ a mão feita + draws: 'value' | 'bluff' | 'middle'."""
    draws = draws or {}
    strong_draw = bool(draws.get('combo') or draws.get('flush_draw') or draws.get('oesd'))
    if made in _VALUE_MADE:
        return VALUE
    # Ar/overcards: polo fraco -> blefe que nega/cuida (melhor ainda com equidade de draw).
    if made in (None, 'air', 'overcards'):
        return BLUFF
    # Par mediano/top pair fraco: MEIO (check), salvo com draw forte (semi-blefe sobe a valor).
    if made in _MIDDLE_MADE:
        return BLUFF if strong_draw else MIDDLE
    return MIDDLE


def classify_turn(board):
    """Tipo da carta de turn a partir do board de 4 cartas (flop + turn). Devolve um de:
    'pairs_top'/'pairs_mid'/'pairs_low', 'completes_flush', 'completes_straight',
    'overcard', 'blank'. (board de 3 cartas ou menos -> None.)"""
    cards = _cards(board)
    if len(cards) < 4:
        return None
    flop, turn = cards[:3], cards[3]
    tr, ts = turn
    flop_ranks = sorted((r for r, _ in flop), reverse=True)
    flop_suits = [s for _, s in flop]
    # 1) completa flush: turn traz o 3º naipe (flop tinha 2 do naipe do turn).
    if flop_suits.count(ts) == 2:
        return 'completes_flush'
    # 2) dobra uma carta do flop.
    if tr in flop_ranks:
        if tr == flop_ranks[0]:
            return 'pairs_top'
        if tr == flop_ranks[-1]:
            return 'pairs_low'
        return 'pairs_mid'
    # 3) completa sequência: 4-ranks dentro de uma janela de 5 (coordenado).
    rset = {r for r, _ in cards} | ({1} if any(r == 14 for r, _ in cards) else set())
    window = 0
    for top in range(14, 4, -1):
        window = max(window, sum(1 for r in range(top, top - 5, -1) if r in rset))
    flop_rset = {r for r, _ in flop} | ({1} if any(r == 14 for r, _ in flop) else set())
    flop_window = 0
    for top in range(14, 4, -1):
        flop_window = max(flop_window, sum(1 for r in range(top, top - 5, -1) if r in flop_rset))
    if window >= 4 and window > flop_window:
        return 'completes_straight'
    # 4) overcard: maior que a maior do flop.
    if tr > flop_ranks[0]:
        return 'overcard'
    return 'blank'


# Cartas de turn que, SENDO overcard/broadway, mais formam draws e favorecem o agressor IP.
_HIGH_DRAWY = ('overcard',)
# Cartas que favorecem o range do BB (quem pagou o flop) -> mais cuidado/menos barril.
_FAVORS_CALLER = ('completes_flush', 'completes_straight', 'pairs_low', 'pairs_mid')


def barrel_lean(turn_type, *, range_bet_flop=True):
    """Lean de FREQUÊNCIA do second barrel pelo tipo de carta + se o flop foi range-bet.
    Devolve dict(freq_lean='more'/'neutral'/'less', note). Advisory (não é a decisão)."""
    if turn_type in _FAVORS_CALLER:
        lean = 'less'
        note = 'carta favorece o range do BB (caller) -> mais cuidado/check'
    elif turn_type in _HIGH_DRAWY:
        lean = 'more'
        note = 'overcard favorece o agressor IP e forma draws -> barril mais'
    else:
        lean = 'neutral'
        note = 'carta neutra (blank/dobra o topo) -> polarização padrão'
    # Flop NÃO range-bet (board já filtrado no flop) -> range mais forte -> barril mais alto.
    if not range_bet_flop and lean != 'less':
        lean = 'more'
        note = note + '; flop não range-bet (range já filtrado) -> frequência maior'
    return dict(freq_lean=lean, note=note)
