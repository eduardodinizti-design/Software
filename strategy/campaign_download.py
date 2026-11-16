"""Install the checked 32-model bank or the separate SB40 family, data only."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import re
import uuid

from strategy.batch_archive import REPOSITORY,BATCH_TAG,PILOT_TAG,make_catalog,verify_remote_parts
from strategy.batch_download import (ASSET_BASE,check_bundle,install_catalog,load_catalog,
    pilot_manifest,read_json,valid_sha,metadata_snapshot)
from strategy.batch_jobs import canonical_flop,case_id
from strategy.blind_war import SB40_TAG,SB40_NEXT16_TAG,SB40_COMPLETE34_TAG,SB40_COMPLETE51_TAG,SB40_SERIES_TAGS
from strategy.campaign import CLOSE32_TAG,validate_campaign_plan,model_identity
from strategy.state_contract import StrategyError

PLANS={
    CLOSE32_TAG:('close32-plan.json','356a455380ed5cc1d88e559185c60b1c47a72bbdfa9690da9afbb04af107536f'),
    SB40_TAG:('sb40-plan.json','b6c55d124bcb8a334c2d79a2017f66cf43046100f297318093b3c1c51f200756'),
    SB40_NEXT16_TAG:('sb40-next16-plan.json','ed7f4a9b39e34fb4e83055eede52b20d7a9cb065fe6e676d81046bc04dceb26e'),
    SB40_COMPLETE34_TAG:('sb40-complete34-plan.json','f070d2c0289dd6eef328e48da8fbecd001c6bf483380e987a7208ea730b63d67'),
    SB40_COMPLETE51_TAG:('sb40-complete51-plan.json',None),
}
PLANS.update({tag:(f'sb40-complete{n}-plan.json',None) for n,tag in SB40_SERIES_TAGS.items()})


def load_campaign(tag,asset=None):
    with metadata_snapshot():return _load_campaign(tag,asset)


def _load_campaign(tag,asset=None,*,return_parent=False):
    if tag not in PLANS:raise StrategyError('KNOWN_CAMPAIGN_REQUIRED')
    filename,pinned=PLANS[tag]
    plan=validate_campaign_plan(read_json(ASSET_BASE+tag+'/'+filename))
    previous=None
    if tag==SB40_COMPLETE51_TAG:
        from strategy.sb40_progression import validate_derived_plan51
        previous,_=validate_derived_plan51(plan)
        pinned=plan['plan_sha256']
    elif tag in SB40_SERIES_TAGS.values():
        from strategy.sb40_series import validate_series_plan
        previous,_=validate_series_plan(plan)
        pinned=plan['plan_sha256']
    if plan['tag']!=tag or plan['plan_sha256']!=pinned:raise StrategyError('CAMPAIGN_IMMUTABLE_PLAN_CHANGED')
    release=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}')
    candidates=[a for a in release['assets'] if a['state']=='uploaded' and re.fullmatch(r'batch-catalog-[0-9]+(?:-a[0-9]+)?\.json',a['name'])]
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
    return (catalog,chosen['name'],previous) if return_parent else (catalog,chosen['name'])


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


def combine_sb40_seventeen(catalog,pilot):
    plan=catalog['_original_plan'];old_plan=pilot['_original_plan']
    if (catalog['tag']!=SB40_NEXT16_TAG or len(catalog['cases'])!=16
            or pilot['tag']!=SB40_TAG or pilot.get('status')!='COMPLETE' or len(pilot['cases'])!=1):
        raise StrategyError('SIXTEEN_NEW_SB40_MODELS_AND_COMPLETE_PILOT_REQUIRED')
    if (model_identity(plan['game'])!=model_identity(old_plan['game'])
            or catalog.get('profile_settings',{})!=pilot.get('profile_settings',{})):
        raise StrategyError('SB40_PRIORS_MENU_GEOMETRY_OR_ANTE_CHANGED')
    identity=lambda c:(canonical_flop(c['board']),c['policy_sha256'],c['file_sha256'],c['tag'])
    if {identity(c) for c in pilot['cases']}!={identity(c) for c in plan['preexisting_models']}:
        raise StrategyError('SB40_PREEXISTING_PILOT_IDENTITY_CHANGED')
    rows=[dict(c,source_ordinal=c['ordinal'],ordinal=i+1)
          for i,c in enumerate(pilot['cases']+catalog['cases'])]
    if len({canonical_flop(c['board']) for c in rows})!=17:
        raise StrategyError('SEVENTEEN_SUIT_DISTINCT_SB40_MODELS_REQUIRED')
    return dict(catalog,cases=rows,planned_new_flops=17,published_new_flops=17,native_target_met_flops=17,
        full_model_count=17,suit_aliases_counted_as_models=False,pilot_tag=SB40_TAG,
        source_catalogs=[dict(tag=SB40_TAG,asset='batch-catalog-43777381626.json'),
            dict(tag=SB40_NEXT16_TAG,plan_sha256=plan['plan_sha256'])])


def combine_sb40_thirty_four(catalog,previous):
    plan=catalog['_original_plan'];prior=previous['_original_plan']
    if (catalog.get('tag')!=SB40_COMPLETE34_TAG or catalog.get('status')!='COMPLETE'
            or len(catalog.get('cases',[]))!=17 or previous.get('tag')!=SB40_NEXT16_TAG
            or previous.get('status')!='COMPLETE' or len(previous.get('cases',[]))!=17):
        raise StrategyError('SEVENTEEN_NEW_AND_SEVENTEEN_PREVIOUS_COMPLETE_SB40_MODELS_REQUIRED')
    if (model_identity(plan['game'])!=model_identity(prior['game'])
            or catalog.get('profile_settings')!=previous.get('profile_settings')):
        raise StrategyError('SB40_PRIORS_MENU_GEOMETRY_OR_ANTE_CHANGED')
    identity=lambda c:(canonical_flop(c['board']),c['policy_sha256'],c['file_sha256'],c['tag'])
    if {identity(c) for c in previous['cases']}!={identity(c) for c in plan['preexisting_models']}:
        raise StrategyError('SB40_PREVIOUS_SEVENTEEN_IDENTITIES_CHANGED')
    rows=[dict(c,source_ordinal=c.get('source_ordinal',c['ordinal']),ordinal=i+1)
          for i,c in enumerate(previous['cases']+catalog['cases'])]
    if len({canonical_flop(c['board']) for c in rows})!=34:
        raise StrategyError('THIRTY_FOUR_SUIT_DISTINCT_SB40_MODELS_REQUIRED')
    return dict(catalog,cases=rows,planned_new_flops=34,published_new_flops=34,native_target_met_flops=34,
        full_model_count=34,suit_aliases_counted_as_models=False,pilot_tag=SB40_TAG,
        source_catalogs=previous['source_catalogs']+[dict(tag=SB40_COMPLETE34_TAG,plan_sha256=plan['plan_sha256'])])


def combine_sb40_fifty_one(catalog,previous):
    plan=catalog['_original_plan'];prior=previous['_original_plan']
    if (catalog.get('tag')!=SB40_COMPLETE51_TAG or catalog.get('status')!='COMPLETE'
            or len(catalog.get('cases',[]))!=17 or previous.get('tag')!=SB40_COMPLETE34_TAG
            or previous.get('status')!='COMPLETE' or len(previous.get('cases',[]))!=34):
        raise StrategyError('SEVENTEEN_NEW_AND_THIRTY_FOUR_COMPLETE_PREVIOUS_SB40_MODELS_REQUIRED')
    if (model_identity(plan['game'])!=model_identity(prior['game'])
            or catalog.get('profile_settings')!=previous.get('profile_settings')):
        raise StrategyError('SB40_PRIORS_MENU_GEOMETRY_OR_ANTE_CHANGED')
    identity=lambda c:(canonical_flop(c['board']),c['policy_sha256'],c['file_sha256'],c['tag'])
    if {identity(c) for c in previous['cases']}!={identity(c) for c in plan['preexisting_models']}:
        raise StrategyError('SB40_PREVIOUS_THIRTY_FOUR_IDENTITIES_CHANGED')
    rows=[dict(c,source_ordinal=c.get('source_ordinal',c['ordinal']),ordinal=i+1)
          for i,c in enumerate(previous['cases']+catalog['cases'])]
    if len({canonical_flop(c['board']) for c in rows})!=51:
        raise StrategyError('FIFTY_ONE_SUIT_DISTINCT_SB40_MODELS_REQUIRED')
    return dict(catalog,cases=rows,planned_new_flops=51,published_new_flops=51,native_target_met_flops=51,
        full_model_count=51,suit_aliases_counted_as_models=False,pilot_tag=SB40_TAG,
        source_catalogs=previous['source_catalogs']+[dict(tag=SB40_COMPLETE51_TAG,plan_sha256=plan['plan_sha256'])])


def load_family(family,asset=None,*,new_only=False):
    with metadata_snapshot():return _load_family(family,asset,new_only=new_only)


def _load_family(family,asset=None,*,new_only=False):
    tags={'btn32':CLOSE32_TAG,'sb40':SB40_TAG,'sb40-next16':SB40_NEXT16_TAG,'sb40-34':SB40_COMPLETE34_TAG,'sb40-51':SB40_COMPLETE51_TAG}
    tags.update({f'sb40-{n}':tag for n,tag in SB40_SERIES_TAGS.items()})
    tag=tags.get(family)
    if tag is None:raise StrategyError('KNOWN_FAMILY_REQUIRED')
    validated_parent=None
    if tag==SB40_COMPLETE51_TAG or tag in SB40_SERIES_TAGS.values():
        catalog,name,validated_parent=_load_campaign(tag,asset,return_parent=True)
    else:
        catalog,name=load_campaign(tag,asset)
    if family=='btn32' and not new_only:
        old,_=load_catalog('batch-catalog-43764947533.json')
        catalog=combine_thirty_two(catalog,old,pilot_manifest())
    if family=='sb40-next16' and not new_only:
        pilot,_=load_campaign(SB40_TAG,'batch-catalog-43777381626.json')
        catalog=combine_sb40_seventeen(catalog,pilot)
    if family=='sb40-34' and not new_only:
        previous,_=load_family('sb40-next16','batch-catalog-43783594940.json')
        catalog=combine_sb40_thirty_four(catalog,previous)
    if family=='sb40-51' and not new_only:
        previous=validated_parent
        catalog=combine_sb40_fifty_one(catalog,previous)
    if tag in SB40_SERIES_TAGS.values() and not new_only:
        from strategy.sb40_series import combine_series
        catalog=combine_series(catalog,validated_parent)
    return catalog,name


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--family',required=True,choices=('btn32','sb40','sb40-next16','sb40-34','sb40-51','sb40-68','sb40-85','sb40-102'))
    p.add_argument('--output');p.add_argument('--ordinals',nargs='+',type=int);p.add_argument('--catalog-asset')
    p.add_argument('--new-only',action='store_true');p.add_argument('--resume',action='store_true')
    args=p.parse_args(argv)
    output=args.output or ('runtime/hu/'+args.family+'-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    if Path(output).exists() and not args.resume:raise StrategyError('BATCH_OUTPUT_MUST_BE_NEW_OR_EXPLICIT_MANAGED_RESUME')
    catalog,asset=load_family(args.family,args.catalog_asset,new_only=args.new_only)
    receipt=install_catalog(output,catalog,asset,ordinals=args.ordinals,resume=args.resume)
    print('Familia:',args.family,'| modelos consultados:',receipt['total_models']);return 0


if __name__=='__main__':raise SystemExit(main())
