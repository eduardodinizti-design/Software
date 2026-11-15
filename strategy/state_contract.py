"""Explicit, immutable HU state. No OCR, input, inferred checks or depth buckets."""
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math

from preflop_equity import parse_card


class StrategyError(ValueError):
    pass


def money(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StrategyError('MONEY_MUST_BE_A_NUMBER')
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise StrategyError('INVALID_MONEY')
    return round(value, 9)


def card(text):
    rank, suit = parse_card(text)
    return '23456789TJQKA'[rank - 2] + suit


def cards(values, lengths):
    result = tuple(card(c) for c in values)
    if len(result) not in lengths or len(set(result)) != len(result):
        raise StrategyError('INVALID_OR_DUPLICATE_CARDS')
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class GameContext:
    positions: tuple
    pot_type: str = 'single_raised'
    mode: str = 'chip_ev'
    stage: str = 'mid'
    tournament_format: str = 'regular'
    dealt_players: int = 9
    arrival_id: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'positions', tuple(self.positions))
        if len(self.positions) != 2 or len(set(self.positions)) != 2 or not all(self.positions):
            raise StrategyError('TWO_DISTINCT_POSITIONS_REQUIRED')
        if self.mode != 'chip_ev' or self.tournament_format not in ('regular', 'freezeout'):
            raise StrategyError('HU_CHIP_EV_ONLY_NOT_PKO_OR_ICM')
        if not isinstance(self.dealt_players, int) or not 2 <= self.dealt_players <= 9:
            raise StrategyError('INVALID_DEALT_PLAYERS')
        if not self.arrival_id:
            raise StrategyError('ARRIVAL_MODEL_ID_REQUIRED')
        if any(p not in ('SB', 'BB', 'UTG', 'UTG1', 'UTG2', 'UTG+1', 'UTG+2',
                         'LJ', 'MP', 'MP1', 'MP2', 'HJ', 'CO', 'BTN') for p in self.positions):
            raise StrategyError('UNKNOWN_POSITION')

    @property
    def oop_player(self):
        order = {'SB': 0, 'BB': 1, 'UTG': 2, 'UTG1': 3, 'UTG+1': 3,
                 'UTG2': 4, 'UTG+2': 4, 'LJ': 5, 'MP': 5, 'MP1': 5,
                 'MP2': 6, 'HJ': 7, 'CO': 8, 'BTN': 9}
        if self.dealt_players == 2 and set(self.positions) == {'SB', 'BB'}:
            return self.positions.index('BB')
        return min((0, 1), key=lambda i: order[self.positions[i]])


@dataclass(frozen=True)
class BettingState:
    board: tuple
    pot_bb: float
    stacks: tuple
    committed: tuple = (0.0, 0.0)
    actor: int = 0
    oop: int = 0
    min_bet_bb: float = 1.0
    last_full_raise_bb: float = 1.0
    acted: tuple = (False, False)
    raise_rights: tuple = (True, True)
    raises: int = 0
    history: tuple = ()
    terminal: str = ''
    winner: int = -1
    needs_cards: int = 0

    def __post_init__(self):
        object.__setattr__(self, 'board', cards(self.board, (3, 4, 5)))
        for name in ('pot_bb', 'min_bet_bb', 'last_full_raise_bb'):
            object.__setattr__(self, name, money(getattr(self, name)))
        for name in ('stacks', 'committed'):
            value = tuple(money(v) for v in getattr(self, name))
            if len(value) != 2:
                raise StrategyError('HU_REQUIRES_TWO_STACKS')
            object.__setattr__(self, name, value)
        for name in ('acted', 'raise_rights'):
            value = tuple(getattr(self, name))
            if len(value) != 2 or any(type(v) is not bool for v in value):
                raise StrategyError('INVALID_BETTING_RIGHTS')
            object.__setattr__(self, name, value)
        object.__setattr__(self, 'history', tuple(self.history))
        if any(not isinstance(e, str) for e in self.history):
            raise StrategyError('INVALID_PUBLIC_HISTORY')
        if type(self.actor) is not int or type(self.oop) is not int or self.actor not in (0, 1) or self.oop not in (0, 1):
            raise StrategyError('INVALID_ACTOR_OR_ORDER')
        if self.pot_bb <= 0 or self.min_bet_bb <= 0 or self.last_full_raise_bb <= 0:
            raise StrategyError('NONPOSITIVE_POT_OR_MINIMUM')
        if sum(self.committed) > self.pot_bb + 1e-7:
            raise StrategyError('POT_MUST_INCLUDE_CURRENT_BETS')
        if not isinstance(self.raises, int) or self.raises < 0:
            raise StrategyError('INVALID_RAISE_COUNT')
        if self.terminal not in ('', 'fold', 'showdown'):
            raise StrategyError('INVALID_TERMINAL')
        if self.terminal == 'fold' and self.winner not in (0, 1):
            raise StrategyError('FOLD_REQUIRES_CONFIRMED_WINNER')
        if self.needs_cards not in (0, 1) or (self.needs_cards and len(self.board) == 5):
            raise StrategyError('INVALID_CHANCE_NODE')
        if not self.terminal and not self.needs_cards and self.stacks[self.actor] <= 0:
            raise StrategyError('ACTOR_HAS_NO_CHIPS')
        if (not self.terminal and not self.needs_cards and max(self.committed) == 0
                and self.actor != self.oop and not self.acted[self.oop]):
            raise StrategyError('IP_TURN_REQUIRES_CONFIRMED_OOP_CHECK')

    @property
    def street(self):
        return {3: 'FLOP', 4: 'TURN', 5: 'RIVER'}[len(self.board)]

    @property
    def call_required_bb(self):
        return max(0.0, self.committed[1 - self.actor] - self.committed[self.actor])

    @property
    def call_cost_bb(self):
        return min(self.call_required_bb, self.stacks[self.actor])

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**value)

    def key(self):
        # Only public data. Neither private hand nor unrevealed runout belongs here.
        return digest(self.to_dict())

    def flop_order_key(self):
        value = self.to_dict()
        # The three simultaneous flop cards are unordered; turn and river are not.
        # This does NOT permute suits or approximate a different board.
        value['board'] = sorted(self.board[:3]) + list(self.board[3:])
        return digest(value)


@dataclass(frozen=True)
class DecisionState:
    context: GameContext
    betting: BettingState
    hero_cards: tuple
    table_id: str
    hand_id: str
    revision: int = 0

    def __post_init__(self):
        validate_game(self.context, self.betting)
        object.__setattr__(self, 'hero_cards', cards(self.hero_cards, (2,)))
        if set(self.hero_cards) & set(self.betting.board):
            raise StrategyError('HERO_BOARD_COLLISION')
        if not self.table_id or not self.hand_id:
            raise StrategyError('CONFIRMED_TABLE_AND_HAND_REQUIRED')
        if self.betting.actor != 0:
            raise StrategyError('NOT_HERO_TURN')

    @classmethod
    def from_dict(cls, value):
        return cls(context=GameContext(**value['context']),
                   betting=BettingState.from_dict(value['betting']),
                   hero_cards=value['hero_cards'], table_id=value['table_id'],
                   hand_id=value['hand_id'], revision=value.get('revision', 0))

    def selection_id(self):
        # Frame number/revision is deliberately excluded: revisits do not re-roll.
        return digest([self.table_id, self.hand_id, asdict(self.context), self.betting.flop_order_key(),
                       sorted(self.hero_cards)])


def validate_game(context, state):
    if state.oop != context.oop_player:
        raise StrategyError('POSITION_AND_POSTFLOP_ORDER_MISMATCH')


def reveal(state, next_card):
    if not state.needs_cards:
        raise StrategyError('NOT_WAITING_FOR_PUBLIC_CARD')
    c = card(next_card)
    if c in state.board:
        raise StrategyError('DUPLICATE_PUBLIC_CARD')
    board = state.board + (c,)
    all_in = min(state.stacks) <= 1e-9
    return replace(state, board=board, needs_cards=int(all_in and len(board) < 5),
                   terminal='showdown' if all_in and len(board) == 5 else '',
                   actor=state.oop, history=state.history + ('BOARD:' + c,))
