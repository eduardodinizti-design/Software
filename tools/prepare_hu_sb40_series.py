"""Freeze the next seventeen only after the preceding saved Windows delivery."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError,URLError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import REPOSITORY
from strategy.batch_download import read_json
from strategy.batch_jobs import atomic_json
from strategy.campaign import checked_campaign_plan
from strategy.sb40_progression import PrerequisitePending,read_asset
from strategy.sb40_series import (family_tag,read_series_intent,parent_run_id,
    load_series_parent,make_series_plan,validate_series_plan)
from strategy.state_contract import StrategyError


def wait_for_parent(target,seconds,parent_run=None):
    run_id=parent_run_id(target,parent_run=parent_run)
    started=time.monotonic();last_status_check=-120.
    while True:
        try:return load_series_parent(target,parent_run=run_id)
        except PrerequisitePending as error:reason=str(error)
        except HTTPError as error:
            if error.code not in (404,429,500,502,503,504):raise
            reason='PARENT_METADATA_NOT_AVAILABLE:'+str(error.code)
        except URLError:reason='PARENT_METADATA_NETWORK_RETRY'
        elapsed=time.monotonic()-started
        if elapsed>=seconds:raise StrategyError('VERIFIED_PARENT_WAIT_TIMEOUT_NO_NEW_CFR_STARTED')
        if elapsed-last_status_check>=120:
            state=read_json(f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{run_id}')
            if state.get('status')=='completed' and state.get('conclusion')!='success':
                raise StrategyError('PARENT_DELIVERY_FAILED_NO_NEW_CFR_STARTED:'+str(state.get('conclusion')))
            last_status_check=elapsed
        print(json.dumps(dict(status='WAITING_FOR_SAVED_AND_VALIDATED_PARENT',required_models=target-17,
            target_models=target,reason=reason,elapsed_seconds=round(elapsed),new_cfr_started=False)),flush=True)
        time.sleep(min(30,max(0,seconds-elapsed)))


def initialize(target,output,wait_seconds,publish=False,parent_run=None):
    tag=family_tag(target);folder=Path(output)
    if folder.exists():raise StrategyError('NEW_CONDITIONAL_INPUT_FOLDER_REQUIRED')
    intent=read_series_intent(target);parent_run_id(target,parent_run=parent_run)
    try:remote=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}')
    except HTTPError as error:
        if error.code!=404:raise
        remote=None
    name=f'sb40-complete{target}-plan.json'
    if remote:
        existing=next((a for a in remote['assets'] if a['state']=='uploaded' and a['name']==name),None)
        if existing is None:raise StrategyError('EXISTING_SERIES_RELEASE_WITHOUT_FROZEN_PLAN_PRESERVED')
        plan=read_asset(existing,tag);_,checkpoint=validate_series_plan(plan)
        if checkpoint['windows_workflow_run']!=parent_run_id(target,parent_run=parent_run):
            raise StrategyError('FROZEN_SERIES_PARENT_CONTROLLER_CHANGED_PRESERVED')
    else:
        previous,checkpoint=wait_for_parent(target,wait_seconds,parent_run)
        plan=make_series_plan(target,previous,checkpoint,intent)
    folder.mkdir(parents=True)
    guards=((f'checkpoint-primeiros{target-17}.json',checkpoint),(f'sb40-{target}-intent.json',intent))
    atomic_json(folder/name,plan)
    for guard,value in guards:atomic_json(folder/guard,value)
    if publish:
        from tools.hu_batch16 import main as batch
        batch(['init','--plan',str(folder/name)])
        assets=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}')['assets']
        for guard,_ in guards:
            path=folder/guard;old=next((a for a in assets if a['name']==guard),None)
            if old:
                if old.get('digest')!='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest():
                    raise StrategyError('EXISTING_SERIES_GUARD_ARTIFACT_CHANGED_PRESERVED')
            else:subprocess.run(['gh','release','upload',tag,'--repo',REPOSITORY,str(path)],check=True)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as stream:stream.write('plan_sha256='+plan['plan_sha256']+'\n')
    print(json.dumps(dict(status='PREREQUISITE_PASS_PLAN_FROZEN',previous_complete_models=target-17,
        target_models=target,new_models=17,plan_sha256=plan['plan_sha256'],
        checkpoint_sha256=checkpoint['checkpoint_sha256'],new_cfr_started=False)),flush=True)
    return 0


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cmd',choices=('init','verify'))
    p.add_argument('--target',required=True,type=int,choices=(68,85,102));p.add_argument('--parent-run')
    p.add_argument('--output');p.add_argument('--wait-seconds',type=int,default=19800);p.add_argument('--publish',action='store_true')
    p.add_argument('--plan');p.add_argument('--checkpoint');p.add_argument('--expected-plan-sha');args=p.parse_args(argv)
    if args.wait_seconds<1:p.error('Positive prerequisite timeout required')
    if args.cmd=='init':
        if not args.output:p.error('--output required')
        return initialize(args.target,args.output,args.wait_seconds,args.publish,args.parent_run)
    if not args.plan or not args.checkpoint:p.error('--plan and --checkpoint required')
    plan=checked_campaign_plan(args.plan)
    if plan['target_total_models']!=args.target:p.error('Plan belongs to another target')
    _,checkpoint=validate_series_plan(plan,args.expected_plan_sha)
    if checkpoint!=json.loads(Path(args.checkpoint).read_text()):raise StrategyError('CHECKED_INPUTS_DIFFER_FROM_SAVED_PARENT')
    print(json.dumps(dict(status='PASS',plan_sha256=plan['plan_sha256'],previous_complete_models=args.target-17)));return 0


if __name__=='__main__':raise SystemExit(main())
