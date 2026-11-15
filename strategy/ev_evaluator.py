"""Chance-sampled tabular CFR and independent fixed-policy evaluation, offline.

Both actors' information sets contain ONLY their own hand and visible history.
Private deals/runouts are environment data, never policy features. All legal
actions of the declared abstraction are traversed; no omniscient leaf maxima.
This prototype reports sampling/budget/coverage, not an unmeasured GTO claim.
"""
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import permutations
import random

from preflop_equity import eval7, parse_card
from strategy.action_tree import Action, BetMenu, apply_action, legal_actions
from strategy.range_catalog import DECK, DealSampler, combo_key, joint_deals
from strategy.state_contract import BettingState, StrategyError, reveal, validate_game


def advance(state, root_board, runout):
    while state.needs_cards:
        state = reveal(state, runout[len(state.board) - len(root_board)])
    return state


def terminal_utility(state, hands, root):
    """Player 0 zero-sum utility; add root.pot/2 for EV from the root node."""
    if not state.terminal:
        raise StrategyError('NONTERMINAL_PAYOFF')
    if state.terminal == 'fold':
        share = float(state.winner == 0)
    else:
        if len(state.board) != 5:
            raise StrategyError('SHOWDOWN_NEEDS_FIVE_PUBLIC_CARDS')
        scores = [eval7([parse_card(c) for c in tuple(h) + state.board]) for h in hands]
        share = 1.0 if scores[0] > scores[1] else 0.5 if scores[0] == scores[1] else 0.0
    return share * state.pot_bb - (root.stacks[0] - state.stacks[0]) - root.pot_bb / 2


@dataclass
class InfoSet:
    regrets: list
    strategy_sum: list
    visits: int = 0

    def current(self):
        positive = [max(0.0, r) for r in self.regrets]
        total = sum(positive)
        return [r / total for r in positive] if total > 0 else [1 / len(positive)] * len(positive)

    def average(self):
        total = sum(self.strategy_sum)
        return [p / total for p in self.strategy_sum] if total else self.current()


class TrainingBudget(StrategyError):
    pass


class CFRTrainer:
    def __init__(self, context, root, ranges, menu=None, *, seed=0, max_nodes=100000):
        validate_game(context, root)
        if type(max_nodes) is not int or max_nodes <= 0:
            raise StrategyError('POSITIVE_NODE_BUDGET_REQUIRED')
        if root.terminal or root.needs_cards:
            raise StrategyError('TRAINING_ROOT_MUST_BE_A_DECISION')
        self.context, self.root, self.ranges = context, root, tuple(ranges)
        self.menu = menu or BetMenu()
        self.sampler = DealSampler(ranges, root.board)
        self.rng = random.Random(seed)
        self.seed, self.max_nodes = seed, max_nodes
        self.nodes, self.infosets = {}, {}
        self.iterations = 0
        self.budget_exhausted = False
        self._state_keys, self._transitions = {}, {}
        self.unseen_evaluation_infosets = set()

    def _node(self, state):
        if state not in self._state_keys:
            if len(self.nodes) >= self.max_nodes:
                raise TrainingBudget('PUBLIC_NODE_BUDGET_EXHAUSTED')
            key = state.key()
            actions = legal_actions(state, self.menu)
            if not actions:
                raise StrategyError('EMPTY_ACTION_SET')
            self._state_keys[state] = key
            self.nodes[key] = (state, actions)
        return self._state_keys[state], self.nodes[self._state_keys[state]][1]

    def _walk(self, state, hands, runout, reach, deltas):
        state = advance(state, self.root.board, runout)
        if state.terminal:
            return terminal_utility(state, hands, self.root)
        key, actions = self._node(state)
        actor = state.actor
        info_key = (key, combo_key(hands[actor]))
        info = self.infosets.setdefault(info_key, InfoSet([0.0] * len(actions), [0.0] * len(actions)))
        strategy = info.current()
        values = []
        for i, action in enumerate(actions):
            transition_key = (key, action.id)
            if transition_key not in self._transitions:
                self._transitions[transition_key] = apply_action(state, action)
            next_reach = list(reach)
            next_reach[actor] *= strategy[i]
            values.append(self._walk(self._transitions[transition_key], hands, runout, next_reach, deltas))
        value = sum(p * v for p, v in zip(strategy, values))
        sign = 1 if actor == 0 else -1
        regrets, averages, count = deltas.setdefault(info_key, ([0.0] * len(actions), [0.0] * len(actions), [0]))
        for i in range(len(actions)):
            regrets[i] += reach[1 - actor] * sign * (values[i] - value)
            averages[i] += reach[actor] * strategy[i]
        count[0] += 1
        return value

    def train(self, iterations):
        if type(iterations) is not int or iterations <= 0:
            raise StrategyError('POSITIVE_INTEGER_ITERATIONS_REQUIRED')
        for _ in range(iterations):
            hands, runout = self.sampler.sample(self.rng)
            deltas = {}
            try:
                self._walk(self.root, hands, runout, (1.0, 1.0), deltas)
            except TrainingBudget:
                # Do not apply an incomplete traversal or call it an iteration.
                self.budget_exhausted = True
                break
            for key, (regrets, averages, count) in deltas.items():
                info = self.infosets[key]
                info.regrets = [a + b for a, b in zip(info.regrets, regrets)]
                info.strategy_sum = [a + b for a, b in zip(info.strategy_sum, averages)]
                info.visits += count[0]
            self.iterations += 1
        return self

    def probabilities(self, state, hand):
        key = (state.key(), combo_key(hand))
        if key not in self.infosets or self.infosets[key].visits == 0:
            self.unseen_evaluation_infosets.add(key)
            return [1 / len(legal_actions(state, self.menu))] * len(legal_actions(state, self.menu))
        return self.infosets[key].average()

    def export(self):
        nodes = {}
        for (key, combo), info in self.infosets.items():
            if not info.visits:
                continue
            state, actions = self.nodes[key]
            if key not in nodes:
                nodes[key] = {'state': state.to_dict(), 'actions': [a.to_dict() for a in actions], 'combos': {}}
            nodes[key]['combos'][combo] = {
                'frequencies': dict(zip((a.id for a in actions), info.average())),
                'visits': info.visits, 'action_ev_bb': None}
        return {
            'schema': 'software.hu-policy.v1', 'context': asdict(self.context),
            'root': self.root.to_dict(), 'menu': asdict(self.menu),
            'ranges': [r.to_dict() for r in self.ranges],
            'quality': {'method': 'chance_sampled_cfr_full_action_traversal', 'iterations': self.iterations,
                        'seed': self.seed, 'public_nodes': len(nodes), 'information_sets': len(self.infosets),
                        'budget_exhausted': self.budget_exhausted, 'converged': False,
                        'global_gap_bb': None, 'windows_validated': False,
                        'unseen_combo_or_public_node': 'POLICY_MISS_NO_NEAREST_NEIGHBOR',
                        'training_ev_is_final_policy_ev': False},
            'nodes': nodes,
        }


def evaluate_profile(root, ranges, menu, probability, *, samples=2000, seed=9281, exact_river=False,
                     actions_fn=None, exact_runouts=False, max_exact_deals=20000):
    """Evaluate a FROZEN profile. Actor access is (visible state, own hand) only.

    Returns conditional counterfactual action EVs, not training-time maxima.
    Exact river enumeration is independent of the trainer's chance sampling.
    """
    values = defaultdict(lambda: {'weight': 0.0, 'reach': 0.0, 'count': 0, 'sum': None})
    rng = random.Random(seed)
    exact = exact_river or exact_runouts
    if exact_river:
        if len(root.board) != 5:
            raise StrategyError('EXACT_ENUMERATION_IS_RIVER_ONLY')
        deals = ((hands, (), w) for hands, w in joint_deals(ranges, root.board))
    elif exact_runouts:
        def all_deals():
            for hands, w in joint_deals(ranges, root.board):
                dead = set(root.board + hands[0] + hands[1])
                live = [c for c in DECK if c not in dead]
                for runout in permutations(live, 5 - len(root.board)):
                    yield hands, runout, w
        deals = all_deals()
    else:
        if type(samples) is not int or samples <= 0:
            raise StrategyError('POSITIVE_EVALUATION_SAMPLE_COUNT_REQUIRED')
        sampler = DealSampler(ranges, root.board)
        deals = ((*sampler.sample(rng), 1.0) for _ in range(samples))
    cache = {}

    def walk(state, hands, runout, reach, weight):
        state = advance(state, root.board, runout)
        if state.terminal:
            return terminal_utility(state, hands, root)
        if state not in cache:
            cache[state] = (state.key(), actions_fn(state) if actions_fn else legal_actions(state, menu))
        key, actions = cache[state]
        actor = state.actor
        probs = probability(state, hands[actor])
        if len(probs) != len(actions) or abs(sum(probs) - 1) > 1e-6 or any(p < 0 for p in probs):
            raise StrategyError('INVALID_BEHAVIORAL_POLICY')
        action_values = []
        for action, p in zip(actions, probs):
            next_reach = list(reach)
            next_reach[actor] *= p
            action_values.append(walk(apply_action(state, action), hands, runout, next_reach, weight))
        target = values[(key, combo_key(hands[actor]))]
        counterfactual_weight = weight * reach[1 - actor]
        if target['sum'] is None:
            target['sum'] = [0.0] * len(actions)
        # Shift zero-sum root utility to this actor's EV from the CURRENT node.
        shift = root.pot_bb / 2 + root.stacks[actor] - state.stacks[actor]
        sign = 1 if actor == 0 else -1
        for i, value in enumerate(action_values):
            target['sum'][i] += counterfactual_weight * (sign * value + shift)
        target['weight'] += counterfactual_weight
        target['reach'] += weight * reach[0] * reach[1]
        target['count'] += 1
        return sum(p * v for p, v in zip(probs, action_values))

    weighted_value, weighted_squares, total, count = 0.0, 0.0, 0.0, 0
    for hands, runout, weight in deals:
        if exact and count >= max_exact_deals:
            raise StrategyError('EXACT_VALIDATION_DEAL_BUDGET_EXHAUSTED_NO_PARTIAL_EV')
        value = walk(root, hands, runout, (1.0, 1.0), weight)
        weighted_value += weight * value
        weighted_squares += weight * value * value
        total += weight
        count += 1
    if not total:
        raise StrategyError('NO_EVALUATION_DEALS')
    mean = weighted_value / total + root.pot_bb / 2
    stderr = None if exact else (max(0.0, weighted_squares / total - (weighted_value / total)**2) / count)**.5
    return {'root_ev_player0_bb': mean,
            'mc_stderr_bb': stderr, 'mc_ci95_bb': None if stderr is None else [mean - 1.96 * stderr, mean + 1.96 * stderr],
            'method': ('exact_river_enumeration' if exact_river else 'exact_joint_deals_and_ordered_runouts')
                      if exact else 'independent_monte_carlo_frozen_profile',
            'deals': count, 'seed': None if exact else seed,
            'rows': {key: {'action_ev_bb': [s / v['weight'] for s in v['sum']],
                           'deals': v['count'], 'profile_reach_probability': v['reach'] / total}
                     for key, v in values.items() if v['weight'] > 0}}


def attach_evaluation(bundle, evaluation):
    """Only attach EVs actually evaluated under the frozen exported profile."""
    matched = 0
    for (key, combo), result in evaluation['rows'].items():
        if key in bundle['nodes'] and combo in bundle['nodes'][key]['combos']:
            node = bundle['nodes'][key]
            node['combos'][combo]['action_ev_bb'] = dict(zip(
                (Action(**a).id for a in node['actions']), result['action_ev_bb']))
            node['combos'][combo]['evaluation_deals'] = result['deals']
            node['combos'][combo]['evaluation_method'] = evaluation['method']
            node['combos'][combo]['profile_reach_probability'] = result['profile_reach_probability']
            matched += 1
    bundle['evaluation'] = {k: v for k, v in evaluation.items() if k != 'rows'}
    bundle['evaluation']['matched_information_sets'] = matched
    return bundle


def exact_river_gap(root, ranges, menu, probability, *, actions_fn=None):
    """Exact best responses WITHOUT seeing the opponent's private hand.

    The optimizing actor carries a belief over all compatible opponent combos.
    This is a gap in the declared river abstraction/ranges, not full-game GTO.
    """
    if len(root.board) != 5:
        raise StrategyError('GAP_ONLY_IMPLEMENTED_FOR_RIVER')
    return exact_hu_gap(root, ranges, menu, probability, actions_fn=actions_fn)


def exact_hu_gap(root, ranges, menu, probability, *, actions_fn=None, max_exact_deals=20000):
    """Independent small-game BR on any street, including hidden future cards.

    At a chance node, condition the opponent belief on the visible new card and
    its probability. The maximizing player never selects separately by a hidden
    runout. Computational limits fail explicitly, without returning partial gaps.
    """
    pairs = []
    runouts = 1
    for i in range(5 - len(root.board)):
        runouts *= 52 - len(root.board) - 4 - i
    for pair in joint_deals(ranges, root.board):
        if (len(pairs) + 1) * runouts > max_exact_deals:
            raise StrategyError('EXACT_GAP_DEAL_BUDGET_EXHAUSTED_NO_PARTIAL_GAP')
        pairs.append(pair)
    total = sum(w for _, w in pairs)
    if not total:
        raise StrategyError('NO_COMPATIBLE_JOINT_DEAL')

    def response(player, own, state, opponents):
        mass = sum(w for _, w in opponents)
        if mass <= 0:
            return 0.0
        if state.terminal:
            value = 0.0
            for opp, w in opponents:
                hands = (own, opp) if player == 0 else (opp, own)
                u = terminal_utility(state, hands, root)
                value += w * (u if player == 0 else -u)
            return value
        if state.needs_cards:
            value = 0.0
            denominator = 52 - len(state.board) - 4
            dead = set(state.board + own)
            for c in DECK:
                if c in dead:
                    continue
                posterior = [(opp, w / denominator) for opp, w in opponents if c not in opp]
                if posterior:
                    value += response(player, own, reveal(state, c), posterior)
            return value
        actions = actions_fn(state) if actions_fn else legal_actions(state, menu)
        if state.actor == player:
            # One action for the WHOLE opponent belief, never one per hidden hand.
            return max(response(player, own, apply_action(state, a), opponents) for a in actions)
        value = 0.0
        probs = [(opp, w, probability(state, opp)) for opp, w in opponents]
        for i, action in enumerate(actions):
            posterior = [(opp, w * p[i]) for opp, w, p in probs if p[i] > 0]
            value += response(player, own, apply_action(state, action), posterior)
        return value

    br_values = []
    for player in (0, 1):
        by_own = defaultdict(list)
        for hands, w in pairs:
            by_own[hands[player]].append((hands[1 - player], w))
        br_values.append(sum(response(player, own, root, opps) for own, opps in by_own.items()) / total)
    return {'method': 'exact_information_set_best_response_' + root.street.lower(),
            'nash_conv_bb': max(0.0, sum(br_values)),
            'exploitability_bb': max(0.0, sum(br_values) / 2),
            'best_response_centered_bb': br_values, 'joint_deals': len(pairs),
            'scope': 'declared_' + root.street.lower() + '_menu_ranges_and_future_streets_only',
            'joint_private_deals': len(pairs), 'joint_deals_including_ordered_runouts': len(pairs) * runouts}
