"""Detecta MESA BUSTADA (herói eliminado) em MODO OBSERVADOR — o caso em que o
herói já caiu e a mesa fica só sendo assistida, SEM o pop-up Ranking/Sair (esse é
tratado por table_reading/tournament_end.py). Ao cair, se o pop-up de recompra e o
Ranking já passaram, não há botão "Sair" — a mesa segue aberta à toa.

GATILHO LIMPO e à prova de falso-positivo (descoberto ao vivo 18/11/2026): a mesa
imprime "Minha posição: rank/restantes". Estando VIVO, rank <= restantes SEMPRE
(você não pode ser o 57º se só restam 52). Logo rank > restantes ⇒ JÁ CAIU.

Trava ABSOLUTA: qualquer sinal de vida (herói com cartas, ou botões de ação na
tela = é a vez dele) VETA o diagnóstico de bustado. Nunca fechar mesa viva.

Este módulo é PURO (sem captura/clique). A rotina que fecha (clica o X) e o
debounce de confirmação vivem no operar_mesa / BustedConfirmer abaixo.
"""
from __future__ import annotations


def detect_busted(hero_rank, players_left, *, hero_present=None, has_action=None):
    """Diagnostica se a mesa está BUSTADA (herói eliminado) a partir da leitura do
    torneio. Devolve dict(status, reason, confidence).

    status:
      - 'BUSTED'  : prova forte de eliminação (rank > restantes) e SEM sinal de vida.
      - 'ALIVE'   : rank <= restantes, ou há sinal de vida (veta qualquer bust).
      - 'UNKNOWN' : posição ilegível → abstém (não fecha nada).

    `hero_present`/`has_action`: sinais de vida (herói com cartas / é a vez dele).
    Se qualquer um for verdadeiro, NUNCA retorna BUSTED (trava de segurança)."""
    alive_signal = bool(has_action) or bool(hero_present)
    ok = (isinstance(hero_rank, int) and isinstance(players_left, int)
          and players_left > 0 and hero_rank > 0)
    if not ok:
        return dict(status='UNKNOWN', reason='POSITION_UNREADABLE', confidence='abstain')
    if hero_rank > players_left:
        if alive_signal:
            # leitura diz bustado mas há sinal de vida -> provável misread; VETA.
            return dict(status='ALIVE', reason='RANK_GT_LEFT_BUT_LIVE_SIGNAL',
                        confidence='veto')
        return dict(status='BUSTED', reason='RANK_GT_LEFT', confidence='high')
    return dict(status='ALIVE', reason='RANK_LE_LEFT', confidence='high')


class BustedConfirmer:
    """Debounce: só confirma BUSTED após `need` diagnósticos BUSTED consecutivos
    (por mesa), zerando a qualquer ALIVE. Um UNKNOWN (posição ilegível num frame)
    NÃO zera nem avança — mantém o progresso. Evita que um único misread de
    "rank/restantes" feche uma mesa. Uma vez confirmado e tratado, `mark_done()`
    impede re-fechar a mesma mesa."""

    def __init__(self, need: int = 3):
        self.need = max(1, int(need))
        self._streak: dict = {}
        self._done: set = set()

    def update(self, table_key, detection) -> bool:
        """Alimenta um diagnóstico de detect_busted p/ uma mesa. Devolve True só
        no momento em que a eliminação é CONFIRMADA (atingiu `need` seguidas e
        ainda não foi tratada)."""
        if table_key in self._done:
            return False
        status = (detection or {}).get('status')
        if status == 'ALIVE':
            self._streak[table_key] = 0
            return False
        if status != 'BUSTED':            # UNKNOWN: segura o progresso
            return False
        self._streak[table_key] = self._streak.get(table_key, 0) + 1
        return self._streak[table_key] >= self.need

    def mark_done(self, table_key) -> None:
        self._done.add(table_key)
        self._streak.pop(table_key, None)

    def is_done(self, table_key) -> bool:
        return table_key in self._done
