"""Observe confirmed actions, update BOTH public ranges and advance the hand."""
from strategy.action_tree import apply_action, legal_actions
from strategy.state_contract import StrategyError, reveal


class LinePolicy:
    def __init__(self, policy):
        self.policy = policy
        self.state = policy.root
        self.ranges = tuple(r.without(self.state.board) for r in policy.ranges)
        self.trace = []

    def observe(self, action):
        if action.id not in {a.id for a in self.policy.actions(self.state)}:
            raise StrategyError('ACTION_OUTSIDE_COMPILED_TREE')
        actor = self.state.actor
        likelihoods = {}
        node = self.policy.nodes[self.policy.node_key(self.state)]
        for combo, _ in self.ranges[actor].weights:
            row = node['combos'].get(combo)
            if row is None:
                raise StrategyError('POLICY_COMBO_MISS_OR_OFF_POLICY')
            likelihoods[combo] = row['frequencies'][action.id]
        # Compute every result first: a missing row/zero reach never half-mutates the hand.
        updated = self.ranges[actor].posterior(likelihoods, self.state.key() + ':' + action.id)
        next_state = apply_action(self.state, action)
        ranges = list(self.ranges)
        before = ranges[actor]
        ranges[actor] = updated
        self.trace.append(dict(node_id=self.state.key(), actor=actor, action_id=action.id,
                               before_sha256=before.fingerprint, after_sha256=updated.fingerprint,
                               mass_before=before.mass, mass_after=updated.mass))
        self.state, self.ranges = next_state, tuple(ranges)
        return self

    def reveal(self, next_card):
        state = reveal(self.state, next_card)
        ranges = tuple(r.without(state.board) for r in self.ranges)
        self.state, self.ranges = state, ranges
        return self
