"""Wait for the verified 34, then freeze and optionally publish the next study."""
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
from strategy.blind_war import SB40_COMPLETE51_TAG
from strategy.campaign import checked_campaign_plan
from strategy.sb40_progression import (PARENT_WINDOWS,PrerequisitePending,load_parent34,
    make_plan51,read_intent,read_asset,validate_derived_plan51)
from strategy.state_contract import StrategyError


def wait_for_parent(seconds):
    started=time.monotonic();last_status_check=-120.
    while True:
        try:return load_parent34()
        except PrerequisitePending as error:reason=str(error)
        except HTTPError as error:
            if error.code not in (404,429,500,502,503,504):raise
            reason='PARENT_METADATA_NOT_AVAILABLE:'+str(error.code)
        except URLError:reason='PARENT_METADATA_NETWORK_RETRY'
        elapsed=time.monotonic()-started
        if elapsed>=seconds:raise StrategyError('VERIFIED_34_PREREQUISITE_WAIT_TIMEOUT_NO_NEW_CFR_STARTED')
        if elapsed-last_status_check>=120:
            state=read_json(f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{PARENT_WINDOWS}')
            if state.get('status')=='completed' and state.get('conclusion')!='success':
                raise StrategyError('PARENT_DELIVERY_FAILED_NO_NEW_CFR_STARTED:'+str(state.get('conclusion')))
            last_status_check=elapsed
        print(json.dumps(dict(status='WAITING_FOR_SAVED_AND_VALIDATED_34',reason=reason,elapsed_seconds=round(elapsed),new_cfr_started=False)),flush=True)
        time.sleep(min(30,max(0,seconds-elapsed)))


def initialize(output,wait_seconds,publish=False):
    folder=Path(output)
    if folder.exists():raise StrategyError('NEW_CONDITIONAL_INPUT_FOLDER_REQUIRED')
    intent=read_intent()
    try:remote=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{SB40_COMPLETE51_TAG}')
    except HTTPError as error:
        if error.code!=404:raise
        remote=None
    existing=None
    if remote:
        existing=next((a for a in remote['assets'] if a['state']=='uploaded' and a['name']=='sb40-complete51-plan.json'),None)
        if existing is None:raise StrategyError('EXISTING_51_RELEASE_WITHOUT_FROZEN_PLAN_PRESERVED')
        plan=read_asset(existing,SB40_COMPLETE51_TAG);previous,checkpoint=validate_derived_plan51(plan)
    else:
        previous,checkpoint=wait_for_parent(wait_seconds)
        plan=make_plan51(previous,checkpoint,intent)
    folder.mkdir(parents=True)
    for name,value in (('sb40-complete51-plan.json',plan),('checkpoint-primeiros34.json',checkpoint),('sb40-51-intent.json',intent)):
        atomic_json(folder/name,value)
    if publish:
        from tools.hu_batch16 import main as batch
        batch(['init','--plan',str(folder/'sb40-complete51-plan.json')])
        assets=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{SB40_COMPLETE51_TAG}')['assets']
        for name in ('checkpoint-primeiros34.json','sb40-51-intent.json'):
            path=folder/name;old=next((a for a in assets if a['name']==name),None)
            if old:
                if old.get('digest')!='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest():
                    raise StrategyError('EXISTING_51_GUARD_ARTIFACT_CHANGED_PRESERVED')
            else:subprocess.run(['gh','release','upload',SB40_COMPLETE51_TAG,'--repo',REPOSITORY,str(path)],check=True)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as target:target.write('plan_sha256='+plan['plan_sha256']+'\n')
    print(json.dumps(dict(status='PREREQUISITE_PASS_PLAN_FROZEN',previous_complete_models=34,new_models=17,
        plan_sha256=plan['plan_sha256'],checkpoint_sha256=checkpoint['checkpoint_sha256'],new_cfr_started=False)),flush=True)
    return 0


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cmd',choices=('init','verify'))
    p.add_argument('--output');p.add_argument('--wait-seconds',type=int,default=19800);p.add_argument('--publish',action='store_true')
    p.add_argument('--plan');p.add_argument('--checkpoint');p.add_argument('--expected-plan-sha');args=p.parse_args(argv)
    if args.wait_seconds<1:p.error('Positive prerequisite timeout required')
    if args.cmd=='init':
        if not args.output:p.error('--output required')
        return initialize(args.output,args.wait_seconds,args.publish)
    if not args.plan or not args.checkpoint:p.error('--plan and --checkpoint required')
    plan=checked_campaign_plan(args.plan);_,checkpoint=validate_derived_plan51(plan,args.expected_plan_sha)
    if checkpoint!=json.loads(Path(args.checkpoint).read_text()):raise StrategyError('CHECKED_RUNTIME_INPUTS_DIFFER_FROM_SAVED_PARENT')
    print(json.dumps(dict(status='PASS',plan_sha256=plan['plan_sha256'],previous_complete_models=34)));return 0


if __name__=='__main__':raise SystemExit(main())
