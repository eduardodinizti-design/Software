"""Wait for the original case; never duplicate its active solve or recovery data."""
import argparse
import json
import subprocess
import time

from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import REPOSITORY
from strategy.state_contract import StrategyError


def api(path):
    return json.loads(subprocess.check_output(['gh','api',f'repos/{REPOSITORY}/'+path],text=True,timeout=45))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ordinal',type=int,required=True)
    p.add_argument('--run',required=True);p.add_argument('--sha',required=True);p.add_argument('--all',action='store_true');args=p.parse_args()
    value=api('actions/runs/'+args.run)
    if value['head_sha']!=args.sha:raise StrategyError('ORIGINAL_NATIVE_SOURCE_COMMIT_CHANGED')
    started=time.monotonic();label=f'Complete SB40 new flop {args.ordinal} of sixteen'
    while time.monotonic()-started<21000:
        if args.all:
            value=api('actions/runs/'+args.run)
            if value['status']=='completed':return
        else:
            jobs=api('actions/runs/'+args.run+'/jobs?per_page=100')['jobs']
            matches=[j for j in jobs if j['name']==label]
            if len(matches)!=1:raise StrategyError('ONE_EXACT_ORIGINAL_NATIVE_CASE_REQUIRED')
            job=matches[0]
            if job['status']=='completed':
                if job['conclusion']!='success':
                    artifacts=api('actions/runs/'+args.run+'/artifacts?per_page=100')['artifacts']
                    prefix='hu-sb40-next16-recovery-'+str(args.ordinal)+'-a'
                    if any(a['name'].startswith(prefix) for a in artifacts):
                        raise StrategyError('RECOVERY_DATA_EXISTS_IMPORT_IT_INSTEAD_OF_REPEATING_CFR')
                print(json.dumps(dict(original_case=args.ordinal,original_conclusion=job['conclusion'])));return
        print(json.dumps(dict(waiting_for_original_case='ALL' if args.all else args.ordinal,elapsed_seconds=round(time.monotonic()-started))),flush=True)
        time.sleep(30)
    raise StrategyError('ORIGINAL_CASE_WAIT_TIMEOUT')


if __name__=='__main__':main()
