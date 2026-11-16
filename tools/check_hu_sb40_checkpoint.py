"""Require the actual saved seventeen-model bank before another SB40 solve."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import verify_remote_parts
from strategy.batch_jobs import atomic_json,canonical_flop
from strategy.blind_war import SB40_TAG,SB40_NEXT16_TAG
from strategy.campaign import model_identity
from strategy.campaign_download import load_family
from strategy.state_contract import StrategyError,digest
from tools.collect_hu_campaign_evidence import release
from tools.finalize_hu_campaign import checked_results

ROOT=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'docs/software-hu-sb40-next16-20261116'
PRIOR_CATALOG='batch-catalog-43783594940.json'


def saved_checkpoint(full,delivery,publication,releases):
    """Remote digests must still match the previously downloaded complete files."""
    cases=full.get('cases',[])
    identity=lambda c:(canonical_flop(c['board']),c['policy_sha256'],c['file_sha256'],c['tag'])
    if (full.get('status')!='COMPLETE' or len(cases)!=17
            or len({canonical_flop(c['board']) for c in cases})!=17
            or delivery.get('status')!='PASS' or delivery.get('complete_distinct_flop_models')!=17
            or delivery.get('new_windows_policy_pass')!=16
            or publication.get('status')!='PASS' or publication.get('complete_models')!=17
            or publication.get('new_confirmed_json_histories')!=16
            or publication.get('zip_crc_all_entries_valid') is not True
            or {identity(c) for c in cases}!={identity(c) for c in delivery.get('inventory',[])}):
        raise StrategyError('THE_PREVIOUS_SEVENTEEN_COMPLETE_SAVED_MODELS_ARE_REQUIRED')
    by_tag={tag:{a['name']:a for a in value['assets']} for tag,value in releases.items()}
    archived=[]
    for case in cases:
        if (case.get('native_target_met') is not True or not case.get('coverage',{}).get('structurally_complete')
                or case.get('worker_exited') is not True or case.get('temporary_cleanup_verified') is not True):
            raise StrategyError('PREVIOUS_POLICY_IS_NOT_COMPLETE_AND_CLOSED')
        verify_remote_parts(case,list(by_tag[case['tag']].values()))
        archived.extend(dict(tag=case['tag'],**p) for p in case['parts'])
    if (sum(c['policy_file_bytes'] for c in cases)!=delivery['total_policy_file_bytes']
            or sum(c['coverage']['public_nodes'] for c in cases)!=delivery['total_public_nodes']):
        raise StrategyError('SAVED_POLICY_INVENTORY_TOTALS_CHANGED')
    checked_results(dict(full,cases=[dict(c,ordinal=c['source_ordinal']) for c in cases[1:]]),delivery['windows_cases'])
    checked_results(dict(full,cases=[dict(cases[0],ordinal=1)]),[delivery['pilot_windows_proof']])
    for item in publication['metadata_hashes']:
        asset=by_tag[item['tag']].get(item['name'])
        if (not asset or asset.get('state')!='uploaded' or asset.get('size')!=item['bytes']
                or asset.get('digest')!='sha256:'+item['sha256']):
            raise StrategyError('PREVIOUS_PUBLISHED_EVIDENCE_IS_MISSING_OR_CHANGED')
    source=by_tag[SB40_NEXT16_TAG].get(publication['source_asset'])
    if (not source or source.get('state')!='uploaded' or source['size']!=publication['source_bytes']
            or source.get('digest')!='sha256:'+publication['source_sha256']):
        raise StrategyError('THE_PREVIOUS_VERIFIED_SOURCE_ZIP_IS_NOT_DURABLE')
    value=dict(schema='software.hu-sb40-saved-checkpoint.v1',status='PASS',complete_saved_models=17,
        complete_distinct_flops=17,model_sha256=model_identity(full['_original_plan']['game']),
        prior_plan_sha256=full['plan_sha256'],prior_catalog_asset=PRIOR_CATALOG,
        profile_settings=full['profile_settings'],
        preserved_models=[{k:c[k] for k in ('board','policy_sha256','file_sha256','tag')} for c in cases],
        archived_policy_parts=archived,remote_archive_parts_verified=len(archived),
        total_saved_policy_bytes=delivery['total_policy_file_bytes'],public_nodes=delivery['total_public_nodes'],
        complete_windows_downloads_previously_passed=17,
        windows_workflow_runs=[str(publication['windows_run']),'43779044783'],
        verified_evidence=publication['metadata_hashes'],source_asset=publication['source_asset'],
        source_sha256=publication['source_sha256'],source_bytes=publication['source_bytes'],
        code_archive_previously_fully_downloaded_and_crc_verified=True,
        verification_scope='CURRENT_REMOTE_SHA256_AND_SIZE_VS_PREVIOUS_ACTUAL_COMPLETE_WINDOWS_DOWNLOADS_AND_JSON_HISTORIES',
        all_policy_bytes_redownloaded_in_this_check=False,
        cfr_checkpoint_scope='CONVERGENCE_LOGS_AND_FINAL_COMPLETE_POLICY_NOT_RESUMABLE_REGRETS_EVERY_ITERATION',
        pppoker_windows_validated=False)
    value['checkpoint_sha256']=digest(value)
    return value


def check_saved():
    full,_=load_family('sb40-next16',PRIOR_CATALOG)
    delivery=json.loads((PRIOR/'published/entrega-sb40-next16-43796410882-a1.json').read_text())
    publication=json.loads((PRIOR/'publicacao-final-verificada.json').read_text())
    releases={tag:release(tag) for tag in (SB40_TAG,SB40_NEXT16_TAG)}
    return saved_checkpoint(full,delivery,publication,releases)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--expected');args=p.parse_args(argv)
    value=check_saved()
    if args.expected and value!=json.loads(Path(args.expected).read_text()):
        raise StrategyError('THE_SAVED_PREREQUISITE_CHECKPOINT_CHANGED')
    atomic_json(args.output,value)
    print(json.dumps({k:value[k] for k in ('status','complete_saved_models','remote_archive_parts_verified','checkpoint_sha256')}))
    return 0


if __name__=='__main__':raise SystemExit(main())
