"""Add seventeen new full SB40 models only after a saved prior-bank checkpoint."""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from postflop_eval import classify_board
from strategy.batch_jobs import atomic_json,canonical_flop,catalogue_flops
from strategy.blind_war import SB40_COMPLETE34_TAG,SB40_NEXT16_TAG
from strategy.campaign import make_campaign,model_identity,validate_campaign_plan
from strategy.campaign_download import load_family
from strategy.state_contract import StrategyError,digest
from tools.check_hu_sb40_checkpoint import check_saved,PRIOR_CATALOG

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/software-hu-sb40-complete34-20261116'


def prepare(previous,checkpoint):
    proof=dict(checkpoint);claimed=proof.pop('checkpoint_sha256',None)
    if (checkpoint.get('status')!='PASS' or digest(proof)!=claimed
            or checkpoint.get('complete_saved_models')!=17 or previous.get('status')!='COMPLETE'
            or previous.get('tag')!=SB40_NEXT16_TAG or len(previous.get('cases',[]))!=17):
        raise StrategyError('VERIFIED_SAVED_SEVENTEEN_MODEL_CHECKPOINT_REQUIRED')
    prior=previous['_original_plan'];game=copy.deepcopy(prior['game'])
    identity=lambda c:(canonical_flop(c['board']),c['policy_sha256'],c['file_sha256'],c['tag'])
    if (model_identity(game)!=checkpoint['model_sha256']
            or previous.get('profile_settings')!=checkpoint['profile_settings']
            or {identity(c) for c in previous['cases']}!={identity(c) for c in checkpoint['preserved_models']}):
        raise StrategyError('CHECKPOINT_PRIORS_OR_PREVIOUS_MODELS_DIFFER')
    forbidden={canonical_flop(c['board']) for c in previous['cases']}|{canonical_flop(b) for b in prior['preserved_holdout_flops']}
    boards=[b for b in catalogue_flops(100) if canonical_flop(b) not in forbidden][:17]
    plan=make_campaign(game,boards,tag=SB40_COMPLETE34_TAG,
        label='SB x BB 40 BB NVT: 17 novos flops completos, 34 acumulados',
        existing=copy.deepcopy(checkpoint['preserved_models']),goal_models=34,
        settings=dict(prior['settings'],memory_mb=12288,work_disk_mb=30720),
        profile_settings=prior['profile_settings'])
    plan['prerequisite_checkpoint_sha256']=checkpoint['checkpoint_sha256']
    plan['preexisting_catalog']=dict(tag=SB40_NEXT16_TAG,asset=PRIOR_CATALOG,plan_sha256=prior['plan_sha256'])
    plan.pop('plan_sha256');plan['plan_sha256']=digest(plan)
    return validate_campaign_plan(plan)


def main():
    checkpoint=check_saved();previous,_=load_family('sb40-next16',PRIOR_CATALOG)
    plan=prepare(previous,checkpoint);OUT.mkdir(exist_ok=True)
    values={'checkpoint-primeiros17.json':checkpoint,'sb40-complete34-plan.json':plan,
        'texturas.json':dict(schema='software.hu-sb40-complete34-textures.v1',
            plan_sha256=plan['plan_sha256'],cases=[dict(c,texture=classify_board(c['board'])) for c in plan['cases']])}
    for name,value in values.items():
        path=OUT/name
        if path.exists() and json.loads(path.read_text())!=value:raise StrategyError('FROZEN_SB40_PLAN_OR_CHECKPOINT_PRESERVED')
        if not path.exists():atomic_json(path,value)
    print(json.dumps(dict(status='PREPARED_AFTER_SAVED_CHECKPOINT',new_models=17,total_models=34,
        plan_sha256=plan['plan_sha256'],checkpoint_sha256=checkpoint['checkpoint_sha256'],
        model_sha256=plan['model_sha256'],boards=[c['board'] for c in plan['cases']])) )


if __name__=='__main__':main()
