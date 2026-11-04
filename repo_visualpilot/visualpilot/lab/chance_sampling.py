"""Probability-preserving public-card sampling; stratification is optional."""
from bisect import bisect_right
from itertools import accumulate
import math


def sample_indices(weights,count,rng,method='random'):
    if type(count) is not int or count<=0 or method not in ('random','stratified'):
        raise ValueError('Amostragem inválida.')
    if not weights or any(type(w) not in (int,float) or not math.isfinite(w) or w<0 for w in weights):
        raise ValueError('Pesos inválidos.')
    cumulative=list(accumulate(weights));total=cumulative[-1]
    if not total>0 or not math.isfinite(total): raise ValueError('Distribuição vazia ou inválida.')
    if method=='random': return rng.choices(range(len(weights)),weights=weights,k=count)
    # One random point in each equal-probability stratum. No cards are classified
    # as good/bad for Hero, no guessed outcomes, no suppression of rare cards.
    upper=math.nextafter(total,0.0)  # Avoid rounding the last stratum onto a zero-mass tail.
    return [min(bisect_right(cumulative,min(upper,total*(i+rng.random())/count)),len(weights)-1)
            for i in range(count)]
