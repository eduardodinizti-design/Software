"""Offline heads-up chip-EV experiments. No live action adapter or GTO claim."""
from collections import Counter
from itertools import combinations
import hashlib
import json
import math
import random

RANKS = '23456789TJQKA'
DECK = tuple(r+s for r in RANKS for s in 'cdhs')


def validate_cards(cards):
    if any(c not in DECK for c in cards) or len(set(cards)) != len(cards):
        raise ValueError('Cartas inválidas ou repetidas.')


def rank5(cards):
    """Comparable exact five-card rank, including wheel and split pots."""
    values = sorted((RANKS.index(c[0])+2 for c in cards), reverse=True)
    groups = sorted(((n, v) for v, n in Counter(values).items()), reverse=True)
    unique = sorted(set(values), reverse=True)
    straight = 5 if unique == [14, 5, 4, 3, 2] else (
        unique[0] if len(unique) == 5 and unique[0]-unique[-1] == 4 else 0)
    flush = len({c[1] for c in cards}) == 1
    if flush and straight: return (8, straight)
    if groups[0][0] == 4: return (7, groups[0][1], groups[1][1])
    if [g[0] for g in groups] == [3, 2]: return (6, groups[0][1], groups[1][1])
    if flush: return (5, *values)
    if straight: return (4, straight)
    if groups[0][0] == 3: return (3, *(v for n, v in groups))
    if [g[0] for g in groups[:2]] == [2, 2]: return (2, *(v for n, v in groups))
    if groups[0][0] == 2: return (1, *(v for n, v in groups))
    return (0, *values)


def rank7(cards):
    return max(rank5(c) for c in combinations(cards, 5))


def expand_range(frequencies, dead=()):
    """NVT action frequencies weight each physical combo, not each hand class."""
    validate_cards(dead)
    result = {}
    for hand, weight in frequencies.items():
        if not isinstance(weight, (int, float)) or not math.isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError('Frequência inválida.')
        if len(hand) not in (2, 3) or any(r not in RANKS for r in hand[:2]):
            raise ValueError('Classe de mão inválida.')
        a, b = hand[:2]
        if (a == b and len(hand) != 2) or (a != b and (len(hand) != 3 or hand[2] not in 'so')):
            raise ValueError('Classe de mão inválida.')
        for combo in combinations(DECK, 2):
            if set(combo) & set(dead): continue
            if sorted(c[0] for c in combo) != sorted((a, b)): continue
            if a != b and (combo[0][1] == combo[1][1]) != (hand[2] == 's'): continue
            if weight: result[combo] = weight
    return result


def range_from_nvt(book, node_id, action, dead=()):
    node = next((n for n in book.nodes.values() if n['id'] == node_id), None)
    if node is None or action not in node['actions']:
        raise ValueError('Nó ou ação NVT não encontrado.')
    excluded = set(node.get('outOfRange', []))
    frequencies = {h: node['freq'][action][i] for h, i in book.hands.items() if i not in excluded}
    return expand_range(frequencies, dead), dict(book.provenance, node_id=node_id, action=action)


def equity(hero, board, villain_range, samples=2000, seed=42):
    """Exact river; reproducible weighted Monte Carlo on flop/turn."""
    if len(hero) != 2 or len(board) not in (3, 4, 5): raise ValueError('Estado pós-flop inválido.')
    validate_cards(tuple(hero)+tuple(board))
    if type(samples) is not int or samples < 2: raise ValueError('Amostra insuficiente.')
    eligible = {}
    for combo, weight in villain_range.items():
        if len(combo) != 2: raise ValueError('Combo inválido.')
        validate_cards(combo)
        if not math.isfinite(weight) or weight < 0: raise ValueError('Peso inválido.')
        if not set(combo) & set(tuple(hero)+tuple(board)) and weight > 0:
            eligible[combo] = weight
    if not eligible: raise ValueError('Range vazio após remoção de bloqueadores.')
    combos = list(eligible); weights = list(eligible.values())
    def score(combo, runout):
        h = rank7(tuple(hero)+tuple(board)+tuple(runout))
        v = rank7(tuple(combo)+tuple(board)+tuple(runout))
        return float(h > v) + .5 * (h == v)
    if len(board) == 5:
        value = sum(score(c, ()) * w for c, w in eligible.items()) / sum(weights)
        return dict(equity=value, standard_error=0., method='exact_river', trials=len(combos))
    rng = random.Random(seed); scores = []
    for combo in rng.choices(combos, weights=weights, k=samples):
        remaining = [c for c in DECK if c not in tuple(hero)+tuple(board)+tuple(combo)]
        scores.append(score(combo, rng.sample(remaining, 5-len(board))))
    mean = sum(scores)/samples
    se = math.sqrt(sum((s-mean)**2 for s in scores)/(samples-1)/samples)
    return dict(equity=mean, standard_error=se, method='monte_carlo_checkdown', trials=samples)


def compare_actions(hero, board, villain_range, pot, stack, bets=(), to_call=0.,
                    fold_by_combo=None, samples=2000, seed=42):
    """EV relative to folding now. Bet model: opponent folds/calls, then showdown.

    fold_by_combo maps each bet size to each combo's fold probability. This is
    an explicit experimental response model, never an inferred optimal strategy.
    No raises, future betting, rake, ICM, or multiway evaluation supported.
    """
    for v in (pot, stack, to_call, *bets):
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError('Valor de fichas inválido.')
    if pot <= 0 or stack <= 0 or to_call > stack: raise ValueError('Pote/stack inválido.')
    if to_call and bets: raise ValueError('Raises ainda não modelados.')
    dead = set(tuple(hero)+tuple(board))
    base = equity(hero, board, villain_range, samples, seed)
    clean = {c:w for c,w in villain_range.items() if not set(c)&dead and w>0}
    rows = []
    if to_call:
        rows = [dict(action='fold', amount=0., ev=0.),
                dict(action='call', amount=to_call, ev=base['equity']*(pot+to_call)-to_call)]
    else:
        rows = [dict(action='check', amount=0., ev=base['equity']*pot)]
        for bet in bets:
            if bet <= 0 or bet > stack: raise ValueError('Aposta fora do stack efetivo.')
            response = (fold_by_combo or {}).get(bet)
            if response is None or any(c not in response for c in clean):
                raise ValueError('Modelo de resposta obrigatório para cada combo e sizing.')
            if any(not math.isfinite(response[c]) or not 0<=response[c]<=1 for c in clean):
                raise ValueError('Probabilidade de fold inválida.')
            fold = sum(w*response[c] for c,w in clean.items())/sum(clean.values())
            continuing = {c:w*(1-response[c]) for c,w in clean.items() if response[c]<1}
            called = equity(hero, board, continuing, samples, seed) if continuing else None
            ev = fold*pot + (1-fold)*(called['equity']*(pot+2*bet)-bet) if called else pot
            rows.append(dict(action='bet', amount=bet, ev=ev, fold_probability=fold, called_equity=called))
    ordered = sorted(rows, key=lambda r:r['ev'], reverse=True)
    payload = dict(hero=list(hero), board=list(board), range=[[*c,w] for c,w in sorted(clean.items())],
                   pot=pot, stack=stack, bets=list(bets), to_call=to_call, seed=seed, samples=samples,
                   response={str(b):[[*c,p] for c,p in sorted(r.items())] for b,r in (fold_by_combo or {}).items()})
    return dict(status='experimental', laboratory_only=True, equity=base, comparisons=ordered,
                best_under_model=ordered[0], inputs=payload,
                input_sha256=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
                assumptions=['heads_up_chip_ev', 'opponent_fold_or_call_only', 'no_future_betting',
                             'no_rake_or_icm', 'response_model_is_hypothesis_not_solver'],
                uncertainty='Monte Carlo error excludes response-model error; ranking is not GTO proof.')
