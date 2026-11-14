"""Vectorized exact hand ranking and collision-correct range dealing.

Ranks use category followed by five base-15 kickers, larger is better.
The independent scalar evaluator in preflop_equity is used for differential
tests. No hand-strength percentile is substituted for a showdown outcome.
"""
from itertools import combinations
import numpy as np

RANKS = '23456789TJQKA'
SUITS = 'shdc'
COMBOS = np.asarray(list(combinations(range(52), 2)), dtype=np.int16)
STRAIGHTS = np.zeros(8192, dtype=np.int16)
for mask in range(8192):
    if mask & 0x100F == 0x100F:
        STRAIGHTS[mask] = 5
    for high in range(6, 15):
        pattern = 31 << (high - 6)
        if mask & pattern == pattern:
            STRAIGHTS[mask] = high


def card_id(card):
    if not isinstance(card, str) or len(card) != 2 or card[0] not in RANKS or card[1] not in SUITS:
        raise ValueError('Invalid exact card: %r' % card)
    return RANKS.index(card[0]) * 4 + SUITS.index(card[1])


def card_text(card):
    return RANKS[int(card) // 4] + SUITS[int(card) % 4]


def hand_class(pair):
    a, b = sorted((int(pair[0]), int(pair[1])), key=lambda x: x // 4, reverse=True)
    ranks = RANKS[a // 4] + RANKS[b // 4]
    return ranks if a // 4 == b // 4 else ranks + ('s' if a % 4 == b % 4 else 'o')


COMBO_CLASSES = tuple(hand_class(c) for c in COMBOS)


def range_weights(weights):
    """A class weight is assigned to EACH physical combo, not divided by 4/6/12."""
    if not isinstance(weights, dict) or not weights:
        raise ValueError('An explicit nonempty class range is required.')
    unknown = set(weights) - set(COMBO_CLASSES)
    if unknown or any(type(v) not in (int, float) or not np.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError('Invalid range weights/classes.')
    result = np.asarray([weights.get(h, 0.) for h in COMBO_CLASSES], dtype=float)
    if not result.sum():
        raise ValueError('Empty range.')
    return result


def deal(hero, ranges, samples, seed):
    """Draw the joint product of ranges conditioned on all cards being distinct.

    Entire colliding joint deals are rejected. Sequentially normalizing each
    villain after the previous draw would bias the requested joint distribution.
    Boards are uniform conditional on every dealt hand, including later folds.
    """
    hero = np.asarray([card_id(c) for c in hero], dtype=np.int16)
    if hero.shape != (2,) or hero[0] == hero[1] or type(samples) is not int or samples < 2:
        raise ValueError('Two distinct hero cards and at least two samples are required.')
    if not 1 <= len(ranges) <= 8:
        raise ValueError('One to eight opponent ranges are required.')
    rng = np.random.default_rng(seed)
    probabilities = []
    for weights in ranges:
        w = range_weights(weights)
        w[np.isin(COMBOS, hero).any(axis=1)] = 0
        if not w.sum():
            raise ValueError('Range entirely blocked by hero.')
        probabilities.append(w / w.sum())
    accepted = []; count = attempted = 0
    limit = max(samples * 100, 100000)
    while count < samples and attempted < limit:
        n = min(max(128, 2 * (samples - count)), 16384, limit - attempted)
        hands = np.stack([COMBOS[rng.choice(len(COMBOS), n, p=w)] for w in probabilities], axis=1)
        flat = np.sort(hands.reshape(n, -1), axis=1)
        valid = ~np.any(np.diff(flat, axis=1) == 0, axis=1)
        accepted.append(hands[valid]); count += int(valid.sum()); attempted += n
    if count < samples:
        raise ValueError('Joint ranges are incompatible or rejection budget exhausted.')
    villains = np.concatenate(accepted, axis=0)[:samples]
    holes = np.concatenate((np.broadcast_to(hero, (samples, 1, 2)), villains), axis=1)
    # Independent continuous keys give a uniform permutation of the live deck.
    keys = rng.random((samples, 52))
    rows = np.arange(samples)[:, None]
    keys[rows, holes.reshape(samples, -1)] = 2.
    board = np.argsort(keys, axis=1)[:, :5].astype(np.int16)
    return holes, board, dict(attempted=attempted, accepted=count, requested=samples,
                             method='joint_rejection_product_ranges_then_uniform_board')


def evaluate(cards):
    """Exact rank of arrays (..., 5..7) without enumerating 21 five-card subsets."""
    c = np.asarray(cards, dtype=np.int16)
    if c.ndim < 2 or c.shape[-1] not in (5, 6, 7):
        raise ValueError('Expected batches of 5, 6 or 7 cards.')
    shape = c.shape[:-1]; c = c.reshape(-1, c.shape[-1])
    if np.any(c < 0) or np.any(c >= 52) or np.any(np.diff(np.sort(c, axis=1), axis=1) == 0):
        raise ValueError('Duplicate/invalid cards in evaluation.')
    ranks = c // 4 + 2; suits = c % 4
    counts = np.stack([(ranks == r).sum(axis=1) for r in range(2, 15)], axis=1)
    rr = np.arange(2, 15, dtype=np.int32)
    mask = ((counts > 0) * (1 << np.arange(13))).sum(axis=1).astype(np.int16)
    def top(eligible, n):
        vals = np.sort(np.where(eligible, rr, 0), axis=1)[:, -n:][:, ::-1]
        return vals
    def pack(cat, kickers):
        out = np.full(len(c), cat, dtype=np.int32)
        for j in range(5):
            out = out * 15 + (kickers[:, j] if j < kickers.shape[1] else 0)
        return out
    score = pack(0, top(counts > 0, 5))
    pairs = top(counts >= 2, 3); trips = top(counts >= 3, 2); quad = top(counts == 4, 1)
    kick = top((counts > 0) & (rr != pairs[:, :1]), 3)
    score = np.where(pairs[:, 0] > 0, pack(1, np.column_stack((pairs[:, 0], kick))), score)
    kick = top((counts > 0) & (rr != pairs[:, :1]) & (rr != pairs[:, 1:2]), 1)
    score = np.where(pairs[:, 1] > 0, pack(2, np.column_stack((pairs[:, :2], kick))), score)
    kick = top((counts > 0) & (rr != trips[:, :1]), 2)
    score = np.where(trips[:, 0] > 0, pack(3, np.column_stack((trips[:, 0], kick))), score)
    straight = STRAIGHTS[mask]
    score = np.where(straight > 0, pack(4, straight[:, None]), score)
    flush_score = np.zeros(len(c), dtype=np.int32); sf = np.zeros(len(c), dtype=np.int16)
    for suit in range(4):
        suited = (suits == suit)
        eligible = np.stack([((ranks == r) & suited).any(axis=1) for r in range(2, 15)], axis=1)
        enough = suited.sum(axis=1) >= 5
        flush_score = np.maximum(flush_score, np.where(enough, pack(5, top(eligible, 5)), 0))
        fmask = (eligible * (1 << np.arange(13))).sum(axis=1).astype(np.int16)
        sf = np.maximum(sf, np.where(enough, STRAIGHTS[fmask], 0))
    score = np.maximum(score, flush_score)
    house_pair = top((counts >= 2) & (rr != trips[:, :1]), 1)
    full = (trips[:, 0] > 0) & (house_pair[:, 0] > 0)
    score = np.where(full, pack(6, np.column_stack((trips[:, 0], house_pair[:, 0]))), score)
    kick = top((counts > 0) & (rr != quad), 1)
    score = np.where(quad[:, 0] > 0, pack(7, np.column_stack((quad, kick))), score)
    score = np.where(sf > 0, pack(8, sf[:, None]), score)
    return score.reshape(shape)


def made_features(holes, board):
    """Public board + OWN cards only. Never opponent cards or future board cards."""
    n, players, _ = holes.shape
    public = np.broadcast_to(board[:, None, :], (n, players, board.shape[1]))
    cards = np.concatenate((holes, public), axis=2)
    score = evaluate(cards); category = score // (15 ** 5)
    pair_rank = (score // (15 ** 4)) % 15
    board_high = np.max(board // 4 + 2, axis=1)[:, None]
    hole_ranks = holes // 4 + 2
    # A pair only on the board is not the same as a private top/overpair.
    private_pair = (category == 1) & (holes[:, :, 0] // 4 != holes[:, :, 1] // 4)
    private_pair &= (hole_ranks == pair_rank[:, :, None]).any(axis=2)
    pocket = (holes[:, :, 0] // 4 == holes[:, :, 1] // 4)
    top_pair = (category == 1) & ((private_pair & (pair_rank >= board_high)) |
                                  (pocket & (hole_ranks[:, :, 0] >= board_high)))
    flush_draw = np.zeros((n, players), dtype=bool)
    if board.shape[1] < 5:
        for suit in range(4):
            suited = (cards % 4 == suit)
            flush_draw |= (suited.sum(axis=2) == 4) & (holes % 4 == suit).any(axis=2)
    return category, top_pair, flush_draw
