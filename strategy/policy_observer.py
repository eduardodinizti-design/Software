"""Bridge to Software's passive reader. Never invent an unobserved action path.

The legacy OCR snapshot does not contain a confirmed postflop timeline. Until
that collector supplies strategy_state, the old read remains visible along with
an explicit engine diagnostic; missing context is not disguised as a solver hit.
"""
from strategy.state_contract import DecisionState, StrategyError, money
from strategy.strategy_decision import choose
from strategy.operational_profile import compatible


class PolicyObserver:
    def __init__(self, policy, profile=None):
        self.policy = policy
        self.profile = profile
        if profile is not None:
            profile.check_policy(policy)

    def advise(self, *, table_key, hand_key, table_state, hero_cards, board, mode, stage):
        payload = table_state.get('strategy_state')
        if payload is None:
            return dict(status='CONTEXT_MISSING', reason=(table_state.get('confirmed_history') or {}).get('reason') or 'CONFIRMED_POSTFLOP_TIMELINE_REQUIRED',
                        policy_sha256=self.policy.fingerprint, execution_allowed=False)
        try:
            d = DecisionState.from_dict(payload)
            if str(d.table_id) != str(table_key) or str(d.hand_id) != str(hand_key):
                raise StrategyError('OBSERVATION_HAND_IDENTITY_MISMATCH')
            actual_board = tuple(board or ())
            if (set(d.hero_cards) != set(hero_cards or ()) or set(d.betting.board[:3]) != set(actual_board[:3])
                    or d.betting.board[3:] != actual_board[3:]):
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
            values = ((p, d.betting.pot_bb), (c, d.betting.call_cost_bb),
                      (stack, d.betting.stacks[0]), (vstack, d.betting.stacks[1]))
            if self.profile is not None:
                if payload.get('profile_sha256') != self.profile.fingerprint or not payload.get('history_confirmation'):
                    raise StrategyError('OBSERVATION_CONFIRMED_HISTORY_BINDING_MISSING')
                history = table_state.get('confirmed_history') or {}
                if history.get('status') != 'CONFIRMED' or history.get('ranges_status') != 'CONDITIONED':
                    raise StrategyError('OBSERVATION_POSTERIOR_RESPONSE_MODEL_MISSING')
            if any(not compatible(a, b, self.profile.quantum_bb) if self.profile else abs(a-b) > 1e-7 for a,b in values):
                raise StrategyError('OBSERVATION_MONEY_MISMATCH')
            if payload.get('range_sha256') != [r.fingerprint for r in self.policy.ranges]:
                raise StrategyError('OBSERVATION_RANGE_SOURCE_MISMATCH')
            advice = choose(self.policy, d)
            if self.profile is not None:
                advice['operational'] = dict(profile_sha256=self.profile.fingerprint,
                    history_revision=d.revision, history_confirmation=payload['history_confirmation'],
                    amount_alignment='WITHIN_DISPLAY_ROUNDING_INTERVAL',
                    observed_quantum_bb=self.profile.quantum_bb,
                    source_authority='COMPILED_HU_REFERENCE', solver_certificate_for_actual_chips=False)
            return advice
        except (StrategyError, ValueError, KeyError, TypeError) as exc:
            return dict(status='POLICY_MISS', reason=str(exc), execution_allowed=False,
                        policy_sha256=self.policy.fingerprint)
