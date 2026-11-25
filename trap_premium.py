"""TRAP pré-flop com PREMIUM vs resteal curto (LEI Eduardo 24/11) — platform-neutral, BOUNDED, advisory.

Spot: o hero está DEEP, enfrenta um OPEN-RAISE e segura AA/KK/QQ. Normalmente 3beta. MAS se há um
stack CURTO de RESTEAL (~12-25bb) ATRÁS do hero (tipicamente os blinds curtos) que o hero COBRE, a
jogada madura é FLAT (trap): induz o short a 3bet-SHOVAR um range mais fraco, e o hero ATOLA pré-flop
dominando. 3betar espantaria justamente o range fraco que queremos induzir.

Dispara SÓ quando TODAS valem (conservador — na dúvida NÃO trapa, perde-se só um trap, nunca erra):
  - recomendação é 3BET (raise/three_bet/all_in/*_shove), status ADVICE;
  - pré-flop (board vazio), enfrentando um OPEN real (1bb < to_call, aposta de 1 abridor);
  - mão PREMIUM (AA/KK/QQ) — as que o hero 3betaria;
  - hero DEEP (> RESTEAL_MAX_BB): flatar só faz sentido com stack p/ induzir e cobrir;
  - há >=1 oponente ATIVO ATRÁS do hero (age depois no pré) com stack de RESTEAL (RESTEAL_MIN..MAX)
    que o hero COBRE (hero_stack >= stack dele) — o induzido-a-shovar.

Não lê tela, não clica. Caveat TRAP_FLAT_PREMIUM_VS_RESTEAL."""
from __future__ import annotations

# ordem de AÇÃO pré-flop (quem age DEPOIS = está "atrás" e pode 3bet-shovar sobre o flat do hero)
_PREFLOP_ORDER = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')
_PREMIUM = frozenset({'AA', 'KK', 'QQ'})
_RANKS = 'AKQJT98765432'
RESTEAL_MIN_BB = 11.0        # abaixo disso é push/fold puro (não "resteal" clássico)
RESTEAL_MAX_BB = 25.0        # acima disso não é mais um shove-stack de resteal
_3BET_ACTIONS = frozenset({'raise', 'three_bet', 'all_in', 'open_shove',
                           'three_bet_shove', 'four_bet'})


def _premium_hand(cards):
    """'AA'/'KK'/'QQ' se for um par premium, senão None."""
    if not (isinstance(cards, (list, tuple)) and len(cards) == 2):
        return None
    r0, r1 = cards[0][0], cards[1][0]
    if r0 == r1 and (r0 + r1) in _PREMIUM:
        return r0 + r1
    return None


def should_trap(state, hero_cards):
    """True se é o spot de trap-flat (premium deep vs open com resteal curto atrás que o hero cobre)."""
    if not isinstance(state, dict) or state.get('board'):
        return False
    if _premium_hand(hero_cards) is None:
        return False
    tocall = (state.get('to_call') or {}).get('to_call_bb')
    if not (isinstance(tocall, (int, float)) and tocall > 1.0):
        return False                                   # precisa enfrentar um OPEN real
    positions = state.get('positions') or {}
    hero_pos = positions.get('hero')
    if hero_pos not in _PREFLOP_ORDER:
        return False
    seats = state.get('seats') or {}
    hero_stack = (seats.get('hero') or {}).get('stack_bb')
    if not isinstance(hero_stack, (int, float)) or hero_stack <= RESTEAL_MAX_BB:
        return False                                   # hero precisa estar DEEP p/ trapar e cobrir
    hi = _PREFLOP_ORDER.index(hero_pos)
    for seat, pos in positions.items():
        if seat == 'hero' or pos not in _PREFLOP_ORDER:
            continue
        if _PREFLOP_ORDER.index(pos) <= hi:
            continue                                   # não está ATRÁS do hero
        st = (seats.get(seat) or {}).get('stack_bb')
        if (isinstance(st, (int, float)) and RESTEAL_MIN_BB <= st <= RESTEAL_MAX_BB
                and hero_stack >= st - 1e-9):
            return True                                # short de resteal atrás que o hero cobre
    return False


def trap_flat(advice, state, hero_cards):
    """Promove 3bet->FLAT (call) quando é o spot de trap. Senão, inalterada. BOUNDED: só toca uma
    recomendação de 3BET; nunca um call/check/fold já recomendado."""
    if not isinstance(advice, dict) or advice.get('status') != 'ADVICE':
        return advice
    if advice.get('recommended') not in _3BET_ACTIONS:
        return advice
    if not should_trap(state, hero_cards):
        return advice
    return dict(advice, recommended='call',
                exploit=dict(base=advice.get('recommended'), to='call',
                             reason='TRAP_FLAT_PREMIUM_VS_RESTEAL'),
                caveats=list(advice.get('caveats') or []) + ['TRAP_FLAT_PREMIUM_VS_RESTEAL'])
