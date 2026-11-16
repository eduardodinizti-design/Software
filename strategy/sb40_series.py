"""Three conditional batches of seventeen, preserving complete verified ancestry."""
import copy
from functools import lru_cache
import json
from pathlib import Path
import re

from strategy.batch_archive import REPOSITORY,verify_remote_parts
from strategy.batch_download import read_json,metadata_snapshot
from strategy.batch_jobs import canonical_flop,catalogue_flops,case_id
from strategy.blind_war import SB40_TAG,SB40_COMPLETE51_TAG,SB40_SERIES_TAGS
from strategy.campaign import make_campaign,model_identity,validate_campaign_plan
from strategy.sb40_progression import (PrerequisitePending,check_asset,read_asset,identity,read_intent,
    PARENT_PLAN,DOC as PARENT_INTENT_DOC)
from strategy.state_contract import StrategyError,digest

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'docs/software-hu-sb40-to102-20261116'
FIRST_PARENT_RUN='43807544505'
CONTROLLER_PATH='.github/workflows/hu-sb40-to102.yml'
CONTROLLER_BRANCH='feat/hu-sb40-to102-20261116'


def family_tag(count):
    if count==51:return SB40_COMPLETE51_TAG
    if count not in SB40_SERIES_TAGS:raise StrategyError('ONLY_RESERVED_SB40_SERIES_TARGETS_ALLOWED')
    return SB40_SERIES_TAGS[count]


@lru_cache(maxsize=1)
def _make_series_intents(parent_plan_bytes,parent_intent_bytes):
    first=read_intent();boards=copy.deepcopy(first['previous_and_in_progress_boards'])
    boards.extend(copy.deepcopy(c['board']) for c in first['cases'])
    forbidden={canonical_flop(b) for b in boards+first['preserved_holdout_flops']}
    available=[b for b in catalogue_flops(256) if canonical_flop(b) not in forbidden]
    result={};parent_intent=first['intent_sha256']
    for index,count in enumerate(SB40_SERIES_TAGS):
        selected=available[17*index:17*(index+1)]
        if len(selected)!=17:raise StrategyError('SEVENTEEN_DISTINCT_RESERVED_BOARDS_REQUIRED')
        value=dict(schema='software.hu-sb40-series-intent.v1',status='WAITING_FOR_COMPLETE_SAVED_WINDOWS_VERIFIED_PARENT',
            tag=family_tag(count),parent_tag=family_tag(count-17),parent_intent_sha256=parent_intent,
            required_previous_models=count-17,new_models=17,target_total_models=count,
            model_sha256=first['model_sha256'],profile_settings=copy.deepcopy(first['profile_settings']),
            settings=copy.deepcopy(first['settings']),preserved_holdout_flops=copy.deepcopy(first['preserved_holdout_flops']),
            previous_and_in_progress_boards=copy.deepcopy(boards),
            cases=[dict(ordinal=i+1,board=b,case_id=case_id(b)) for i,b in enumerate(selected)],
            max_parallel_hosts=8,workers_per_host=1,catalog_protocol='run-attempt-v1',
            policy_ids_created_only_after_actual_parent_completion=True,pppoker_windows_validated=False)
        value['intent_sha256']=digest(value);result[count]=value;parent_intent=value['intent_sha256']
        boards.extend(copy.deepcopy(selected))
    return result


def make_series_intents():
    # Only deterministic enumeration is cached, keyed by both local frozen source files.
    return copy.deepcopy(_make_series_intents(PARENT_PLAN.read_bytes(),
        (PARENT_INTENT_DOC/'sb40-51-intent.json').read_bytes()))


def read_series_intent(count):
    expected=make_series_intents()[count]
    actual=json.loads((DOC/f'sb40-{count}-intent.json').read_text())
    if actual!=expected:raise StrategyError('RESERVED_SERIES_GAME_OR_BOARDS_CHANGED')
    return actual


def parent_run_id(target,proof_ref=None,parent_run=None):
    family_tag(target)
    run=FIRST_PARENT_RUN if target==68 else (parent_run or (proof_ref or {}).get('run_id'))
    if not isinstance(run,str) or not re.fullmatch(r'[0-9]+',run):
        raise StrategyError('EXPLICIT_PARENT_CONTROLLER_RUN_REQUIRED')
    if proof_ref and (proof_ref.get('run_id')!=run or proof_ref.get('tag')!=family_tag(target-17)):
        raise StrategyError('PINNED_PARENT_RUN_OR_RELEASE_CHANGED')
    return run


def checked_parent_milestone(target,run_id,run,delivery,proof_attempt,jobs=()):
    """Later stages depend on a completed delivery job, not the unfinished controller."""
    expected_path=('.github/workflows/hu-sb40-complete51.yml' if target==68 else CONTROLLER_PATH)
    expected_branch=('feat/hu-sb40-complete51-20261116' if target==68 else CONTROLLER_BRANCH)
    if (str(run.get('id'))!=run_id or run.get('path')!=expected_path
            or run.get('head_branch')!=expected_branch or run.get('head_sha')!=delivery.get('source_commit')):
        raise StrategyError('PARENT_WORKFLOW_SOURCE_OR_BRANCH_DIFFERS')
    if target==68:
        if run.get('status')!='completed':raise PrerequisitePending('FIRST_PARENT_WINDOWS_WORKFLOW_STILL_RUNNING')
        if run.get('conclusion')!='success':raise StrategyError('FIRST_PARENT_WINDOWS_WORKFLOW_FAILED')
        return dict(method='COMPLETE_PARENT_WORKFLOW',run_id=run_id,conclusion='success')
    name=f'Deliver SB40 {target-17} and verify publication'
    matches=[j for j in jobs if j.get('name')==name and j.get('run_attempt')==proof_attempt]
    if not matches:raise PrerequisitePending('PREVIOUS_DELIVERY_JOB_NOT_YET_VISIBLE')
    job=max(matches,key=lambda j:j['id'])
    if job.get('status')!='completed':raise PrerequisitePending('PREVIOUS_DELIVERY_JOB_STILL_RUNNING')
    if job.get('conclusion')!='success':raise StrategyError('PREVIOUS_DELIVERY_JOB_DID_NOT_PASS')
    return dict(method='COMPLETE_PREVIOUS_DELIVERY_JOB_WITHIN_THE_SAME_CONTROLLER',run_id=run_id,
        job_id=job['id'],job_name=name,run_attempt=proof_attempt,conclusion='success')


def run_jobs(run_id):
    rows=[];page=1
    while True:
        value=read_json(f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{run_id}/jobs?filter=all&per_page=100&page={page}')
        rows.extend(value['jobs'])
        if len(value['jobs'])<100:break
        page+=1
        if page>20:raise StrategyError('PARENT_JOB_HISTORY_EXCEEDS_BOUNDED_METADATA_LIMIT')
    return rows


def checkpoint_parent(target,full,delivery,proof,proof_ref,releases,run,jobs=()):
    count=target-17;tag=family_tag(count);intent=read_series_intent(target)
    run_id=parent_run_id(target,proof_ref)
    pattern=rf'publicacao-final-verificada-sb40-{count}-{run_id}-a([0-9]+)\.json'
    matched=re.fullmatch(pattern,proof_ref.get('name',''))
    if not matched:raise StrategyError('EXACT_PARENT_PUBLICATION_MARKER_REQUIRED')
    milestone=checked_parent_milestone(target,run_id,run,delivery,int(matched[1]),jobs)
    cases=full.get('cases',[]);plan=full.get('_original_plan',{})
    schema=('software.hu-sb40-51-publication-check.v1' if count==51 else 'software.hu-sb40-series-publication-check.v1')
    if (full.get('tag')!=tag or full.get('status')!='COMPLETE' or len(cases)!=count
            or len({canonical_flop(c['board']) for c in cases})!=count
            or model_identity(plan['game'])!=intent['model_sha256']
            or full.get('profile_settings')!=intent['profile_settings']
            or delivery.get('status')!='PASS' or delivery.get('complete_distinct_flop_models')!=count
            or delivery.get('previous_saved_flop_models')!=count-17 or delivery.get('new_complete_flop_models')!=17
            or delivery.get('new_windows_policy_pass')!=17 or delivery.get('new_confirmed_synthetic_hands')!=17
            or delivery.get('new_json_street_queries')!=51 or delivery.get('new_exact_suit_street_queries')!=51
            or delivery.get('all_new_workers_exited') is not True or delivery.get('all_new_native_temporaries_removed') is not True
            or delivery.get('pppoker_windows_validated') is not False
            or delivery.get('context')!=plan['game']['context'] or delivery.get('profile_settings')!=intent['profile_settings']
            or delivery.get('plan_sha256')!=full.get('plan_sha256')
            or proof.get('schema')!=schema or proof.get('status')!='PASS' or proof.get('complete_models')!=count
            or proof.get('complete_prior_models_preserved')!=count-17 or str(proof.get('windows_run'))!=run_id
            or proof.get('new_confirmed_json_histories')!=17 or proof.get('new_json_street_queries')!=51
            or proof.get('new_exact_suit_street_queries')!=51 or proof.get('zip_crc_all_entries_valid') is not True
            or proof.get('pppoker_windows_validated') is not False
            or proof.get('native_catalog_asset')!=delivery.get('catalog_asset')
            or not re.fullmatch(r'batch-catalog-'+run_id+r'-a[0-9]+\.json',proof.get('native_catalog_asset',''))
            or {identity(c) for c in cases}!={identity(c) for c in delivery.get('inventory',[])}):
        raise StrategyError('COMPLETE_SAVED_ACTUALLY_WINDOWS_VERIFIED_PARENT_REQUIRED')
    by_tag={t:{a['name']:a for a in release['assets']} for t,release in releases.items()}
    archived=[]
    for case in cases:
        if (case.get('native_target_met') is not True or not case.get('coverage',{}).get('structurally_complete')
                or case.get('worker_exited') is not True or case.get('temporary_cleanup_verified') is not True):
            raise StrategyError('A_PARENT_POLICY_IS_PARTIAL_OR_NOT_CLOSED')
        verify_remote_parts(case,list(by_tag[case['tag']].values()))
        archived.extend(dict(tag=case['tag'],**part) for part in case['parts'])
    metadata=proof.get('metadata_hashes',[])
    expected_summary='entrega-sb40-'+str(count)+'-'+run_id+'-a'+matched[1]+'.json'
    if len(metadata)!=5 or expected_summary not in {m['name'] for m in metadata}:
        raise StrategyError('EXACT_SAVED_PARENT_REPORT_AND_SOURCE_MANIFEST_REQUIRED')
    for item in metadata:check_asset(by_tag[item['tag']].get(item['name']),item)
    check_asset(by_tag[tag].get(proof_ref['name']),proof_ref)
    check_asset(by_tag[tag].get(proof['source_asset']),
        dict(name=proof['source_asset'],bytes=proof['source_bytes'],sha256=proof['source_sha256']))
    if (sum(c['policy_file_bytes'] for c in cases)!=delivery['total_policy_file_bytes']
            or sum(c['coverage']['public_nodes'] for c in cases)!=delivery['total_public_nodes']):
        raise StrategyError('SAVED_PARENT_TOTALS_CHANGED')
    from tools.finalize_hu_campaign import checked_results
    from tools.finalize_hu_sb40_complete51 import checked_root_review
    checked_results(dict(full,cases=[dict(c,ordinal=c['source_ordinal']) for c in cases[-17:]]),delivery['windows_cases'])
    for row in delivery['windows_cases']:checked_root_review(row)
    histories=proof.get('published_histories_checked',[])
    if (len(histories)!=17 or any(h.get('status')!='PASS' or h.get('json_streets')!=3 for h in histories)
            or {h['policy_sha256'] for h in histories}!={c['policy_sha256'] for c in cases[-17:]}):
        raise StrategyError('ALL_SEVENTEEN_PUBLISHED_PARENT_HAND_HISTORIES_REQUIRED')
    previous=delivery.get('prerequisite_checkpoint',{})
    body=dict(previous);claimed=body.pop('checkpoint_sha256',None)
    if (previous.get('status')!='PASS' or previous.get('complete_saved_models')!=count-17 or digest(body)!=claimed
            or claimed!=plan.get('prerequisite_checkpoint_sha256')
            or {identity(c) for c in previous['preserved_models']}!={identity(c) for c in cases[:-17]}):
        raise StrategyError('UNCHANGED_ALL_PREVIOUS_GENERATIONS_CHECKPOINT_REQUIRED')
    value=dict(schema='software.hu-sb40-series-saved-checkpoint.v1',status='PASS',complete_saved_models=count,
        complete_distinct_flops=count,model_sha256=intent['model_sha256'],prior_plan_sha256=plan['plan_sha256'],
        prior_catalog_asset=proof['native_catalog_asset'],profile_settings=full['profile_settings'],
        preserved_models=[{k:c[k] for k in ('board','policy_sha256','file_sha256','tag')} for c in cases],
        archived_policy_parts=archived,remote_archive_parts_verified=len(archived),
        total_saved_policy_bytes=delivery['total_policy_file_bytes'],public_nodes=delivery['total_public_nodes'],
        complete_windows_downloads_previously_passed=count,parent_delivery_proof=proof_ref,
        previous_checkpoint_sha256=claimed,source_asset=proof['source_asset'],
        source_sha256=proof['source_sha256'],source_bytes=proof['source_bytes'],verified_evidence=metadata,
        windows_workflow_run=run_id,completed_delivery_milestone=milestone,
        verification_scope='CURRENT_REMOTE_SHA256_VS_COMPLETED_FULL_WINDOWS_BANK_AND_PUBLISHED_HISTORY_CHECKS',
        all_policy_bytes_redownloaded_in_this_check=False,
        cfr_checkpoint_scope='CONVERGENCE_LOGS_AND_COMPLETE_FINAL_POLICIES_NOT_EVERY_RESUMABLE_CFR_ITERATION',
        pppoker_windows_validated=False)
    value['checkpoint_sha256']=digest(value);return value


def load_series_parent(target,proof_ref=None,*,parent_run=None):
    with metadata_snapshot():
        from strategy.campaign_download import load_family
        count=target-17;tag=family_tag(count);run_id=parent_run_id(target,proof_ref,parent_run)
        remote=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}')
        assets={a['name']:a for a in remote['assets']}
        pattern=rf'publicacao-final-verificada-sb40-{count}-{run_id}-a[0-9]+\.json'
        if proof_ref:
            if not re.fullmatch(pattern,proof_ref.get('name','')):raise StrategyError('EXPECTED_PINNED_PARENT_PUBLICATION')
            asset=assets.get(proof_ref['name']);check_asset(asset,proof_ref)
        else:
            options=[a for a in assets.values() if a['state']=='uploaded' and re.fullmatch(pattern,a['name'])]
            if not options:raise PrerequisitePending('WAITING_FOR_COMPLETE_SAVED_PARENT_PUBLICATION_RECEIPT')
            asset=max(options,key=lambda a:a['id'])
            proof_ref=dict(tag=tag,run_id=run_id,name=asset['name'],bytes=asset['size'],
                sha256=asset.get('digest','').removeprefix('sha256:'))
        proof=read_asset(asset,tag);stem=asset['name'][len(f'publicacao-final-verificada-sb40-{count}-'):-5]
        delivery=read_asset(assets[f'entrega-sb40-{count}-{stem}.json'],tag)
        run=read_json(f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{run_id}')
        jobs=run_jobs(run_id) if target!=68 else []
        full,_=load_family('sb40-'+str(count),proof['native_catalog_asset'])
        releases={tag:remote}
        for t in {c['tag'] for c in full['cases']}-{tag}:
            releases[t]=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{t}')
        return full,checkpoint_parent(target,full,delivery,proof,proof_ref,releases,run,jobs)


def make_series_plan(target,previous,checkpoint,intent):
    family_tag(target);count=target-17
    body=dict(checkpoint);claimed=body.pop('checkpoint_sha256',None)
    if (intent!=read_series_intent(target) or checkpoint.get('status')!='PASS'
            or checkpoint.get('complete_saved_models')!=count or digest(body)!=claimed
            or previous.get('status')!='COMPLETE' or len(previous.get('cases',[]))!=count
            or model_identity(previous['_original_plan']['game'])!=intent['model_sha256']
            or checkpoint['profile_settings']!=intent['profile_settings']
            or {identity(c) for c in previous['cases']}!={identity(c) for c in checkpoint['preserved_models']}
            or {canonical_flop(c['board']) for c in previous['cases']}!=
                {canonical_flop(b) for b in intent['previous_and_in_progress_boards']}):
        raise StrategyError('NO_NEW_SOLVE_BEFORE_ALL_PRIOR_MODELS_ARE_SAVED_AND_MATCH_THE_INTENT')
    plan=make_campaign(copy.deepcopy(previous['_original_plan']['game']),[c['board'] for c in intent['cases']],
        tag=family_tag(target),label=f'SB x BB 40 BB NVT: 17 novos flops, {target} acumulados apos validar os {count}',
        existing=checkpoint['preserved_models'],goal_models=target,settings=intent['settings'],profile_settings=intent['profile_settings'])
    plan.update(prerequisite_checkpoint_sha256=claimed,pilot_tag=SB40_TAG,catalog_protocol='run-attempt-v1',
        intent_sha256=intent['intent_sha256'],parent_delivery_proof=checkpoint['parent_delivery_proof'],
        preexisting_catalog=dict(tag=family_tag(count),asset=checkpoint['prior_catalog_asset'],
            plan_sha256=previous['_original_plan']['plan_sha256']))
    plan.pop('plan_sha256');plan['plan_sha256']=digest(plan);return validate_campaign_plan(plan)


def validate_series_plan(plan,expected_sha=None):
    with metadata_snapshot():
        validate_campaign_plan(plan);target=plan['target_total_models']
        if family_tag(target)!=plan['tag']:raise StrategyError('EXACT_SERIES_TARGET_RELEASE_REQUIRED')
        if expected_sha and expected_sha!=plan['plan_sha256']:raise StrategyError('FROZEN_RUNTIME_PLAN_SHA_CHANGED')
        previous,checkpoint=load_series_parent(target,plan.get('parent_delivery_proof'))
        if plan!=make_series_plan(target,previous,checkpoint,read_series_intent(target)):
            raise StrategyError('RUNTIME_PLAN_IS_NOT_THE_EXACT_DERIVATION_FROM_THE_SAVED_PARENT')
        return previous,checkpoint


def combine_series(catalog,previous):
    plan=catalog['_original_plan'];target=plan['target_total_models'];family_tag(target)
    if (catalog.get('tag')!=family_tag(target) or catalog.get('status')!='COMPLETE' or len(catalog.get('cases',[]))!=17
            or previous.get('tag')!=family_tag(target-17) or previous.get('status')!='COMPLETE'
            or len(previous.get('cases',[]))!=target-17
            or model_identity(plan['game'])!=model_identity(previous['_original_plan']['game'])
            or catalog.get('profile_settings')!=previous.get('profile_settings')
            or {identity(c) for c in previous['cases']}!={identity(c) for c in plan['preexisting_models']}):
        raise StrategyError('EXACT_SAVED_PARENT_AND_SEVENTEEN_NEW_MODELS_REQUIRED')
    rows=[dict(c,source_ordinal=c.get('source_ordinal',c['ordinal']),ordinal=i+1)
        for i,c in enumerate(previous['cases']+catalog['cases'])]
    if len({canonical_flop(c['board']) for c in rows})!=target:raise StrategyError('ALL_SERIES_MODELS_MUST_BE_SUIT_DISTINCT')
    return dict(catalog,cases=rows,planned_new_flops=target,published_new_flops=target,native_target_met_flops=target,
        full_model_count=target,suit_aliases_counted_as_models=False,pilot_tag=SB40_TAG,
        source_catalogs=previous['source_catalogs']+[dict(tag=family_tag(target),plan_sha256=plan['plan_sha256'])])
