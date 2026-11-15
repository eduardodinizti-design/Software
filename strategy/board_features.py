"""Board/range diagnostics. Showdown equity is not the EV of a bet."""
from collections import defaultdict
from itertools import combinations
import random

from preflop_equity import eval7, parse_card
from postflop_eval import classify_board, hand_strength
from strategy.range_catalog import DECK, DealSampler, combo_cards
from strategy.state_contract import cards


def describe(board):
    board = cards(board, (3, 4, 5))
    return dict(cards=list(board), texture=classify_board(list(board)))


def range_distribution(range_, board):
    range_ = range_.without(board)
    categories = defaultdict(float)
    for combo, w in range_.weights:
        categories[hand_strength(list(combo_cards(combo)), list(board))['made']] += w / range_.mass
    return dict(categories)


def nuts_reference(board):
    parsed = [parse_card(c) for c in board]
    scores = sorted(eval7(parsed + [parse_card(a), parse_card(b)])
                    for a, b in combinations([c for c in DECK if c not in board], 2))
    return scores[-1], scores[int(.95 * (len(scores) - 1))]


def range_strength_features(range_, board, reference):
    range_ = range_.without(board)
    categories, draws = defaultdict(float), defaultdict(float)
    nuts, upper_tail = reference
    nuts_mass, tail_mass = 0.0, 0.0
    for combo, w in range_.weights:
        hand = list(combo_cards(combo))
        p = w / range_.mass
        strength = hand_strength(hand, list(board))
        categories[strength['made']] += p
        for name, value in strength['draws'].items():
            if isinstance(value, bool) and value:
                draws[name] += p
        score = eval7([parse_card(c) for c in hand + list(board)])
        nuts_mass += p * (score == nuts)
        tail_mass += p * (score >= upper_tail)
    return dict(categories=dict(categories), draw_mass=dict(draws),
                current_absolute_nuts_mass=nuts_mass, common_upper_tail_mass=tail_mass,
                tail_reference='95th percentile uniform legal physical combos; includes threshold ties')


def compare_distributions(ranges, board, *, samples=20000, seed=0):
    board = cards(board, (3, 4, 5))
    if type(samples) is not int or samples <= 0:
        raise ValueError('POSITIVE_SAMPLE_COUNT_REQUIRED')
    sampler, rng = DealSampler(ranges, board), random.Random(seed)
    total, squares = 0.0, 0.0
    for _ in range(samples):
        hands, runout = sampler.sample(rng)
        scores = [eval7([parse_card(c) for c in tuple(h) + board + runout]) for h in hands]
        x = float(scores[0] > scores[1]) + 0.5 * float(scores[0] == scores[1])
        total += x
        squares += x * x
    mean = total / samples
    stderr = (max(0, squares / samples - mean * mean) / samples) ** 0.5
    reference = nuts_reference(board)
    features = [range_strength_features(r, board, reference) for r in ranges]
    return dict(board=list(board), equity_player0=mean,
                mc_ci95=[max(0, mean - 1.96 * stderr), min(1, mean + 1.96 * stderr)],
                samples=samples, seed=seed,
                categories=[f['categories'] for f in features], range_features=features,
                range_sha256=[r.fingerprint for r in ranges],
                method='weighted_joint_deals_showdown_only_not_action_ev')
