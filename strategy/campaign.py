"""Checked, sized campaigns over immutable complete-policy inventories."""
import copy
import json
from pathlib import Path
import re

from strategy.batch_jobs import canonical_flop,catalogue_flops,case_id
from strategy.hu_engine import HOLDOUT_FLOPS
from strategy.state_contract import StrategyError,digest

CLOSE32_TAG='hu-btn-bb-nvt-complete32-20261115'


def model_identity(game):
    body=copy.deepcopy(game);body['root'].pop('board')
    return digest(body)


def complete_inventory(catalog,pilot_result):
    if (catalog.get('status')!='COMPLETE' or catalog.get('native_target_met_flops')!=len(catalog['cases'])
            or not pilot_result.get('native_target_met') or not pilot_result['coverage']['structurally_complete']):
        raise StrategyError('ONLY_COMPLETE_NATIVE_TARGET_MET_MODELS_COUNT')
    rows=[dict(board=pilot_result['board'],policy_sha256=pilot_result['policy_sha256'],
        file_sha256=pilot_result['file_sha256'],tag=catalog['pilot_tag'])]
    rows += [{k:c[k] for k in ('board','policy_sha256','file_sha256','tag')} for c in catalog['cases']]
    keys=[canonical_flop(r['board']) for r in rows]
    if len(keys)!=len(set(keys)):raise StrategyError('INVENTORY_DUPLICATES_SUIT_EQUIVALENT_MODELS')
    return rows


def make_campaign(game,boards,*,tag,label,existing=(),goal_models=None,settings=None,profile_settings=None):
    game=copy.deepcopy(game);values=[list(b) for b in boards]
    limits=dict(iterations=2001,accuracy_pct=.5,threads=4,memory_mb=10240,
                work_disk_mb=12288,timeout_seconds=18000)
    limits.update(settings or {})
    value=dict(schema='software.hu-campaign-plan.v1',tag=tag,label=label,game=game,
        model_sha256=model_identity(game),cases=[dict(ordinal=i+1,case_id=case_id(b),board=b) for i,b in enumerate(values)],
        preexisting_models=list(existing),target_total_models=goal_models or len(existing)+len(values),
        already_solved_board=game['root']['board'],preserved_holdout_flops=[b.split() for b in HOLDOUT_FLOPS],
        max_parallel_hosts=8,workers_per_host=1,archive_filename='full-policy.zip',
        profile_settings=dict(profile_settings or {}),
        settings=limits)
    value['plan_sha256']=digest(value);return value


def close32_plan(game,catalog,pilot_result):
    existing=complete_inventory(catalog,pilot_result)
    forbidden={canonical_flop(r['board']) for r in existing}|{canonical_flop(b.split()) for b in HOLDOUT_FLOPS}
    remaining=32-len(existing)
    if remaining<=0:raise StrategyError('THIRTY_TWO_MODELS_ALREADY_COMPLETE')
    boards=[b for b in catalogue_flops(100) if canonical_flop(b) not in forbidden][:remaining]
    return make_campaign(game,boards,tag=CLOSE32_TAG,label='BTN x BB NVT: fechamento de 32 flops completos',
        existing=existing,goal_models=32)


def checked_campaign_plan(path):
    p=json.loads(Path(path).read_text());body=dict(p);claimed=body.pop('plan_sha256',None)
    if p.get('schema')!='software.hu-campaign-plan.v1' or digest(body)!=claimed:
        raise StrategyError('CAMPAIGN_PLAN_HASH_MISMATCH')
    if not re.fullmatch(r'hu-[a-z0-9-]+',p.get('tag','')):raise StrategyError('SAFE_CAMPAIGN_TAG_REQUIRED')
    cases=p['cases'];new=[canonical_flop(c['board']) for c in cases]
    existing=[canonical_flop(c['board']) for c in p['preexisting_models']]
    holdout={canonical_flop(b) for b in p['preserved_holdout_flops']}
    if (not new or len(set(new))!=len(new) or len(set(existing))!=len(existing)
            or set(new)&(set(existing)|holdout) or [c['ordinal'] for c in cases]!=list(range(1,len(cases)+1))
            or any(c['case_id']!=case_id(c['board']) for c in cases)
            or p['target_total_models']!=len(existing)+len(new)
            or model_identity(p['game'])!=p['model_sha256']):
        raise StrategyError('CAMPAIGN_REQUIRES_NEW_DISTINCT_MODELS_AND_MATCHING_TARGET')
    return p
