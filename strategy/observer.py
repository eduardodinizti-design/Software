"""B09 — observação contínua LEVE (plano de evolução do cérebro, Lote 2).

Mantém o CENÁRIO por (mesa, mão) a partir do vetor de apostas, usando só o
classificador barato do B08 (`classify`) — SEM o cálculo pesado de estratégia
(equity/advise). Assim a otimização de pular o advise fora da vez do hero NÃO
descarta a história observável: o nível/agressor do pote continua rastreado a
cada frame barato, e um frame que PERDE a leitura (ex.: raise não lido por um
instante) não "des-abre" o pote — a agressão já vista é retida (monotônica na
mão). Troca de identidade de mão REINICIA (não contamina). PURO: sem captura.
"""
from strategy.scenarios import classify, from_table_state

# Posto de AGRESSÃO do cenário: só sobe dentro de uma mão (um pote não "des-abre").
_RANK = {'pending': -1, 'unopened': 0, 'limped': 1, 'open': 2, 'open_with_callers': 2,
         'limp_then_iso': 3, 'threebet_cold': 4, 'vs_3bet': 4, 'vs_4bet_or_more': 5}


def _score(scn):
    base = _RANK.get(scn.get('scenario'), 0) * 10
    return base + scn.get('n_raises', 0) * 3 + scn.get('n_limpers', 0)


class ContinuousObserver:
    """Rastreia o cenário corrente por identidade de mão, de forma barata e sem
    perder história. `observe(identity, table_state)` atualiza e devolve o cenário
    efetivo; `scenario(identity)` relê; `forget(identity)` descarta."""

    def __init__(self):
        self._by_id = {}            # identity -> cenário efetivo (dict do classify)

    def observe(self, identity, table_state):
        cur = classify(from_table_state(table_state))
        prev = self._by_id.get(identity)
        if prev is not None and _score(cur) < _score(prev):
            # Frame regrediu (provável leitura perdida): RETÉM a história já vista.
            effective = dict(prev, retained_history=True)
        else:
            effective = cur
        self._by_id[identity] = effective
        return effective

    def scenario(self, identity):
        return self._by_id.get(identity)

    def forget(self, identity):
        self._by_id.pop(identity, None)

    def reset(self):
        self._by_id.clear()
