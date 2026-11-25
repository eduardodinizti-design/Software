"""Alargar o OPEN pra CAÇAR bounty (PKO), BOUNDED — platform-neutral (Suprema + PPPoker).

Princípio (igual ao exploit de HUD [[nvt-exploit-preflop-hud]]): o GTO é a base; isto é um DELTA
por cima que SÓ promove mãos que o GTO JÁ abre em frequência MISTA (raise>=MIN_MIX). Nunca abre
uma mão fora do range. Gatilho: há INCENTIVO de caça = um vilão CURTO que o HERO COBRE e que tem
BOUNTY na cabeça (state['bounties']) — abrir mais largo deixa a gente isolar/stack-off e levar o
bounty. O call largo já vem do call-off (scale_bounty_bb); aqui é só o OPEN.

Puro: não lê tela, não clica. Advisory (caveat BOUNTY_OPEN_WIDEN)."""
from __future__ import annotations

MIN_MIX = 0.10           # só promove se o GTO abre a mão em >= 10% (borderline)
SHORT_BB = 20.0          # vilão "curto" (alvo de caça) por padrão
MAX_TO_CALL_OPEN = 1.0   # spot de OPEN = enfrenta só os blinds (to_call <= 1bb)


def _freq(mix, action):
    for m in (mix or []):
        if m.get('action') == action:
            try:
                return float(m.get('frequency') or 0.0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def has_hunt_incentive(state, *, short_bb=SHORT_BB):
    """Há alvo de caça? vilão CURTO (<=short_bb) que o HERO COBRE e com BOUNTY (>0) na cabeça."""
    seats = (state or {}).get('seats') or {}
    bounties = (state or {}).get('bounties') or {}
    hero = (seats.get('hero') or {}).get('stack_bb')
    if not isinstance(hero, (int, float)):
        return False
    for k, s in seats.items():
        if k == 'hero' or not isinstance(s, dict):
            continue
        vb, vs = bounties.get(k), s.get('stack_bb')
        if (isinstance(vb, (int, float)) and vb > 0
                and isinstance(vs, (int, float)) and vs <= short_bb and hero >= vs):
            return True
    return False


def widen_open(advice, state, *, incentive=None, short_bb=SHORT_BB):
    """Em spot de OPEN (pré-flop, to_call só os blinds) com incentivo de caça, promove fold->raise
    SE o GTO abre a mão em freq mista (raise>=MIN_MIX). Senão, inalterada. BOUNDED."""
    if not isinstance(advice, dict) or advice.get('status') != 'ADVICE':
        return advice
    if advice.get('recommended') != 'fold':
        return advice
    board = (state or {}).get('board') or []
    tocall = ((state or {}).get('to_call') or {}).get('to_call_bb')
    if board or (isinstance(tocall, (int, float)) and tocall > MAX_TO_CALL_OPEN):
        return advice                                    # não é spot de OPEN
    inc = has_hunt_incentive(state, short_bb=short_bb) if incentive is None else incentive
    if not inc:
        return advice
    if _freq(advice.get('mix'), 'raise') < MIN_MIX:      # GTO nem abre misto -> não força
        return advice
    return dict(advice, recommended='raise',
                exploit=dict(base='fold', to='raise', reason='BOUNTY_OPEN_WIDEN'),
                caveats=list(advice.get('caveats') or []) + ['BOUNTY_OPEN_WIDEN'])
