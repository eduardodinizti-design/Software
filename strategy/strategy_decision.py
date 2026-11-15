"""Stable mixed selection; a lab policy and permission to click are separate."""
from dataclasses import asdict

from strategy.action_tree import legal_actions
from strategy.range_catalog import combo_key
from strategy.state_contract import StrategyError
from strategy.decision_explanation import explain


def choose(policy, decision, *, selection_mode='policy_mix'):
    if decision.context != policy.context:
        raise StrategyError('POLICY_CONTEXT_MISMATCH')
    state = decision.betting
    node, row = policy.row(state, decision.hero_cards)
    actions = policy.actions(state)
    if selection_mode not in ('policy_mix', 'exact_response'):
        raise StrategyError('UNKNOWN_SELECTION_MODE')
    probabilities = dict(row['frequencies'])
    if selection_mode == 'exact_response':
        # An explicitly labelled local response to a frozen model, not a new GTO
        # profile. Never maximize noisy Monte Carlo estimates as if they were exact.
        method = (policy.data.get('evaluation') or {}).get('method', '')
        evs = row.get('action_ev_bb')
        if not method.startswith('exact_') or evs is None:
            raise StrategyError('EXACT_RESPONSE_REQUIRES_EXACT_FROZEN_PROFILE_EVS')
        best = max(evs.values())
        ties = [a.id for a in actions if best - evs[a.id] <= 1e-9]
        total = sum(probabilities[a] for a in ties)
        probabilities = {a.id: (probabilities[a.id] / total if total else 1 / len(ties))
                         if a.id in ties else 0.0 for a in actions}
    # Stable per hand/public decision and policy, not a new draw on each frame.
    token = decision.selection_id()
    draw = int(token[:16], 16) / 2**64
    cumulative, selected = 0.0, actions[-1]
    for action in actions:
        cumulative += probabilities[action.id]
        if draw < cumulative:
            selected = action
            break
    candidates = []
    for action in actions:
        candidates.append(dict(action_id=action.id, action=action.kind,
                               additional_bb=action.amount_bb,
                               raise_to_bb=state.committed[state.actor] + action.amount_bb
                                   if action.kind in ('raise', 'all_in') else None,
                               frequency=row['frequencies'][action.id],
                               selection_frequency=probabilities[action.id],
                               ev_bb=(row.get('action_ev_bb') or {}).get(action.id)))
    quality = dict(policy.quality)
    quality['selection_mode'] = selection_mode
    quality['current_information_set_reach_probability'] = row.get('profile_reach_probability')
    quality['selected_profile_global_gap_bb'] = quality.get('global_gap_bb') if selection_mode == 'policy_mix' else None
    explanation = explain(decision, candidates, selected, quality)
    caveats = ['HU_CHIP_EV_COMPILED_POLICY', 'LAB_POLICY_REQUIRES_WINDOWS_EXECUTION_VALIDATION']
    if selection_mode == 'exact_response':
        caveats.append('LOCAL_RESPONSE_TO_FROZEN_MODEL_NOT_A_NEW_EQUILIBRIUM_PROFILE')
        explanation['reason'] = 'Maior EV enumerado contra o modelo congelado; nao certifica nova estrategia de equilibrio.'
    return dict(status='ADVICE', phase='postflop', street=state.street,
                recommended=selected.kind, action_id=selected.id,
                sizing=dict(size_bb=selected.amount_bb, semantics='ADDITIONAL_BB',
                            raise_to_bb=state.committed[0] + selected.amount_bb,
                            fraction_of_current_pot=(selected.amount_bb / state.pot_bb
                                if selected.kind == 'bet' else None), heuristic=False),
                candidates=candidates, node_id=policy.node_key(state), combo=combo_key(decision.hero_cards),
                policy_sha256=policy.fingerprint, range_sha256=[r.fingerprint for r in policy.ranges],
                context=asdict(decision.context), selection_id=token, quality=quality,
                explanation=explanation,
                exploratory=True, execution_allowed=False,
                caveats=caveats)
