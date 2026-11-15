"""Install the checked 32-model bank or the separate SB40 family, data only."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import re
import uuid

from strategy.batch_archive import REPOSITORY,BATCH_TAG,PILOT_TAG,make_catalog,verify_remote_parts
from strategy.batch_download import (ASSET_BASE,check_bundle,install_catalog,load_catalog,
    pilot_manifest,read_json,valid_sha)
from strategy.batch_jobs import canonical_flop,case_id
from strategy.blind_war import SB40_TAG
from strategy.campaign import CLOSE32_TAG,validate_campaign_plan
from strategy.state_contract import StrategyError

PLANS={
    CLOSE32_TAG:('close32-plan.json','356a455380ed5cc1d88e559185c60b1c47a72bbdfa9690da9afbb04af107536f'),
    SB40_TAG:('sb40-plan.json','b6c55d124bcb8a334c2d79a2017f66cf43046100f297318093b3c1c51f200756'),
}


def load_campaign(tag,asset=None):
    if tag not in PLANS:raise StrategyError('KNOWN_CAMPAIGN_REQUIRED')
    filename,pinned=PLANS[tag]
    plan=validate_campaign_plan(read_json(ASSET_BASE+tag+'/'+filename))
    if plan['tag']!=tag or plan['plan_sha256']!=pinned:raise StrategyError('CAMPAIGN_IMMUTABLE_PLAN_CHANGED')
    release=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}')
    candidates=[a for a in release['assets'] if a['state']=='uploaded' and re.fullmatch(r'batch-catalog-[0-9]+\.json',a['name'])]
    if asset:candidates=[a for a in candidates if a['name']==asset]
    if not candidates:raise StrategyError('CAMPAIGN_CATALOG_NOT_YET_PUBLISHED')
    chosen=max(candidates,key=lambda a:a['id'])
    received=read_json(ASSET_BASE+tag+'/'+chosen['name'])
    if (received.get('schema')!='software.hu-batch-catalog.v1' or received.get('tag')!=tag
            or received.get('plan_sha256')!=pinned or received.get('status')!='COMPLETE'):
        raise StrategyError('COMPLETE_IMMUTABLE_CAMPAIGN_CATALOG_REQUIRED')
    catalog=make_catalog(plan,received['cases'])
    if (catalog['status']!='COMPLETE' or len(received['cases'])!=len(plan['cases'])
            or catalog['cases']!=received['cases'] or received['context']!=catalog['context']
            or received['root_template']!=catalog['root_template']):
        raise StrategyError('CAMPAIGN_CASES_OR_GEOMETRY_DIFFER_FROM_PINNED_PLAN')
    for expected,case in zip(plan['cases'],catalog['cases']):
        check_bundle(case);verify_remote_parts(case,release['assets'])
        if (case.get('tag')!=tag or case.get('ordinal')!=expected['ordinal'] or case_id(case['board'])!=case['case_id']
                or not valid_sha(case.get('policy_sha256')) or not valid_sha(case.get('file_sha256'))
                or type(case.get('policy_file_bytes')) is not int or case['policy_file_bytes']<=0):
            raise StrategyError('CAMPAIGN_CASE_IDENTITY_INVALID')
    catalog['_original_plan']=plan;catalog['profile_settings']=plan.get('profile_settings',{})
    return catalog,chosen['name']


def combine_thirty_two(catalog,old,pilot):
    plan=catalog['_original_plan']
    if catalog['tag']!=CLOSE32_TAG or len(catalog['cases'])!=15:raise StrategyError('FIFTEEN_MISSING_MODELS_REQUIRED')
    if old['context']!=catalog['context'] or old['root_template']!=catalog['root_template']:
        raise StrategyError('PREVIOUS_MODELS_HAVE_DIFFERENT_CONTEXT')
    previous=[pilot]+old['cases'];expected=plan['preexisting_models']
    identity=lambda c:(canonical_flop(c['board']),c['policy_sha256'],c['file_sha256'],c['tag'])
    if len(previous)!=17 or {identity(c) for c in previous}!={identity(c) for c in expected}:
        raise StrategyError('PREEXISTING_SEVENTEEN_MODELS_CHANGED')
    rows=[dict(c,source_ordinal=c['ordinal'],ordinal=i+1) for i,c in enumerate(previous+catalog['cases'])]
    if len({canonical_flop(c['board']) for c in rows})!=32:raise StrategyError('THIRTY_TWO_DISTINCT_MODELS_REQUIRED')
    result=dict(catalog,cases=rows,planned_new_flops=32,published_new_flops=32,native_target_met_flops=32,
        source_catalogs=[dict(tag=PILOT_TAG,asset='download-manifest.json'),
            dict(tag=BATCH_TAG,asset='batch-catalog-43764947533.json'),
            dict(tag=CLOSE32_TAG,plan_sha256=plan['plan_sha256'])],
        full_model_count=32,suit_aliases_counted_as_models=False)
    return result


def load_family(family,asset=None,*,new_only=False):
    tag=CLOSE32_TAG if family=='btn32' else SB40_TAG if family=='sb40' else None
    if tag is None:raise StrategyError('KNOWN_FAMILY_REQUIRED')
    catalog,name=load_campaign(tag,asset)
    if family=='btn32' and not new_only:
        old,_=load_catalog('batch-catalog-43764947533.json')
        catalog=combine_thirty_two(catalog,old,pilot_manifest())
    return catalog,name


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--family',required=True,choices=('btn32','sb40'))
    p.add_argument('--output');p.add_argument('--ordinals',nargs='+',type=int);p.add_argument('--catalog-asset')
    p.add_argument('--new-only',action='store_true');p.add_argument('--resume',action='store_true')
    args=p.parse_args(argv)
    output=args.output or ('runtime/hu/'+args.family+'-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    if Path(output).exists() and not args.resume:raise StrategyError('BATCH_OUTPUT_MUST_BE_NEW_OR_EXPLICIT_MANAGED_RESUME')
    catalog,asset=load_family(args.family,args.catalog_asset,new_only=args.new_only)
    receipt=install_catalog(output,catalog,asset,ordinals=args.ordinals,resume=args.resume)
    print('Familia:',args.family,'| modelos consultados:',receipt['total_models']);return 0


if __name__=='__main__':raise SystemExit(main())
