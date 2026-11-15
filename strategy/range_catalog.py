"""Physical combo distributions with immutable weights and source fingerprints."""
from bisect import bisect_left
from dataclasses import dataclass
from functools import cached_property
import itertools
import json
import math

from preflop_equity import FULL_DECK, hand_to_combos
from strategy.state_contract import StrategyError, card, digest

DECK = tuple('23456789TJQKA'[r - 2] + s for r, s in FULL_DECK)


def combo_key(values):
    if isinstance(values, str):
        values = values.split() if ' ' in values else (values[:2], values[2:])
    c = tuple(sorted(card(v) for v in values))
    if len(c) != 2 or c[0] == c[1]:
        raise StrategyError('INVALID_PHYSICAL_COMBO')
    return ''.join(c)


def combo_cards(key):
    return (key[:2], key[2:])


@dataclass(frozen=True)
class ComboRange:
    weights: tuple
    source_id: str

    def __post_init__(self):
        if not isinstance(self.source_id, str) or not self.source_id:
            raise StrategyError('RANGE_SOURCE_REQUIRED')
        merged = {}
        for k, w in self.weights:
            k = combo_key(k)
            if isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0:
                raise StrategyError('INVALID_RANGE_WEIGHT')
            if k in merged:
                raise StrategyError('DUPLICATE_RANGE_COMBO')
            if w:
                merged[k] = float(w)
        if not merged:
            raise StrategyError('EMPTY_RANGE')
        object.__setattr__(self, 'weights', tuple(sorted(merged.items())))

    @classmethod
    def from_classes(cls, frequencies, source_id):
        values = []
        for hand, freq in frequencies.items():
            if not isinstance(freq, (int, float)) or isinstance(freq, bool) or not math.isfinite(freq) or not 0 <= freq <= 1:
                raise StrategyError('INVALID_CLASS_FREQUENCY')
            if not isinstance(hand, str):
                raise StrategyError('INVALID_HAND_CLASS')
            hand = hand[:2].upper() + hand[2:].lower()
            ranks = '23456789TJQKA'
            if (len(hand) not in (2, 3) or any(c not in ranks for c in hand[:2])
                    or (len(hand) == 2 and hand[0] != hand[1])
                    or (len(hand) == 3 and (hand[0] == hand[1] or hand[2] not in 'so'))):
                raise StrategyError('INVALID_HAND_CLASS')
            for combo in hand_to_combos(hand):
                values.append((combo_key('23456789TJQKA'[r - 2] + s for r, s in combo), freq))
        return cls(tuple(values), source_id)

    @classmethod
    def from_dict(cls, value):
        return cls(tuple(value['weights'].items()), value['source_id'])

    def to_dict(self):
        return {'weights': dict(self.weights), 'source_id': self.source_id}

    @cached_property
    def mass(self):
        return sum(w for _, w in self.weights)

    @cached_property
    def fingerprint(self):
        return digest(self.to_dict())

    def without(self, dead):
        dead = set(card(c) for c in dead)
        return ComboRange(tuple((k, w) for k, w in self.weights if not dead.intersection(combo_cards(k))),
                          self.source_id)

    def probabilities(self):
        return {k: w / self.mass for k, w in self.weights}

    def posterior(self, likelihoods, event_id):
        values = []
        for k, w in self.weights:
            if k not in likelihoods:
                raise StrategyError('MISSING_ACTION_LIKELIHOOD:' + k)
            p = likelihoods[k]
            if not isinstance(p, (int, float)) or isinstance(p, bool) or not math.isfinite(p) or not 0 <= p <= 1:
                raise StrategyError('INVALID_ACTION_LIKELIHOOD')
            values.append((k, w * p))
        if not any(w > 0 for _, w in values):
            raise StrategyError('OFF_POLICY_ZERO_REACH_ACTION_REQUIRES_ARRIVAL_MODEL')
        return ComboRange(tuple(values), digest([self.fingerprint, event_id, likelihoods]))


class RangeCatalog:
    def __init__(self, records):
        self.records = dict(records)

    @classmethod
    def from_reference(cls, path):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return cls({name: ComboRange.from_classes(r['class_frequencies'],
                    digest([data['source'], r['node_id'], r['selected_action']]))
                    for name, r in data['ranges'].items()})

    def get(self, range_id):
        if range_id not in self.records:
            raise StrategyError('UNKNOWN_RANGE_ID:' + range_id)
        return self.records[range_id]


def joint_deals(ranges, board):
    """Exact product distribution conditioned on public and private collisions."""
    if len(ranges) != 2:
        raise StrategyError('TWO_RANGES_REQUIRED')
    left, right = (r.without(board) for r in ranges)
    for (a, wa), (b, wb) in itertools.product(left.weights, right.weights):
        if not set(combo_cards(a)).intersection(combo_cards(b)):
            yield (combo_cards(a), combo_cards(b)), wa * wb


class DealSampler:
    def __init__(self, ranges, board):
        if len(ranges) != 2:
            raise StrategyError('TWO_RANGES_REQUIRED')
        self.ranges = tuple(r.without(board) for r in ranges)
        self.board = tuple(board)
        self.cumulative = []
        for r in self.ranges:
            total, cum = 0.0, []
            for _, w in r.weights:
                total += w
                cum.append(total)
            self.cumulative.append(cum)
        if next(joint_deals(self.ranges, self.board), None) is None:
            raise StrategyError('NO_COMPATIBLE_JOINT_DEAL')

    def sample(self, rng):
        # Reject the ENTIRE pair: sequentially resampling only villain biases the prior.
        for _ in range(10000):
            hands = []
            for r, cum in zip(self.ranges, self.cumulative):
                i = min(len(cum) - 1, bisect_left(cum, rng.random() * cum[-1]))
                hands.append(combo_cards(r.weights[i][0]))
            if not set(hands[0]).intersection(hands[1]):
                break
        else:
            # Exact weighted fallback for pathological overlapping ranges.
            pairs = list(joint_deals(self.ranges, self.board))
            hands = rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs], k=1)[0]
        dead = set(self.board + tuple(hands[0]) + tuple(hands[1]))
        runout = tuple(rng.sample([c for c in DECK if c not in dead], 5 - len(self.board)))
        return tuple(hands), runout
