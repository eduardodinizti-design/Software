"""Freeze sixteen new SB40 textures without changing the published arrival."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from postflop_eval import classify_board
from strategy.batch_jobs import atomic_json,canonical_flop,catalogue_flops
from strategy.blind_war import SB40_TAG,SB40_NEXT16_TAG
from strategy.campaign import checked_campaign_plan,make_campaign,model_identity,validate_campaign_plan
from strategy.state_contract import StrategyError

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'docs/software-hu-close32-sb40-20261115'
OUT=ROOT/'docs/software-hu-sb40-next16-20261116'


def prepare(pilot_plan,pilot_catalog):
    if (pilot_plan['tag']!=SB40_TAG or pilot_catalog['tag']!=SB40_TAG
            or pilot_catalog['plan_sha256']!=pilot_plan['plan_sha256']
            or pilot_catalog['status']!='COMPLETE' or len(pilot_catalog['cases'])!=1):
        raise StrategyError('EXACT_COMPLETE_SB40_PILOT_REQUIRED')
    previous=pilot_catalog['cases'][0]
    if not previous['native_target_met'] or not previous['coverage']['structurally_complete']:
        raise StrategyError('ONLY_COMPLETE_TARGET_MET_SB40_PILOT_COUNTS')
    game=copy.deepcopy(pilot_plan['game'])
    forbidden={canonical_flop(previous['board'])}|{canonical_flop(b) for b in pilot_plan['preserved_holdout_flops']}
    boards=[b for b in catalogue_flops(100) if canonical_flop(b) not in forbidden][:16]
    existing=[{k:previous[k] for k in ('board','policy_sha256','file_sha256','tag')}]
    plan=make_campaign(game,boards,tag=SB40_NEXT16_TAG,
        label='SB x BB 40 BB NVT: 16 novos flops completos, 17 com o piloto',
        existing=existing,goal_models=17,profile_settings=pilot_plan['profile_settings'],
        settings=dict(work_disk_mb=30720))
    if model_identity(game)!=pilot_plan['model_sha256']:
        raise StrategyError('SB40_PRIORS_MENU_OR_GEOMETRY_CHANGED')
    return validate_campaign_plan(plan)


def main():
    pilot=checked_campaign_plan(PRIOR/'sb40-plan.json')
    catalog=json.loads((PRIOR/'published/batch-catalog-43777381626.json').read_text())
    plan=prepare(pilot,catalog);OUT.mkdir(exist_ok=True)
    for name,value in (('sb40-next16-plan.json',plan),('texturas.json',dict(
            schema='software.hu-sb40-next16-textures.v1',plan_sha256=plan['plan_sha256'],
            cases=[dict(c,texture=classify_board(c['board'])) for c in plan['cases']]))):
        path=OUT/name
        if path.exists() and json.loads(path.read_text())!=value:
            raise StrategyError('EXISTING_FROZEN_SB40_PLAN_PRESERVED')
        if not path.exists():atomic_json(path,value)
    print(json.dumps(dict(plan_sha256=plan['plan_sha256'],new_models=16,total_with_pilot=17,
        game_model_sha256=plan['model_sha256'],boards=[c['board'] for c in plan['cases']])) )


if __name__=='__main__':main()
