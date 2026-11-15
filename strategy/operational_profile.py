"""Explicit geometry/money/arrival contract for a compiled HU policy."""
from dataclasses import asdict, dataclass
import json
import math

from strategy.state_contract import StrategyError, digest


@dataclass(frozen=True)
class OperationalProfile:
    policy_sha256: str
    quantum_bb: float = .1  # actual precision displayed by the BB reader
    confirmations: int = 2
    max_snapshot_age_s: float = 3.0
    max_path_actions: int = 4
    max_search_nodes: int = 512
    ante_pot_bb: float = 0.0
    preflop_aggressor: int = 0
    require_preflop_witness: bool = True
    amount_box: tuple = (.76, .425, .205, .06)
    amount_decimals: int = 3
    decimal_separator: str = ','
    max_size_error_bb: float = .05
    pot_includes_bets: bool = True
    name: str = 'blue-portrait-bb-reference-v1'

    def __post_init__(self):
        object.__setattr__(self, 'amount_box', tuple(self.amount_box))
        for value in (self.quantum_bb, self.max_snapshot_age_s, self.max_size_error_bb):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise StrategyError('INVALID_OPERATIONAL_PRECISION_OR_AGE')
        if not self.policy_sha256 or self.confirmations < 2 or not 1 <= self.max_path_actions <= 8:
            raise StrategyError('INVALID_OPERATIONAL_PROFILE')
        if (type(self.confirmations) is not int or not 2 <= self.confirmations <= 10
                or type(self.max_path_actions) is not int or type(self.max_search_nodes) is not int
                or not 1 <= self.max_search_nodes <= 10000):
            raise StrategyError('INVALID_OPERATIONAL_BUDGET')
        if type(self.require_preflop_witness) is not bool or type(self.pot_includes_bets) is not bool:
            raise StrategyError('INVALID_OPERATIONAL_BOOLEAN')
        if self.preflop_aggressor not in (0, 1) or self.ante_pot_bb < 0 or not math.isfinite(self.ante_pot_bb):
            raise StrategyError('INVALID_ARRIVAL_RECIPE')
        if len(self.amount_box) != 4 or any(not 0 <= v <= 1 for v in self.amount_box):
            raise StrategyError('INVALID_AMOUNT_BOX')
        x, y, w, h = self.amount_box
        if w <= 0 or h <= 0 or x + w > 1 or y + h > 1 or not 0 <= self.amount_decimals <= 6:
            raise StrategyError('INVALID_AMOUNT_BOX_OR_DECIMALS')
        if self.decimal_separator not in ('.', ','):
            raise StrategyError('INVALID_DECIMAL_SEPARATOR')

    @property
    def fingerprint(self):
        return digest(asdict(self))

    @classmethod
    def load(cls, path, policy):
        with open(path, encoding='utf-8') as f:
            p = cls(**json.load(f))
        p.check_policy(policy)
        return p

    def check_policy(self, policy):
        if self.policy_sha256 != policy.fingerprint:
            raise StrategyError('OPERATIONAL_PROFILE_POLICY_HASH_MISMATCH')

    def recipe(self, policy):
        """SRP equal-contribution arrival; other pot types need a separate recipe.

        This declares the model being used. It does not claim the imported NVT
        chart was solved for this open/ante structure.
        """
        if policy.context.pot_type != 'single_raised' or len(policy.root.board) != 3:
            raise StrategyError('ARRIVAL_RECIPE_NOT_SINGLE_RAISED_FLOP')
        positions = policy.context.positions
        posts = {'SB': .5, 'BB': 1.0}
        if policy.context.dealt_players == 2 and 'BTN' in positions:
            posts = {'BTN': .5, 'BB': 1.0}
        dead = sum(v for p, v in posts.items() if p not in positions)
        level = (policy.root.pot_bb - dead - self.ante_pot_bb) / 2
        if level <= 1:
            raise StrategyError('ARRIVAL_OPEN_NOT_ABOVE_BLIND')
        return dict(forced_pot_bb=1.5 + self.ante_pot_bb, posts=posts, open_to_bb=level,
                    aggressor=positions[self.preflop_aggressor],
                    caller=positions[1 - self.preflop_aggressor])


def compatible(observed, expected, quantum=.1):
    """Compatibility with a rounded display, not an assertion of exact chips."""
    return (not isinstance(observed, bool) and isinstance(observed, (int, float))
            and math.isfinite(observed) and observed >= 0
            and abs(observed - expected) <= quantum / 2 + 1e-8)


def interval(value, quantum=.1):
    return [max(0.0, value - quantum / 2), value + quantum / 2]
