"""NUNCA dar WALK a um jogador SIT-OUT (LEI Eduardo, ver memória nvt-regra-sitout-nunca-walk)
— platform-neutral (Suprema + PPPoker), BOUNDED, advisory.

Um jogador SIT-OUT não é ameaça: ele AUTO-FOLDA a blind. Logo, num STEAL/BLIND-WAR em que a
ação fecharia só com jogadores SIT-OUT (o hero é first-in e os defensores que restam estão
TODOS sit-out), FOLDAR é regalar a blind a quem a largaria de graça. Aqui promovemos fold->raise
(ROUBA) com o size de open normal (o executor aplica o 2x).

Dispara SÓ quando TODAS valem:
  - a recomendação é FOLD (status ADVICE);
  - pré-flop (board vazio);
  - NÃO enfrenta aposta REAL (to_call <= 1bb): um raise só viria de um jogador ATIVO, e um
    sit-out nunca aposta — então to_call>1bb significa oponente ATIVO vivo;
  - NÃO resta nenhum oponente ATIVO vivo além do hero (`state['positions'] == {'hero'}`): quem
    ainda fecha a ação está sit-out e vai auto-foldar;
  - há ao menos um defensor SIT-OUT na mão (`state['sitout_positions']` não-vazio).

Se o hero enfrenta uma aposta REAL de um ATIVO, ou sobra QUALQUER oponente ATIVO, NÃO mexe
(sit-out não muda nada aí). Conservador: na dúvida, NÃO força (direção segura = perder um
roubo, nunca agir errado). Puro: não lê tela, não clica. Caveat NEVER_WALK_SITOUT_STEAL."""
from __future__ import annotations

MAX_TO_CALL_STEAL = 1.0   # first-in: enfrenta no MÁXIMO o big blind (sem raise de um ATIVO)
_BLINDS = ('SB', 'BB')
DEFEND_MIN_MIX = 0.10     # só promove o resteal se o GTO já 3beta a mão em >= 10% (borderline)


def is_sitout_walk_steal(state):
    """True se o spot é um STEAL onde os defensores que FECHAM a ação estão TODOS sit-out
    (e não há oponente ATIVO vivo) — ou seja, foldar seria dar WALK a quem auto-folda."""
    if not isinstance(state, dict):
        return False
    if state.get('board'):
        return False                                   # só pré-flop
    tocall = (state.get('to_call') or {}).get('to_call_bb')
    if isinstance(tocall, (int, float)) and tocall > MAX_TO_CALL_STEAL:
        return False                                   # enfrenta aposta REAL de um ATIVO
    positions = state.get('positions') or {}
    if 'hero' not in positions or set(positions) != {'hero'}:
        return False                                   # sobra oponente ATIVO vivo -> não é walk
    sitout = state.get('sitout_positions') or []
    return bool(sitout)                                # há defensor(es) sit-out p/ roubar


def never_walk_sitout(advice, state):
    """Promove fold->raise quando o único caminho é dar WALK a sit-out. Senão, inalterada.
    BOUNDED: só toca um FOLD; nunca um call/raise/check já recomendado."""
    if not isinstance(advice, dict) or advice.get('status') != 'ADVICE':
        return advice
    if advice.get('recommended') != 'fold':
        return advice
    if not is_sitout_walk_steal(state):
        return advice
    return dict(advice, recommended='raise',
                exploit=dict(base='fold', to='raise', reason='NEVER_WALK_SITOUT_STEAL'),
                caveats=list(advice.get('caveats') or []) + ['NEVER_WALK_SITOUT_STEAL'])


def _aggr_in_mix(mix):
    """Ação AGRESSIVA (three_bet/raise/all_in/four_bet) de MAIOR freq no mix, se >= DEFEND_MIN_MIX."""
    best, bf = None, 0.0
    for m in (mix or []):
        if not isinstance(m, dict) or m.get('action') not in ('three_bet', 'raise', 'all_in', 'four_bet'):
            continue
        try:
            f = float(m.get('frequency') or 0.0)
        except (TypeError, ValueError):
            f = 0.0
        if f > bf:
            best, bf = m.get('action'), f
    return best if bf >= DEFEND_MIN_MIX else None


def widen_defense_vs_sitout(advice, state):
    """PONTO 2 do sit-out (LEI Eduardo 24/11): o hero ENFRENTA um OPEN e há um BLIND SIT-OUT na mão
    (dead money que o opener ROUBA -> ele abre mais LARGO/FRACO). Contra isso o hero RE-STEALA mais
    largo: promove fold->3bet SE o GTO já 3beta a mão em freq mista (>=DEFEND_MIN_MIX). BOUNDED — nunca
    inventa um 3bet fora do range; na dúvida NÃO força. Espelha bounty_open.widen_open p/ a DEFESA."""
    if not isinstance(advice, dict) or advice.get('status') != 'ADVICE':
        return advice
    if advice.get('recommended') != 'fold':
        return advice
    if (state or {}).get('board'):
        return advice                                    # só pré-flop
    tocall = ((state or {}).get('to_call') or {}).get('to_call_bb')
    if not (isinstance(tocall, (int, float)) and tocall > MAX_TO_CALL_STEAL):
        return advice                                    # precisa ENFRENTAR um open real (raise > 1bb)
    if not any(p in _BLINDS for p in ((state or {}).get('sitout_positions') or [])):
        return advice                                    # sem blind sit-out = sem dead money extra
    act = _aggr_in_mix(advice.get('mix'))
    if not act:
        return advice                                    # GTO nem 3beta misto -> não resteala lixo
    return dict(advice, recommended=act,
                exploit=dict(base='fold', to=act, reason='SITOUT_DEAD_MONEY_WIDEN_RESTEAL'),
                caveats=list(advice.get('caveats') or []) + ['SITOUT_DEAD_MONEY_WIDEN_RESTEAL'])
