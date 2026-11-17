"""Three-player postflop laboratory: legal histories and side pots, not a solver.

Stable player identities are MP=0, BTN=1, BB=2, even after a fold. Amounts
are fractional BB, without site-specific odd-chip rounding. Nothing here
captures a screen, recommends an action, or sends gameplay input.
"""
from dataclasses import asdict, dataclass
import math

from preflop_equity import eval7, parse_card
from strategy.state_contract import StrategyError, card, cards, money

POSITIONS = ('MP', 'BTN', 'BB')
ORDER = (2, 0, 1)
EPS = 1e-8


@dataclass(frozen=True)
class MultiwayState:
    board: tuple
    stacks: tuple = (38., 38., 37.)
    contributions: tuple = (2., 2., 2.)
    dead_pot_bb: float = 1.5  # folded SB=.5, BBA=1; ante is NOT a live bet
    committed: tuple = (0., 0., 0.)
    folded: tuple = (False, False, False)
    pending: tuple = ORDER
    acted_to: tuple = (None, None, None)
    checked: tuple = (False, False, False)
    last_full_raise_bb: float = 1.
    phase: str = 'action'
    history: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, 'board', cards(self.board, (3, 4, 5)))
        for name in ('stacks', 'contributions', 'committed'):
            value = tuple(money(v) for v in getattr(self, name))
            if len(value) != 3:
                raise StrategyError('THREE_PLAYER_AMOUNTS_REQUIRED')
            object.__setattr__(self, name, value)
        for name in ('folded', 'checked'):
            value = tuple(getattr(self, name))
            if len(value) != 3 or any(type(v) is not bool for v in value):
                raise StrategyError('THREE_BOOLEAN_FLAGS_REQUIRED')
            object.__setattr__(self, name, value)
        object.__setattr__(self, 'dead_pot_bb', money(self.dead_pot_bb))
        object.__setattr__(self, 'last_full_raise_bb', money(self.last_full_raise_bb))
        if self.last_full_raise_bb <= 0:
            raise StrategyError('POSITIVE_FULL_RAISE_REQUIRED')
        acted = tuple(self.acted_to)
        if len(acted) != 3:
            raise StrategyError('THREE_ACTION_BASELINES_REQUIRED')
        object.__setattr__(self, 'acted_to', tuple(None if v is None else money(v) for v in acted))
        pending = tuple(self.pending)
        if (len(set(pending)) != len(pending)
                or any(type(i) is not int or i not in (0, 1, 2) for i in pending)):
            raise StrategyError('INVALID_PENDING_PLAYERS')
        if any(self.folded[i] or self.stacks[i] <= EPS for i in pending):
            raise StrategyError('FOLDED_OR_ALL_IN_PLAYER_CANNOT_ACT')
        object.__setattr__(self, 'pending', pending)
        object.__setattr__(self, 'history', tuple(self.history))
        if any(not isinstance(e, str) for e in self.history):
            raise StrategyError('INVALID_MULTIWAY_HISTORY')
        if any(c > t + EPS for c, t in zip(self.committed, self.contributions)):
            raise StrategyError('STREET_COMMITMENT_EXCEEDS_TOTAL_CONTRIBUTION')
        if self.phase not in ('action', 'deal', 'showdown', 'fold'):
            raise StrategyError('INVALID_MULTIWAY_PHASE')
        if (self.phase == 'action') != bool(pending):
            raise StrategyError('PENDING_ACTION_AND_PHASE_DISAGREE')
        if self.phase == 'deal' and len(self.board) == 5:
            raise StrategyError('CANNOT_DEAL_AFTER_RIVER')
        if self.phase == 'showdown' and len(self.board) != 5:
            raise StrategyError('SHOWDOWN_REQUIRES_FIVE_BOARD_CARDS')
        if self.phase == 'fold' and sum(not f for f in self.folded) != 1:
            raise StrategyError('FOLD_TERMINAL_REQUIRES_ONE_SURVIVOR')
        if sum(not f for f in self.folded) < 1:
            raise StrategyError('NO_SURVIVING_PLAYER')

    @property
    def pot_bb(self):
        return self.dead_pot_bb + sum(self.contributions)

    @property
    def actor(self):
        return self.pending[0] if self.pending else None

    @property
    def street(self):
        return {3: 'FLOP', 4: 'TURN', 5: 'RIVER'}[len(self.board)]

    @property
    def call_required_bb(self):
        if self.actor is None:
            return 0.
        return max(self.committed) - self.committed[self.actor]

    @property
    def call_cost_bb(self):
        return min(self.call_required_bb, self.stacks[self.actor]) if self.actor is not None else 0.

    @property
    def can_raise(self):
        i = self.actor
        if i is None or self.stacks[i] <= self.call_required_bb + EPS:
            return False
        if not any(j != i and not self.folded[j] and self.stacks[j] > EPS for j in range(3)):
            return False  # opponents already all-in; only call or fold remains
        baseline = self.acted_to[i]
        return (baseline is None or self.checked[i]
                or max(self.committed) - baseline >= self.last_full_raise_bb - EPS)

    def to_dict(self):
        return asdict(self)


def _finish_round(state, **changes):
    """Build a consistent phase before constructing the immutable next state."""
    value = state.to_dict()
    value.update(changes)
    alive = [i for i in range(3) if not value['folded'][i]]
    can_act = [i for i in alive if value['stacks'][i] > EPS]
    pending = tuple(i for i in value['pending'] if i in can_act)
    high = max(value['committed'])
    if len(alive) == 1:
        pending, phase = (), 'fold'
    elif len(can_act) <= 1:
        # A single player can still face a call, but cannot bet into a dry pot.
        pending = tuple(i for i in can_act if value['committed'][i] < high - EPS)
        phase = 'action' if pending else ('showdown' if len(value['board']) == 5 else 'deal')
    else:
        phase = 'action' if pending else ('showdown' if len(value['board']) == 5 else 'deal')
    value.update(pending=pending, phase=phase)
    return MultiwayState(**value)


def act(state, kind, to_bb=None):
    """Apply one CONFIRMED action. Raises are street totals, never added sizes."""
    if state.phase != 'action':
        raise StrategyError('NO_MULTIWAY_DECISION_PENDING')
    i = state.actor
    stacks, total, committed = list(state.stacks), list(state.contributions), list(state.committed)
    folded, acted, checked = list(state.folded), list(state.acted_to), list(state.checked)
    due, high = state.call_required_bb, max(committed)
    last_raise = state.last_full_raise_bb
    if kind not in ('check', 'fold', 'call', 'bet', 'raise'):
        raise StrategyError('UNKNOWN_MULTIWAY_ACTION')
    if kind in ('check', 'fold', 'call') and to_bb is not None:
        raise StrategyError('PASSIVE_ACTION_HAS_NO_RAISE_TO')
    paid = 0.
    if kind == 'check':
        if due > EPS:
            raise StrategyError('CANNOT_CHECK_FACING_BET')
    elif kind == 'fold':
        if due <= EPS:
            raise StrategyError('FREE_CHECK_MUST_NOT_BE_RECORDED_AS_FOLD')
        folded[i] = True
    elif kind == 'call':
        if due <= EPS:
            raise StrategyError('CANNOT_CALL_WITHOUT_BET')
        paid = min(stacks[i], due)
    else:
        if (kind == 'bet') != (high <= EPS):
            raise StrategyError('BET_VERSUS_RAISE_MISMATCH')
        if not state.can_raise:
            raise StrategyError('RAISE_NOT_REOPENED_OR_NO_OPPONENT_CAN_RESPOND')
        target = money(to_bb)
        paid = target - committed[i]
        if target <= high + EPS or paid > stacks[i] + EPS:
            raise StrategyError('RAISE_TO_OUTSIDE_STACK_OR_NOT_ABOVE_BET')
        increment = target - high
        if increment < last_raise - EPS and abs(paid - stacks[i]) > EPS:
            raise StrategyError('UNDER_MINIMUM_RAISE_REQUIRES_ALL_IN')
        if increment >= last_raise - EPS:
            last_raise = increment
    stacks[i] = round(stacks[i] - paid, 9)
    total[i] = round(total[i] + paid, 9)
    committed[i] = round(committed[i] + paid, 9)
    acted[i], checked[i] = committed[i], kind == 'check'
    if kind in ('bet', 'raise'):
        start = ORDER.index(i)
        order = ORDER[start + 1:] + ORDER[:start]
        pending = tuple(j for j in order if not folded[j] and stacks[j] > EPS)
    else:
        pending = state.pending[1:]
    event = f'{state.street}:{POSITIONS[i]}:{kind}:{committed[i]:.9f}'
    return _finish_round(state, stacks=tuple(stacks), contributions=tuple(total),
        committed=tuple(committed), folded=tuple(folded), acted_to=tuple(acted),
        checked=tuple(checked), last_full_raise_bb=last_raise,
        pending=pending, history=state.history + (event,))


def reveal(state, next_card):
    if state.phase != 'deal':
        raise StrategyError('BETTING_MUST_CLOSE_BEFORE_DEALING')
    c = card(next_card)
    if c in state.board:
        raise StrategyError('DUPLICATE_PUBLIC_CARD')
    pending = tuple(i for i in ORDER if not state.folded[i] and state.stacks[i] > EPS)
    return _finish_round(state, board=state.board + (c,), committed=(0., 0., 0.),
        acted_to=(None, None, None), checked=(False, False, False),
        last_full_raise_bb=1., pending=pending, history=state.history + ('BOARD:' + c,))


def action_menu(state, fractions=(1/3, 1/2, 2/3, 1.), raise_fractions=(1.,)):
    """Legal candidate sizes; this menu contains NO strategy frequencies."""
    if state.phase != 'action':
        return []
    out = [{'kind': 'fold'}, {'kind': 'call', 'cost_bb': state.call_cost_bb}] if state.call_required_bb > EPS else [{'kind': 'check'}]
    if not state.can_raise:
        return out
    high = max(state.committed)
    cap = state.committed[state.actor] + state.stacks[state.actor]
    minimum = high + state.last_full_raise_bb
    values = set()
    for fraction in fractions if high <= EPS else raise_fractions:
        if type(fraction) not in (int, float) or not math.isfinite(fraction) or fraction <= 0:
            raise StrategyError('INVALID_MULTIWAY_POT_FRACTION')
        # A pot raise includes the call BEFORE applying the raise fraction.
        target = high + fraction * (state.pot_bb + state.call_required_bb)
        values.add(round(min(cap, max(minimum, target)), 9))
    values.add(cap)
    for target in sorted(values):
        if target > high + EPS:
            out.append(dict(kind='bet' if high <= EPS else 'raise', to_bb=target,
                            all_in=abs(target - cap) <= EPS))
    return out


def settle(state, hands=None):
    """Award actual chip pots. No PKO/ICM utility is inferred from chip awards."""
    if state.phase not in ('showdown', 'fold'):
        raise StrategyError('TERMINAL_HISTORY_REQUIRED_FOR_PAYOUT')
    alive = [i for i in range(3) if not state.folded[i]]
    scores = {}
    if state.phase == 'showdown':
        if hands is None or len(hands) != 3:
            raise StrategyError('THREE_PRIVATE_HAND_SLOTS_REQUIRED')
        seen = set(state.board)
        for i, hand in enumerate(hands):
            if hand is None and state.folded[i]:
                continue
            private = cards(hand, (2,))
            if seen.intersection(private):
                raise StrategyError('PRIVATE_CARD_COLLISION')
            seen.update(private)
            if i in alive:
                scores[i] = eval7([parse_card(c) for c in private + state.board])
    payouts = [0., 0., 0.]
    layers, previous = [], 0.
    for level in sorted(set(v for v in state.contributions if v > EPS)):
        contributors = [i for i, v in enumerate(state.contributions) if v >= level - EPS]
        eligible = [i for i in contributors if not state.folded[i]]
        amount = (level - previous) * len(contributors)
        if not layers:
            amount += state.dead_pot_bb
        if not eligible:
            raise StrategyError('POT_LAYER_WITHOUT_ELIGIBLE_PLAYER')
        if state.phase == 'fold':
            winners = eligible
        else:
            best = max(scores[i] for i in eligible)
            winners = [i for i in eligible if scores[i] == best]
        for i in winners:
            payouts[i] += amount / len(winners)
        layers.append(dict(amount_bb=amount, eligible=eligible, winners=winners,
                           uncalled_return=len(contributors) == 1))
        previous = level
    if not layers:
        winners = alive if state.phase == 'fold' else [i for i in alive if scores[i] == max(scores.values())]
        for i in winners:
            payouts[i] += state.dead_pot_bb / len(winners)
        layers.append(dict(amount_bb=state.dead_pot_bb, eligible=alive, winners=winners, uncalled_return=False))
    if abs(sum(payouts) - state.pot_bb) > EPS:
        raise StrategyError('CHIP_CONSERVATION_FAILURE')
    return dict(payouts_bb=payouts, layers=layers, pot_bb=state.pot_bb,
                final_stacks_bb=[s + p for s, p in zip(state.stacks, payouts)],
                bounty_utility_calculated=False, odd_chip_rounding='FRACTIONAL_BB_LAB_ONLY')
