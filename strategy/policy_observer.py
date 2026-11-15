"""Bridge to Software's passive reader. Never invent an unobserved action path.

The legacy OCR snapshot does not contain a confirmed postflop timeline. Until
that collector supplies strategy_state, the old read remains visible along with
an explicit engine diagnostic; missing context is not disguised as a solver hit.
"""
from strategy.state_contract import DecisionState, StrategyError, money
from strategy.strategy_decision import choose


class PolicyObserver:
    def __init__(self, policy):
        self.policy = policy

    def advise(self, *, table_key, hand_key, table_state, hero_cards, board, mode, stage):
        payload = table_state.get('strategy_state')
        if payload is None:
            return dict(status='CONTEXT_MISSING', reason='CONFIRMED_POSTFLOP_TIMELINE_REQUIRED',
                        policy_sha256=self.policy.fingerprint, execution_allowed=False)
        try:
            d = DecisionState.from_dict(payload)
            if str(d.table_id) != str(table_key) or str(d.hand_id) != str(hand_key):
                raise StrategyError('OBSERVATION_HAND_IDENTITY_MISMATCH')
            if set(d.hero_cards) != set(hero_cards or ()) or tuple(d.betting.board) != tuple(board or ()):
                raise StrategyError('OBSERVATION_CARDS_MISMATCH')
            if d.context.mode != mode or d.context.stage != stage:
                raise StrategyError('OBSERVATION_TOURNAMENT_MISMATCH')
            if (table_state.get('positions') or {}).get('hero') != d.context.positions[0]:
                raise StrategyError('OBSERVATION_POSITION_MISMATCH')
            villains = [seat for seat, position in (table_state.get('positions') or {}).items()
                        if seat != 'hero' and position == d.context.positions[1]]
            if len(villains) != 1:
                raise StrategyError('OBSERVATION_VILLAIN_IDENTITY_MISSING')
            active = table_state.get('active_seats')
            if not isinstance(active, (list, tuple)) or set(active) != {'hero', villains[0]} or len(active) != 2:
                raise StrategyError('OBSERVATION_ACTIVE_PARTICIPANTS_UNCONFIRMED_OR_MULTIWAY')
            p = (table_state.get('pot') or {}).get('pot_bb')
            c = (table_state.get('to_call') or {}).get('to_call_bb')
            stack = ((table_state.get('seats') or {}).get('hero') or {}).get('stack_bb')
            vstack = ((table_state.get('seats') or {}).get(villains[0]) or {}).get('stack_bb')
            if p is None or c is None or stack is None or vstack is None:
                raise StrategyError('OBSERVATION_MONEY_MISSING')
            p, c, stack, vstack = (money(v) for v in (p, c, stack, vstack))
            if any(abs(a - b) > 1e-7 for a, b in ((p, d.betting.pot_bb),
                    (c, d.betting.call_cost_bb), (stack, d.betting.stacks[0]), (vstack, d.betting.stacks[1]))):
                raise StrategyError('OBSERVATION_MONEY_MISMATCH')
            if payload.get('range_sha256') != [r.fingerprint for r in self.policy.ranges]:
                raise StrategyError('OBSERVATION_RANGE_SOURCE_MISMATCH')
            return choose(self.policy, d)
        except (StrategyError, ValueError, KeyError, TypeError) as exc:
            return dict(status='POLICY_MISS', reason=str(exc), execution_allowed=False,
                        policy_sha256=self.policy.fingerprint)
