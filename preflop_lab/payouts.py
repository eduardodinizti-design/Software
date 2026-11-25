"""Contribution-level side pots, uncalled returns and terminal cash bounties."""
import numpy as np


def settle(contributions, active, ranks, dead_money=0.):
    """Return chip awards for every player; folded contributions remain in pots.

    A one-player top layer is an uncalled return. Side-pot eligibility is by
    actual contribution. Ranks may be any comparable numeric exact evaluator.
    """
    paid = np.asarray(contributions, dtype=float)
    active = np.asarray(active, dtype=bool); ranks = np.asarray(ranks)
    if paid.ndim != 2 or active.shape != paid.shape or ranks.shape != paid.shape:
        raise ValueError('Contribution/eligibility/rank dimensions differ.')
    if not np.isfinite(paid).all() or (paid < 0).any() or not np.isfinite(dead_money) or dead_money < 0:
        raise ValueError('Invalid contributions/dead money.')
    if (~active.any(axis=1)).any():
        raise ValueError('At least one player must remain.')
    n, players = paid.shape; award = np.zeros_like(paid)
    levels = np.sort(paid, axis=1); previous = np.zeros(n)
    # Dead antes/folded money belongs to the main pot and all remaining players.
    best = np.max(np.where(active, ranks, -1), axis=1)
    winners = active & (ranks == best[:, None])
    award += dead_money * winners / winners.sum(axis=1)[:, None]
    for j in range(players):
        level = levels[:, j]
        contributors = paid >= level[:, None] - 1e-9
        layer = (level - previous) * contributors.sum(axis=1)
        eligible = active & contributors
        # If everyone eligible folded, the last live hand takes the uncontested
        # layer. Valid betting normally avoids this, but settlement conserves it.
        eligible = np.where(eligible.any(axis=1)[:, None], eligible, active)
        best = np.max(np.where(eligible, ranks, -1), axis=1)
        winners = eligible & (ranks == best[:, None])
        award += layer[:, None] * winners / winners.sum(axis=1)[:, None]
        previous = level
    if not np.allclose(award.sum(axis=1), paid.sum(axis=1) + dead_money, atol=1e-7):
        raise ArithmeticError('Chip conservation failed.')
    return award


def bounty_awards(contributions, active, ranks, awards, caps, cash_heads):
    """Immediate KO/PKO cash, awarded only on an exhausted target's deciding pot.

    Tied eliminations split the configured immediate reward between eligible
    winners; the heads/currency model is supplied explicitly. No future growth
    value or ICM is invented here. Returns per-player rewards in declared BB.
    """
    paid=np.asarray(contributions,float);ranks=np.asarray(ranks);active=np.asarray(active,bool)
    caps=np.asarray(caps,float);cash_heads=np.asarray(cash_heads,float)
    if caps.shape != (paid.shape[1],) or cash_heads.shape != caps.shape or not np.isfinite(caps).all() or not np.isfinite(cash_heads).all() or (cash_heads<0).any() or (caps<=0).any():
        raise ValueError('Invalid bounty model.')
    result=np.zeros_like(paid)
    for target in range(paid.shape[1]):
        busted=(paid[:,target]>=caps[target]-1e-8) & (awards[:,target]<1e-8) & active[:,target]
        eligible=active & (paid>=paid[:,target,None]-1e-8)
        best=np.max(np.where(eligible,ranks,-1),axis=1)
        winners=eligible & (ranks==best[:,None])
        result+=busted[:,None]*cash_heads[target]*winners/winners.sum(axis=1)[:,None]
    return result
