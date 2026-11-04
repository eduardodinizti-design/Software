"""Explicit cash-bounty utility for fictitious heads-up PKO experiments.

This is not an ICM/bounty-power solver. Future value of the progressive portion
is unknown and deliberately not booked as immediate cash.
"""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class PKOContext:
    hero_stack: float
    villain_stack: float
    hero_bounty: float
    villain_bounty: float
    cash_fraction: float
    bb_per_currency: float
    conversion_source: str
    currency: str = 'LAB'

    def validate(self, effective_stack):
        positive=(self.hero_stack,self.villain_stack,self.bb_per_currency)
        nonnegative=(self.hero_bounty,self.villain_bounty)
        if any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in positive):
            raise ValueError('Stacks e conversão do bounty devem ser positivos.')
        if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in nonnegative):
            raise ValueError('Bounties inválidos.')
        if type(self.cash_fraction) not in (int,float) or not math.isfinite(self.cash_fraction) or not 0<=self.cash_fraction<=1:
            raise ValueError('Regra de pagamento do bounty inválida.')
        if not self.conversion_source or not self.currency: raise ValueError('Origem e moeda da conversão obrigatórias.')
        if abs(min(self.hero_stack,self.villain_stack)-effective_stack)>1e-7:
            raise ValueError('Stack efetivo incompatível com cobertura PKO.')

    @property
    def hero_covers(self): return self.hero_stack>=self.villain_stack

    @property
    def villain_covers(self): return self.villain_stack>=self.hero_stack

    def reward(self, probability_win, villain_all_in):
        if not math.isfinite(probability_win) or not 0<=probability_win<=1: raise ValueError('Probabilidade inválida.')
        cash=self.villain_bounty*self.cash_fraction
        eligible=self.hero_covers and villain_all_in
        return dict(eligible=eligible,expected_cash=probability_win*cash if eligible else 0.,
            expected_bb=probability_win*cash*self.bb_per_currency if eligible else 0.,
            progressive_added_on_win=self.villain_bounty*(1-self.cash_fraction) if eligible else 0.,
            future_progressive_ev=None)

    def trace(self):
        return dict(asdict(self),hero_covers=self.hero_covers,villain_covers=self.villain_covers,
                    utility='chip_ev_plus_immediate_cash_bounty_conversion',
                    excludes=['ICM','future_progressive_bounty_value','multiway_side_pots'])
