"""Derive the next 17 only from the actual saved and Windows-verified 34."""
import copy
import hashlib
import json
from pathlib import Path
import re

from strategy.batch_archive import REPOSITORY,verify_remote_parts
from strategy.batch_download import ASSET_BASE,fetch,read_json,safe_name
from strategy.batch_jobs import canonical_flop,catalogue_flops,case_id
from strategy.blind_war import SB40_TAG,SB40_COMPLETE34_TAG,SB40_COMPLETE51_TAG
from strategy.campaign import checked_campaign_plan,make_campaign,model_identity,validate_campaign_plan
from strategy.state_contract import StrategyError,digest

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'docs/software-hu-sb40-complete51-20261116'
PARENT_PLAN=ROOT/'docs/software-hu-sb40-complete34-20261116/sb40-complete34-plan.json'
PARENT_SHA='f070d2c0289dd6eef328e48da8fbecd001c6bf483380e987a7208ea730b63d67'
PARENT_NATIVE='43799276504'
PARENT_WINDOWS='43800302038'
PARENT_CATALOG='batch-catalog-'+PARENT_NATIVE+'.json'


class PrerequisitePending(StrategyError):
    pass


def identity(case):
    return canonical_flop(case['board']),case['policy_sha256'],case['file_sha256'],case['tag']


def make_intent(parent):
    validate_campaign_plan(parent)
    if parent['plan_sha256']!=PARENT_SHA or parent['tag']!=SB40_COMPLETE34_TAG:
        raise StrategyError('EXACT_FROZEN_PARENT_34_STUDY_REQUIRED')
    reserved=parent['preexisting_models']+parent['cases']
    forbidden={canonical_flop(c['board']) for c in reserved}|{canonical_flop(b) for b in parent['preserved_holdout_flops']}
    boards=[b for b in catalogue_flops(100) if canonical_flop(b) not in forbidden][:17]
    value=dict(schema='software.hu-sb40-51-intent.v1',status='WAITING_FOR_COMPLETE_SAVED_WINDOWS_VERIFIED_34',
        tag=SB40_COMPLETE51_TAG,parent_tag=SB40_COMPLETE34_TAG,parent_plan_sha256=PARENT_SHA,
        parent_native_run=PARENT_NATIVE,parent_windows_run=PARENT_WINDOWS,parent_catalog_asset=PARENT_CATALOG,
        required_previous_models=34,new_models=17,target_total_models=51,
        model_sha256=model_identity(parent['game']),profile_settings=parent['profile_settings'],
        settings=parent['settings'],preserved_holdout_flops=parent['preserved_holdout_flops'],
        previous_and_in_progress_boards=[c['board'] for c in reserved],
        cases=[dict(ordinal=i+1,board=b,case_id=case_id(b)) for i,b in enumerate(boards)],
        max_parallel_hosts=8,workers_per_host=1,
        policy_ids_created_only_after_actual_parent_completion=True,pppoker_windows_validated=False)
    value['intent_sha256']=digest(value);return value


def read_intent():
    expected=make_intent(checked_campaign_plan(PARENT_PLAN))
    actual=json.loads((DOC/'sb40-51-intent.json').read_text())
    if actual!=expected:raise StrategyError('RESERVED_NEXT_SEVENTEEN_OR_FROZEN_PARENT_CHANGED')
    return actual


def check_asset(asset,expected):
    if (not asset or asset.get('state')!='uploaded' or asset.get('size')!=expected['bytes']
            or asset.get('digest')!='sha256:'+expected['sha256']):
        raise StrategyError('SAVED_PARENT_ARTIFACT_MISSING_OR_CHANGED:'+expected['name'])


def read_asset(asset,tag):
    if not safe_name(asset['name']):raise StrategyError('UNSAFE_PARENT_ASSET_NAME')
    with fetch(ASSET_BASE+tag+'/'+asset['name']) as source:raw=source.read(32*1024**2+1)
    check_asset(asset,dict(name=asset['name'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    if len(raw)>32*1024**2:raise StrategyError('PARENT_EVIDENCE_TOO_LARGE')
    return json.loads(raw)


def checkpoint34(full,delivery,proof,proof_ref,releases,parent_run):
    """Current remote hashes back the completed full-file Windows receipts."""
    if parent_run.get('status')!='completed':raise PrerequisitePending('PARENT_WINDOWS_DELIVERY_STILL_RUNNING')
    if parent_run.get('conclusion')!='success':raise StrategyError('PARENT_WINDOWS_DELIVERY_DID_NOT_PASS')
    cases=full.get('cases',[])
    if (full.get('tag')!=SB40_COMPLETE34_TAG or full.get('status')!='COMPLETE' or len(cases)!=34
            or full.get('plan_sha256')!=PARENT_SHA or len({canonical_flop(c['board']) for c in cases})!=34
            or delivery.get('status')!='PASS' or delivery.get('complete_distinct_flop_models')!=34
            or delivery.get('new_complete_flop_models')!=17 or delivery.get('new_windows_policy_pass')!=17
            or delivery.get('new_confirmed_synthetic_hands')!=17
            or delivery.get('new_json_street_queries')!=51 or delivery.get('new_exact_suit_street_queries')!=51
            or delivery.get('all_new_workers_exited') is not True or delivery.get('all_new_native_temporaries_removed') is not True
            or delivery.get('pppoker_windows_validated') is not False
            or proof.get('schema')!='software.hu-sb40-34-publication-check.v1' or proof.get('status')!='PASS'
            or proof.get('complete_models')!=34 or proof.get('new_confirmed_json_histories')!=17
            or proof.get('zip_crc_all_entries_valid') is not True or str(proof.get('windows_run'))!=PARENT_WINDOWS
            or proof.get('native_catalog_asset')!=PARENT_CATALOG
            or {identity(c) for c in cases}!={identity(c) for c in delivery.get('inventory',[])}):
        raise StrategyError('ALL_THIRTY_FOUR_SAVED_AND_ACTUALLY_WINDOWS_VERIFIED_MODELS_REQUIRED')
    expected_context=full['_original_plan']['game']['context']
    if delivery.get('context')!=expected_context or delivery.get('profile_settings')!=full['profile_settings']:
        raise StrategyError('PARENT_ARRIVAL_PRIORS_OR_ANTE_CHANGED')
    by_tag={tag:{a['name']:a for a in value['assets']} for tag,value in releases.items()}
    archived=[]
    for case in cases:
        if (case.get('native_target_met') is not True or not case.get('coverage',{}).get('structurally_complete')
                or case.get('worker_exited') is not True or case.get('temporary_cleanup_verified') is not True):
            raise StrategyError('A_PARENT_POLICY_IS_PARTIAL_OR_NOT_CLOSED')
        verify_remote_parts(case,list(by_tag[case['tag']].values()))
        archived.extend(dict(tag=case['tag'],**part) for part in case['parts'])
    for item in proof['metadata_hashes']:check_asset(by_tag[item['tag']].get(item['name']),item)
    check_asset(by_tag[SB40_COMPLETE34_TAG].get(proof_ref['name']),proof_ref)
    check_asset(by_tag[SB40_COMPLETE34_TAG].get(proof['source_asset']),
        dict(name=proof['source_asset'],bytes=proof['source_bytes'],sha256=proof['source_sha256']))
    if (sum(c['policy_file_bytes'] for c in cases)!=delivery['total_policy_file_bytes']
            or sum(c['coverage']['public_nodes'] for c in cases)!=delivery['total_public_nodes']):
        raise StrategyError('SAVED_PARENT_TOTALS_CHANGED')
    from tools.finalize_hu_campaign import checked_results
    checked_results(dict(full,cases=[dict(c,ordinal=c['source_ordinal']) for c in cases[17:]]),delivery['windows_cases'])
    histories=proof.get('published_histories_checked',[])
    if (len(histories)!=17 or any(h.get('status')!='PASS' or h.get('json_streets')!=3 for h in histories)
            or {h['policy_sha256'] for h in histories}!={c['policy_sha256'] for c in cases[17:]}):
        raise StrategyError('ALL_SEVENTEEN_PUBLISHED_PARENT_HAND_HISTORIES_REQUIRED')
    previous=delivery.get('prerequisite_checkpoint',{})
    body=dict(previous);claimed=body.pop('checkpoint_sha256',None)
    if (previous.get('status')!='PASS' or previous.get('complete_saved_models')!=17 or digest(body)!=claimed
            or claimed!=full['_original_plan']['prerequisite_checkpoint_sha256']
            or {identity(c) for c in previous['preserved_models']}!={identity(c) for c in cases[:17]}):
        raise StrategyError('THE_FIRST_SEVENTEEN_SAVED_CHECKPOINT_IS_REQUIRED')
    value=dict(schema='software.hu-sb40-34-saved-checkpoint.v1',status='PASS',complete_saved_models=34,
        complete_distinct_flops=34,model_sha256=model_identity(full['_original_plan']['game']),
        prior_plan_sha256=PARENT_SHA,prior_catalog_asset=PARENT_CATALOG,profile_settings=full['profile_settings'],
        preserved_models=[{k:c[k] for k in ('board','policy_sha256','file_sha256','tag')} for c in cases],
        archived_policy_parts=archived,remote_archive_parts_verified=len(archived),
        total_saved_policy_bytes=delivery['total_policy_file_bytes'],public_nodes=delivery['total_public_nodes'],
        complete_windows_downloads_previously_passed=34,parent_delivery_proof=proof_ref,
        previous_first17_checkpoint_sha256=claimed,source_asset=proof['source_asset'],
        source_sha256=proof['source_sha256'],source_bytes=proof['source_bytes'],
        verified_evidence=proof['metadata_hashes'],windows_workflow_run=PARENT_WINDOWS,
        verification_scope='CURRENT_REMOTE_SHA256_VS_COMPLETED_FULL_WINDOWS_BANK_AND_PUBLISHED_HISTORY_CHECKS',
        all_policy_bytes_redownloaded_in_this_check=False,
        cfr_checkpoint_scope='CONVERGENCE_LOGS_AND_COMPLETE_FINAL_POLICIES_NOT_EVERY_RESUMABLE_CFR_ITERATION',
        pppoker_windows_validated=False)
    value['checkpoint_sha256']=digest(value);return value


def load_parent34(proof_ref=None):
    from strategy.campaign_download import load_family
    remote=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{SB40_COMPLETE34_TAG}')
    assets={a['name']:a for a in remote['assets']}
    pattern=r'publicacao-final-verificada-sb40-34-'+PARENT_WINDOWS+r'-a[0-9]+\.json'
    if proof_ref:
        if not re.fullmatch(pattern,proof_ref.get('name','')):raise StrategyError('EXPECTED_PARENT_PROOF_FROM_THE_KNOWN_WINDOWS_RUN')
        asset=assets.get(proof_ref['name']);check_asset(asset,proof_ref)
    else:
        options=[a for a in assets.values() if a['state']=='uploaded' and re.fullmatch(pattern,a['name'])]
        if not options:raise PrerequisitePending('WAITING_FOR_THE_COMPLETE_SAVED_34_PUBLICATION_RECEIPT')
        asset=max(options,key=lambda a:a['id'])
        proof_ref=dict(name=asset['name'],bytes=asset['size'],sha256=asset.get('digest','').removeprefix('sha256:'))
    proof=read_asset(asset,SB40_COMPLETE34_TAG)
    stem=asset['name'][len('publicacao-final-verificada-sb40-34-'):-5]
    summary_name='entrega-sb40-34-'+stem+'.json'
    delivery=read_asset(assets[summary_name],SB40_COMPLETE34_TAG)
    run=read_json(f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{PARENT_WINDOWS}')
    full,_=load_family('sb40-34',PARENT_CATALOG)
    releases={SB40_COMPLETE34_TAG:remote}
    for tag in {c['tag'] for c in full['cases']} - {SB40_COMPLETE34_TAG}:
        releases[tag]=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}')
    return full,checkpoint34(full,delivery,proof,proof_ref,releases,run)


def make_plan51(previous,checkpoint,intent):
    body=dict(checkpoint);claimed=body.pop('checkpoint_sha256',None)
    if (checkpoint.get('status')!='PASS' or checkpoint.get('complete_saved_models')!=34 or digest(body)!=claimed
            or previous.get('status')!='COMPLETE' or len(previous.get('cases',[]))!=34
            or model_identity(previous['_original_plan']['game'])!=intent['model_sha256']
            or checkpoint['profile_settings']!=intent['profile_settings']
            or {identity(c) for c in previous['cases']}!={identity(c) for c in checkpoint['preserved_models']}):
        raise StrategyError('NO_NEW_SOLVE_BEFORE_ALL_THIRTY_FOUR_ARE_SAVED_AND_MATCH_THE_INTENT')
    if {canonical_flop(c['board']) for c in previous['cases']}!={canonical_flop(b) for b in intent['previous_and_in_progress_boards']}:
        raise StrategyError('THE_COMPLETED_PARENT_BOARDS_DIFFER_FROM_THE_RESERVED_THIRTY_FOUR')
    plan=make_campaign(copy.deepcopy(previous['_original_plan']['game']),[c['board'] for c in intent['cases']],
        tag=SB40_COMPLETE51_TAG,label='SB x BB 40 BB NVT: 17 novos flops, 51 acumulados apos validar os 34',
        existing=checkpoint['preserved_models'],goal_models=51,settings=intent['settings'],profile_settings=intent['profile_settings'])
    plan['prerequisite_checkpoint_sha256']=checkpoint['checkpoint_sha256']
    plan['pilot_tag']=SB40_TAG
    plan['catalog_protocol']='run-attempt-v1'
    plan['intent_sha256']=intent['intent_sha256'];plan['parent_delivery_proof']=checkpoint['parent_delivery_proof']
    plan['preexisting_catalog']=dict(tag=SB40_COMPLETE34_TAG,asset=PARENT_CATALOG,plan_sha256=PARENT_SHA)
    plan.pop('plan_sha256');plan['plan_sha256']=digest(plan)
    return validate_campaign_plan(plan)


def validate_derived_plan51(plan,expected_sha=None):
    validate_campaign_plan(plan)
    if expected_sha and plan['plan_sha256']!=expected_sha:raise StrategyError('FROZEN_RUNTIME_PLAN_SHA_CHANGED')
    previous,checkpoint=load_parent34(plan.get('parent_delivery_proof'))
    if plan!=make_plan51(previous,checkpoint,read_intent()):
        raise StrategyError('RUNTIME_PLAN_IS_NOT_THE_EXACT_DERIVATION_FROM_THE_SAVED_34')
    return previous,checkpoint
