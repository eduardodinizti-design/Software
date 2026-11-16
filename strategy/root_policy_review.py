"""Read-only root frequencies conditional on both priors and physical blockers."""
import math

from strategy.range_catalog import DECK,combo_cards
from strategy.state_contract import StrategyError


def review_root_policy(policy):
    state=policy.root
    if len(state.board)!=3 or state.history or state.terminal or state.needs_cards:
        raise StrategyError('ROOT_REVIEW_REQUIRES_THE_INITIAL_FLOP_NODE')
    actor=state.actor;actions=policy.actions(state);index={card:i for i,card in enumerate(DECK)}
    def mask(key):return sum(1<<index[c] for c in combo_cards(key))
    ranges=tuple(r.without(state.board) for r in policy.ranges)
    opponent=[(mask(key),weight) for key,weight in ranges[1-actor].weights]
    numerators=[0.]*len(actions);joint_mass=0.;deals=0;own_count=0
    for key,weight in ranges[actor].weights:
        own_mask=mask(key);possible=[w for other,w in opponent if not own_mask&other]
        mass=weight*sum(possible)
        if mass<=0:continue
        probabilities=policy.probabilities(state,combo_cards(key))
        if (len(probabilities)!=len(actions) or any(not math.isfinite(v) or not 0<=v<=1 for v in probabilities)
                or abs(sum(probabilities)-1)>1e-6):
            raise StrategyError('ROOT_REVIEW_INVALID_STORED_FREQUENCIES')
        for i,value in enumerate(probabilities):numerators[i]+=mass*value
        joint_mass+=mass;deals+=len(possible);own_count+=1
    if joint_mass<=0:raise StrategyError('ROOT_REVIEW_NO_COMPATIBLE_JOINT_PRIVATE_DEAL')
    result=[dict(action.to_dict(),action_id=action.id,frequency=value/joint_mass)
            for action,value in zip(actions,numerators)]
    return dict(schema='software.hu-root-policy-review.v1',
        method='BLOCKER_CONDITIONED_JOINT_RANGE_WEIGHTED_ROOT_POLICY',
        source_policy_sha256=policy.fingerprint,board=list(state.board),actor=actor,
        actor_position=policy.context.positions[actor],actions=result,
        compatible_joint_private_deals=deals,actor_supported_private_combos=own_count,
        compatible_joint_prior_mass=joint_mass,source_range_sha256=[r.fingerprint for r in policy.ranges],
        scope='WEIGHTED_ROOT_FREQUENCIES_NOT_AN_ACTION_FOR_EVERY_HAND_OR_AN_EV_CERTIFICATE',
        policy_modified=False,pppoker_windows_validated=False)
