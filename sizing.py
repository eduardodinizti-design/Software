"""Founded raise-sizing heuristics for the preflop advice.

Sizes are NOT taken from the button label or from the pack's historical bets
(the handoff and the cursor spec both forbid that). They are standard MTT sizing
rules in big blinds, read from the live table (limpers, the opener's size,
position): a first proposal to calibrate with use. Every size states its basis
and whether it is a heuristic; folds/checks/calls/limps/all-ins are exact.
"""
# Big-blind sizing constants (with antes); a first proposal, tune with data.
OPEN_RAISE_BB = 2.2            # first-in open
ISO_ADD_PER_LIMPER_BB = 1.0   # add this per limper when isolating
THREEBET_IP_MULT = 3.0        # 3bet to ~3x the open, in position
THREEBET_OOP_MULT = 4.0       # ~4x out of position

# Postflop action order (SB first, BTN last = in position).
_POSTFLOP_ORDER = ('SB', 'BB', 'UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN')


def count_limpers(table_state):
    """Non-hero, non-blind seats that just called the BB (bet ~1bb)."""
    positions = table_state.get('positions') or {}
    n = 0
    for bet in (table_state.get('bets') or []):
        seat, amount = bet.get('seat'), bet.get('bet_bb')
        if seat == 'hero' or not isinstance(amount, (int, float)):
            continue
        if 0.9 <= amount <= 1.1 and positions.get(seat) not in ('BB', 'SB'):
            n += 1
    return n


def opener_raise_bb(table_state):
    """The largest non-hero bet above the BB = the opener's raise-to size, or None."""
    best = None
    for bet in (table_state.get('bets') or []):
        seat, amount = bet.get('seat'), bet.get('bet_bb')
        if seat == 'hero' or not isinstance(amount, (int, float)):
            continue
        if amount > 1.5 and (best is None or amount > best):
            best = amount
    return best


def in_position(hero_position, opener_position):
    """Will the hero act after the opener post-flop? (BTN last, blinds first.)"""
    if hero_position not in _POSTFLOP_ORDER or opener_position not in _POSTFLOP_ORDER:
        return True
    return _POSTFLOP_ORDER.index(hero_position) > _POSTFLOP_ORDER.index(opener_position)


def recommend_size(action, *, hero_stack_bb=None, to_call_bb=None, limpers=0,
                   opener_bb=None, ip=True):
    """{action, size_bb, basis, heuristic} for one action, or None for fold.

    Open/3bet are heuristic sizes; call/limp/all-in/check are exact amounts."""
    cap = hero_stack_bb if isinstance(hero_stack_bb, (int, float)) else None

    def capped(size):
        return round(min(size, cap), 1) if cap is not None else round(size, 1)

    if action in ('fold',):
        return None
    if action == 'check':
        return dict(action='check', size_bb=0.0, basis='check', heuristic=False)
    if action == 'call':
        return dict(action='call', size_bb=to_call_bb, basis='to_call', heuristic=False)
    if action == 'limp':
        return dict(action='limp', size_bb=capped(1.0), basis='bb', heuristic=False)
    if action == 'all_in':
        return dict(action='all_in', size_bb=cap, basis='stack', heuristic=False)
    if action in ('raise', 'open_raise'):
        size = OPEN_RAISE_BB + ISO_ADD_PER_LIMPER_BB * limpers
        return dict(action='raise', size_bb=capped(size), heuristic=True,
                    basis='open %.1fbb + %d limper(s)' % (OPEN_RAISE_BB, limpers))
    if action == 'three_bet':
        base = opener_bb if isinstance(opener_bb, (int, float)) else OPEN_RAISE_BB
        mult = THREEBET_IP_MULT if ip else THREEBET_OOP_MULT
        return dict(action='three_bet', size_bb=capped(base * mult), heuristic=True,
                    basis='3bet %.0fx open (%s)' % (mult, 'IP' if ip else 'OOP'))
    return None


def size_from_reading(action, table_state, hero_position, opener_position=None):
    """Convenience: build the context from a read_table_state result and size the action."""
    hero = (table_state.get('seats') or {}).get('hero', {})
    return recommend_size(action, hero_stack_bb=hero.get('stack_bb'),
                          to_call_bb=(table_state.get('to_call') or {}).get('to_call_bb'),
                          limpers=count_limpers(table_state),
                          opener_bb=opener_raise_bb(table_state),
                          ip=in_position(hero_position, opener_position) if opener_position else True)
