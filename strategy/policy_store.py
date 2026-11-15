"""Validated compiled policy lookup. No nearest-neighbor or hidden default fold."""
import gzip
import json
import math
from pathlib import Path

from strategy.action_tree import Action, BetMenu, is_legal, legal_actions
from strategy.range_catalog import ComboRange, combo_key
from strategy.state_contract import BettingState, GameContext, StrategyError, digest, validate_game


class CompiledPolicy:
    def __init__(self, data):
        if data.get('schema') != 'software.hu-policy.v1':
            raise StrategyError('UNKNOWN_POLICY_SCHEMA')
        self.context = GameContext(**data['context'])
        self.root = BettingState.from_dict(data['root'])
        validate_game(self.context, self.root)
        self.ranges = tuple(ComboRange.from_dict(r) for r in data['ranges'])
        if len(self.ranges) != 2:
            raise StrategyError('TWO_RANGES_REQUIRED')
        self.menu = BetMenu(**data['menu'])
        self.nodes, self.quality = data['nodes'], dict(data['quality'])
        self.native_menu = self.quality.get('method') == 'texassolver_discounted_cfr'
        self._flop_order_index = {}
        for key, node in self.nodes.items():
            state = BettingState.from_dict(node['state'])
            validate_game(self.context, state)
            normalized = state.flop_order_key()
            if normalized in self._flop_order_index and self._flop_order_index[normalized] != key:
                raise StrategyError('DUPLICATE_EQUIVALENT_PUBLIC_NODE')
            self._flop_order_index[normalized] = key
            actions = tuple(Action(**a) for a in node['actions']) if self.native_menu else legal_actions(state, self.menu)
            ids = tuple(a.id for a in actions)
            if (not actions or len(set(ids)) != len(ids) or any(not is_legal(state, a) for a in actions)
                    or key != state.key() or node['actions'] != [a.to_dict() for a in actions]):
                raise StrategyError('POLICY_PUBLIC_STATE_OR_ACTION_MISMATCH')
            valid_combos = dict(self.ranges[state.actor].without(state.board).weights)
            for combo, row in node['combos'].items():
                if combo != combo_key(combo) or combo not in valid_combos:
                    raise StrategyError('POLICY_COMBO_OUTSIDE_ARRIVAL')
                p = row['frequencies']
                if set(p) != set(ids) or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                           or not math.isfinite(v) or not 0 <= v <= 1 for v in p.values()):
                    raise StrategyError('INVALID_POLICY_DISTRIBUTION')
                if abs(sum(p.values()) - 1) > 1e-6:
                    raise StrategyError('POLICY_DISTRIBUTION_NOT_NORMALIZED')
                evs = row.get('action_ev_bb')
                if evs is not None and (set(evs) != set(ids) or any(
                        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                        for v in evs.values())):
                    raise StrategyError('INVALID_POLICY_EV')
        self.fingerprint = digest(data)
        self.data = data

    @classmethod
    def load(cls, path):
        opener = gzip.open if str(path).endswith('.gz') else open
        with opener(path, 'rt', encoding='utf-8') as f:
            return cls(json.load(f))

    def row(self, state, hand):
        key, combo = self.node_key(state), combo_key(hand)
        if combo not in self.nodes[key]['combos']:
            raise StrategyError('POLICY_COMBO_MISS_OR_OFF_POLICY')
        return self.nodes[key], self.nodes[key]['combos'][combo]

    def probabilities(self, state, hand):
        node, row = self.row(state, hand)
        return [row['frequencies'][a.id] for a in self.actions(state)]

    def actions(self, state):
        key = self.node_key(state)
        return tuple(Action(**a) for a in self.nodes[key]['actions'])

    def node_key(self, state):
        key = state.key()
        if key not in self.nodes:
            key = self._flop_order_index.get(state.flop_order_key())
        if key not in self.nodes:
            raise StrategyError('POLICY_PUBLIC_NODE_MISS')
        return key


def save_policy(data, path):
    # Validate before publishing. Atomic replace avoids a half-written policy.
    CompiledPolicy(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(temp, 'wt', encoding='utf-8') as f:
        json.dump(data, f, sort_keys=True, separators=(',', ':'), allow_nan=False)
    temp.replace(path)
