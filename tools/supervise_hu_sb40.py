"""Supervise the existing immutable runs; retry only expired prerequisite waits."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError,URLError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import REPOSITORY
from strategy.batch_jobs import atomic_json
from strategy.campaign_download import load_campaign,load_family
from strategy.blind_war import SB40_COMPLETE34_TAG
from strategy.sb40_progression import PrerequisitePending,load_parent34
from strategy.sb40_series import load_series_parent
from strategy.state_contract import StrategyError

RUNS={
    'native34':('43799276504','9017fcbb2da924ff22853f59ad9da38b09c6e580','hu-sb40-complete34.yml','feat/hu-sb40-complete34-20261116'),
    'windows34':('43800302038','98c45e9cf8e2ae6db22d48604408fb264c4cd98b','hu-sb40-complete34-windows.yml','feat/hu-sb40-complete34-20261116'),
    'seed51':('43807544505','3a1f445636335a659cd8beadbdb6d6293c8ea16f','hu-sb40-complete51.yml','feat/hu-sb40-complete51-20261116'),
    'series':('43810403786','e5a1e5e751ca25cd19d912de9782ce53c4aa5dea','hu-sb40-to102.yml','feat/hu-sb40-to102-20261116'),
}
WAIT_JOBS={
    ('windows34','checked-catalog'):(34,'Await only the exact complete checked catalog; never call a partial batch learned','COMPLETE_CAMPAIGN_WAIT_TIMEOUT'),
    ('seed51','initialize'):(51,'Wait for all 34 saved Windows-verified models before freezing or publishing the new study','VERIFIED_34_PREREQUISITE_WAIT_TIMEOUT_NO_NEW_CFR_STARTED'),
    **{('series',f'initialize{n}'):(n,f'Wait for {n-17} complete saved Windows-verified models before allocating the next seventeen','VERIFIED_PARENT_WAIT_TIMEOUT_NO_NEW_CFR_STARTED') for n in (68,85,102)},
}
BAD={'failure','timed_out','action_required','startup_failure','stale'}


def transient_api_error(error):
    if isinstance(error,subprocess.TimeoutExpired):return True
    if isinstance(error,HTTPError):
        return error.code in (429,500,502,503,504) or (error.code==403 and error.headers.get('X-RateLimit-Remaining')=='0')
    if isinstance(error,URLError):return True
    message=str(getattr(error,'stderr','') or '').lower()
    return bool(re.search(r'http (?:429|500|502|503|504)',message) or 'rate limit exceeded' in message)


def api(path,*,method=None,raw=False):
    args=['gh','api',f'repos/{REPOSITORY}/'+path]
    if method:args+=['--method',method]
    result=subprocess.run(args,capture_output=True,check=True,text=True,timeout=60)
    return result.stdout if raw else (json.loads(result.stdout) if result.stdout.strip() else None)


def read_run(key):
    run_id,sha,workflow,branch=RUNS[key];run=api('actions/runs/'+run_id)
    if (str(run.get('id'))!=run_id or run.get('head_sha')!=sha or run.get('head_branch')!=branch
            or run.get('path')!='.github/workflows/'+workflow):
        raise StrategyError('SUPERVISOR_REFUSES_UNEXPECTED_RUN_OR_SOURCE:'+key)
    return run


def read_jobs(run):
    rows=[];page=1
    while True:
        value=api(f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100&page={page}")
        rows.extend(value['jobs'])
        if len(value['jobs'])<100:return rows
        page+=1
        if page>20:raise StrategyError('SUPERVISOR_JOB_METADATA_LIMIT')


def expired_wait(key,job,log):
    definition=WAIT_JOBS.get((key,job.get('name')))
    if definition is None:return False
    if job.get('conclusion') not in ('failure','timed_out'):return False
    _,step_name,reason=definition
    steps=[s for s in job.get('steps',[]) if s.get('name')==step_name]
    if len(steps)!=1 or steps[0].get('conclusion') not in ('failure','timed_out','cancelled'):return False
    return reason in log or job.get('conclusion')=='timed_out'


def prerequisite_ready(target):
    try:
        if target==34:load_campaign(SB40_COMPLETE34_TAG,'batch-catalog-43799276504.json')
        elif target==51:load_parent34()
        else:load_series_parent(target,parent_run=RUNS['series'][0] if target>68 else None)
    except PrerequisitePending:return False
    except HTTPError as error:
        if error.code==404:return False
        raise
    return True


def choose_retry(key,run,jobs,logs):
    """Keep partial/solver/test failures visible; never start them as generic retries."""
    if run.get('status')!='completed' or run.get('conclusion')=='success':return None
    if run.get('conclusion')=='cancelled':raise StrategyError('EXPLICIT_CANCELLATION_PRESERVED:'+key)
    failures=[j for j in jobs if j.get('conclusion') in BAD]
    if len(failures)!=1:raise StrategyError('NON_WAIT_FAILURE_REQUIRES_DIAGNOSIS:'+key)
    job=failures[0]
    if not expired_wait(key,job,logs.get(job['id'],'')):
        raise StrategyError('NON_WAIT_FAILURE_REQUIRES_DIAGNOSIS:'+key+':'+job['name'])
    target=WAIT_JOBS[(key,job['name'])][0]
    if not prerequisite_ready(target):return None
    return dict(run_key=key,run_id=str(run['id']),run_attempt=run['run_attempt'],job_id=job['id'],
        job_name=job['name'],target=target,reason='EXPIRED_WAIT_AND_PREREQUISITE_NOW_FULLY_VERIFIED')


def verify_final():
    """No count reaches 102 until complete policies and the publication receipt agree."""
    from strategy.batch_download import read_json
    from strategy.sb40_series import family_tag
    from strategy.sb40_progression import read_asset
    from tools.finalize_hu_campaign import checked_results
    from tools.finalize_hu_sb40_complete51 import checked_root_review
    tag=family_tag(102);run_id=RUNS['series'][0]
    remote=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}')
    assets={a['name']:a for a in remote['assets'] if a['state']=='uploaded'}
    candidates=[a for a in assets.values() if re.fullmatch(r'publicacao-final-verificada-sb40-102-'+run_id+r'-a[0-9]+\.json',a['name'])]
    if not candidates:raise StrategyError('COMPLETE_102_PUBLICATION_RECEIPT_REQUIRED')
    asset=max(candidates,key=lambda a:a['id']);proof=read_asset(asset,tag)
    stamp=asset['name'][len('publicacao-final-verificada-sb40-102-'):-5]
    delivery=read_asset(assets['entrega-sb40-102-'+stamp+'.json'],tag)
    full,catalog_name=load_family('sb40-102',proof['native_catalog_asset'])
    new=dict(full,cases=[dict(c,ordinal=c['source_ordinal']) for c in full['cases'][-17:]])
    checked_results(new,delivery['windows_cases'])
    for row in delivery['windows_cases']:checked_root_review(row)
    if (full['cases']!=delivery.get('inventory') or len(full['cases'])!=102
            or delivery.get('status')!='PASS' or delivery.get('complete_distinct_flop_models')!=102
            or delivery.get('all_new_workers_exited') is not True
            or delivery.get('all_new_native_temporaries_removed') is not True
            or proof.get('schema')!='software.hu-sb40-series-publication-check.v1'
            or proof.get('status')!='PASS' or proof.get('complete_models')!=102
            or proof.get('zip_crc_all_entries_valid') is not True
            or proof.get('new_json_street_queries')!=51 or proof.get('new_exact_suit_street_queries')!=51
            or proof.get('new_confirmed_json_histories')!=17 or proof.get('complete_prior_models_preserved')!=85
            or str(proof.get('windows_run'))!=run_id or proof.get('pppoker_windows_validated') is not False):
        raise StrategyError('ALL_102_SAVED_WINDOWS_VERIFIED_POLICIES_REQUIRED')
    histories=proof.get('published_histories_checked',[])
    if (len(histories)!=17 or any(h.get('status')!='PASS' or h.get('json_streets')!=3 for h in histories)
            or {h['policy_sha256'] for h in histories}!={c['policy_sha256'] for c in new['cases']}
            or len(proof.get('metadata_hashes',[]))!=5):
        raise StrategyError('ALL_102_PUBLISHED_HISTORY_AND_REPORT_RECEIPTS_REQUIRED')
    from strategy.sb40_progression import check_asset
    for item in proof['metadata_hashes']:check_asset(assets.get(item['name']),item)
    check_asset(assets.get(proof['source_asset']),dict(name=proof['source_asset'],bytes=proof['source_bytes'],sha256=proof['source_sha256']))
    return dict(status='PASS',complete_distinct_models=102,release=tag,publication_asset=asset['name'],
        publication_sha256=asset['digest'].removeprefix('sha256:'),catalog_asset=catalog_name,
        full_policy_files_previously_read_on_windows=102,all_policy_bytes_redownloaded_by_supervisor=False,
        input_devices_used=False,pppoker_windows_validated=False)


def once(state,*,apply=False):
    if apply and (os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY):
        raise StrategyError('AUTOMATIC_RETRY_REQUIRES_THE_OWNED_GITHUB_ACTIONS_WORKFLOW')
    result=dict(schema='software.hu-sb40-supervisor.v1',status='RUNNING',done=False,
        observed_at=datetime.now(timezone.utc).isoformat(),runs={},retry_actions=[],
        retries_requested=state.get('retries_requested',[]),pppoker_windows_validated=False)
    for key in RUNS:
        run=read_run(key);jobs=read_jobs(run)
        result['runs'][key]=dict(run_id=str(run['id']),attempt=run['run_attempt'],status=run['status'],conclusion=run.get('conclusion'),
            passed_jobs=sum(j.get('conclusion')=='success' for j in jobs),
            running_jobs=[j['name'] for j in jobs if j['status']=='in_progress'],
            failed_jobs=[j['name'] for j in jobs if j.get('conclusion') in BAD])
        if run['status']=='completed' and run.get('conclusion')!='success':
            failures=[j for j in jobs if j.get('conclusion') in BAD];logs={}
            for job in failures:
                if (key,job.get('name')) in WAIT_JOBS:
                    logs[job['id']]=api(f"actions/jobs/{job['id']}/logs",raw=True)
            action=choose_retry(key,run,jobs,logs)
            if action:
                stamp=f"{action['run_id']}:a{action['run_attempt']}:{action['job_id']}"
                if stamp not in result['retries_requested']:
                    if apply:
                        api(f"actions/jobs/{action['job_id']}/rerun",method='POST')
                        result['retries_requested'].append(stamp)
                    result['retry_actions'].append(dict(action,applied=apply))
        if key=='series' and run['status']=='completed' and run.get('conclusion')=='success':
            result.update(status='COMPLETE_102',done=True,final_verification=verify_final())
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--checkpoint');p.add_argument('--seconds',type=int,default=19800)
    p.add_argument('--poll-seconds',type=int,default=120);p.add_argument('--once',action='store_true')
    p.add_argument('--apply',action='store_true');args=p.parse_args(argv)
    if args.seconds<1 or not 30<=args.poll_seconds<=600:p.error('Positive duration and 30..600 second polling required')
    out=Path(args.output)
    if out.exists():raise StrategyError('SUPERVISOR_OUTPUT_MUST_BE_NEW')
    state=json.loads(Path(args.checkpoint).read_text()) if args.checkpoint else {}
    out.mkdir(parents=True);started=time.monotonic()
    while True:
        try:state=once(state,apply=args.apply)
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,HTTPError,URLError) as error:
            if not transient_api_error(error):raise
            state=dict(state,status='WAITING_FOR_GITHUB_API',done=False,
                observed_at=datetime.now(timezone.utc).isoformat(),error_type=type(error).__name__,
                pppoker_windows_validated=False)
        atomic_json(out/'state.json',state)
        with (out/'events.jsonl').open('a') as target:target.write(json.dumps(state)+'\n')
        print(json.dumps(state),flush=True)
        if args.once or state['done'] or time.monotonic()-started>=args.seconds:break
        deadline=min(started+args.seconds,time.monotonic()+args.poll_seconds)
        while time.monotonic()<deadline:time.sleep(min(30,max(0,deadline-time.monotonic())))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as target:target.write('done='+str(state['done']).lower()+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
