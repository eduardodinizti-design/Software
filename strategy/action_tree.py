"""HU no-limit betting transitions, separate from the solver's declared menu."""
from dataclasses import asdict, dataclass, replace
import math

from strategy.state_contract import BettingState, StrategyError, money

EPS = 1e-7


@dataclass(frozen=True)
class Action:
    kind: str
    amount_bb: float = 0.0  # additional contribution, NEVER ambiguous raise-to

    def __post_init__(self):
        if self.kind not in ('fold', 'check', 'call', 'bet', 'raise', 'all_in'):
            raise StrategyError('UNKNOWN_ACTION')
        object.__setattr__(self, 'amount_bb', money(self.amount_bb))

    @property
    def id(self):
        return self.kind + ':' + format(self.amount_bb, '.9f').rstrip('0').rstrip('.')

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class BetMenu:
    fractions: tuple = (1 / 3, 2 / 3)
    max_raises: int = 2
    include_all_in: bool = True

    def __post_init__(self):
        object.__setattr__(self, 'fractions', tuple(self.fractions))
        if not self.fractions or any(not isinstance(f, (int, float)) or not math.isfinite(f) or f <= 0
                                     for f in self.fractions):
            raise StrategyError('INVALID_BET_MENU')
        if type(self.max_raises) is not int or self.max_raises < 0:
            raise StrategyError('INVALID_TREE_RAISE_BUDGET')
        if type(self.include_all_in) is not bool:
            raise StrategyError('INVALID_ALL_IN_OPTION')


def is_legal(state, action):
    if state.terminal or state.needs_cards:
        return False
    a, b = state.actor, 1 - state.actor
    price = state.call_required_bb
    paid = action.amount_bb
    if action.kind == 'fold':
        return price > EPS and paid == 0
    if action.kind == 'check':
        return price <= EPS and paid == 0
    if action.kind == 'call':
        return price > EPS and abs(paid - state.call_cost_bb) < EPS
    if paid <= price + EPS or paid > state.stacks[a] + EPS or not state.raise_rights[a]:
        return False
    if state.stacks[b] <= EPS:
        return False
    all_in = abs(paid - state.stacks[a]) < EPS
    if action.kind == 'all_in':
        if not all_in:
            return False
    elif all_in or action.kind != ('raise' if price > EPS else 'bet'):
        return False
    # Full raise size is measured above the previous HIGH commitment.
    increment = state.committed[a] + paid - max(state.committed)
    minimum = state.last_full_raise_bb if max(state.committed) > EPS else state.min_bet_bb
    return all_in or increment + EPS >= minimum


def legal_actions(state, menu):
    """Available actions IN THIS ABSTRACTION; is_legal covers the actual game."""
    if state.terminal or state.needs_cards:
        return ()
    price, actor = state.call_required_bb, state.actor
    out = [Action('fold'), Action('call', state.call_cost_bb)] if price > EPS else [Action('check')]
    # max_raises is an explicit offline tree budget, never a real stack/depth veto.
    if price <= EPS or state.raises < menu.max_raises:
        for fraction in menu.fractions:
            # Pot raise: call + fraction*(pot already on table + call).
            paid = price + fraction * (state.pot_bb + price) if price > EPS else fraction * state.pot_bb
            action = Action('raise' if price > EPS else 'bet', paid)
            if is_legal(state, action):
                out.append(action)
        if menu.include_all_in:
            action = Action('all_in', state.stacks[actor])
            if is_legal(state, action):
                out.append(action)
    return tuple({a.id: a for a in out}.values())


def _end_round(state):
    committed, stacks, pot = list(state.committed), list(state.stacks), state.pot_bb
    if min(stacks) <= EPS:
        # Return unmatched chips before running out; no imaginary side pot in HU.
        high = 0 if committed[0] > committed[1] else 1
        refund = max(0.0, committed[high] - committed[1 - high])
        stacks[high] += refund
        committed[high] -= refund
        pot -= refund
    return replace(state, pot_bb=pot, stacks=tuple(stacks), committed=(0.0, 0.0),
                   actor=state.oop, acted=(False, False), raise_rights=(True, True),
                   raises=0, last_full_raise_bb=state.min_bet_bb,
                   terminal='showdown' if len(state.board) == 5 else '',
                   needs_cards=int(len(state.board) < 5))


def apply_action(state, action):
    if not is_legal(state, action):
        raise StrategyError('ILLEGAL_ACTION:' + action.id)
    a, b = state.actor, 1 - state.actor
    history = state.history + (str(a) + ':' + action.id,)
    if action.kind == 'fold':
        return replace(state, history=history, terminal='fold', winner=b)
    if action.kind == 'check':
        acted = list(state.acted)
        acted[a] = True
        result = replace(state, actor=b, acted=tuple(acted), history=history)
        return _end_round(result) if all(acted) else result
    stacks, committed = list(state.stacks), list(state.committed)
    stacks[a] = money(stacks[a] - action.amount_bb)
    old_high = max(committed)
    committed[a] = money(committed[a] + action.amount_bb)
    pot = money(state.pot_bb + action.amount_bb)
    if action.kind == 'call':
        result = replace(state, pot_bb=pot, stacks=tuple(stacks), committed=tuple(committed),
                         actor=b, history=history, terminal='showdown')
        return _end_round(result)
    increment = committed[a] - old_high
    minimum = state.last_full_raise_bb if old_high > EPS else state.min_bet_bb
    full = increment + EPS >= minimum
    acted = list(state.acted)
    rights = list(state.raise_rights)
    if full:
        acted = [False, False]
        rights[b] = True
    else:
        rights[b] = not state.acted[b]
    acted[a], rights[a] = True, False
    return replace(state, pot_bb=pot, stacks=tuple(stacks), committed=tuple(committed),
                   actor=b, history=history, acted=tuple(acted), raise_rights=tuple(rights),
                   raises=state.raises + 1,
                   last_full_raise_bb=increment if full else state.last_full_raise_bb)
