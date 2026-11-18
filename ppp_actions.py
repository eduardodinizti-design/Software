"""Enum de AÇÕES e STAGE do PPPoker (ActionBRC.actionType / RoundStartBRC.stage),
decodificado dos dados ao vivo (18/11, hook_sequence.js numa FT).

actionType (ActionBRC):
    1  = fold          (chips=0, encarando aposta)
    2  = check         (chips=0, callNeedChips=0)
    3  = call          (chips = callNeedChips)
    7  = bet/raise     (chips>0, abre/aumenta aposta; bet vs raise = pelo contexto da rua)
    8  = post SB       (chips = curBlind)
    9  = post BB       (chips = 2*curBlind)
    10 = post ante     (rajada após/junto do AnteBRC)
PENDENTE confirmar ao vivo: códigos distintos p/ RAISE e ALL-IN (candidatos 4/5/6, não
vistos ainda). Enquanto isso, 7 = agressão e all-in é inferido (chips atinge o stack /
isAllin no HandCardRSP). Blinds: curBlind (RoundStartBRC) = SB; BB = 2*curBlind.

stage (RoundStartBRC): 1=preflop 2=flop 3=turn 4=river.
"""
from __future__ import annotations

FOLD, CHECK, CALL = 'fold', 'check', 'call'
BET, RAISE, ALLIN = 'bets', 'raises', 'all-in'

# código bruto -> rótulo base
ACTION_TYPES = {
    1: 'fold',
    2: 'check',
    3: 'call',
    7: 'aggr',       # bet ou raise (decidir pelo contexto)
    8: 'post_sb',
    9: 'post_bb',
    10: 'post_ante',
}
POST_TYPES = {8, 9, 10}
AGGRESSIVE = {7}

STAGES = {1: 'preflop', 2: 'flop', 3: 'turn', 4: 'river'}


def is_post(action_type: int) -> bool:
    return int(action_type) in POST_TYPES


def stage_name(stage: int) -> str:
    return STAGES.get(int(stage), 'preflop')


def to_hh_action(action_type: int, chips: int, *, street_has_aggression: bool,
                 is_all_in: bool = False):
    """Converte (actionType, chips, contexto) numa ação de hand history.

    Devolve dict p/ emit_hand: {'action': ..., 'amount': ..., 'to': ...} ou None p/ posts
    (blinds/antes não são "ações" — vão em `posts`).
    street_has_aggression: já houve bet/raise nesta rua? (bet vs raise)
    """
    a = int(action_type)
    if a in POST_TYPES:
        return None
    label = ACTION_TYPES.get(a)
    if label == 'fold':
        return {'action': 'folds'}
    if label == 'check':
        return {'action': 'checks'}
    if label == 'call':
        return {'action': 'all-in' if is_all_in else 'calls', 'amount': int(chips)}
    if label == 'aggr' or a in AGGRESSIVE:
        if is_all_in:
            return {'action': 'all-in', 'amount': int(chips)}
        if street_has_aggression:
            return {'action': 'raises', 'to': int(chips)}
        return {'action': 'bets', 'amount': int(chips)}
    # desconhecido: registra cru p/ não perder a ação
    return {'action': f'action{a}', 'amount': int(chips)}
