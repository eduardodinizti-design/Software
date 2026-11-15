"""Wait for each family's immutable data receipts, independently of other jobs."""
import argparse
import json
import re
import subprocess
import time

REPO='eduardodinizti-design/Software'


def api(path):
    result=subprocess.run(['gh','api','repos/'+REPO+'/'+path],capture_output=True,text=True,check=True,timeout=45)
    return json.loads(result.stdout)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True)
    p.add_argument('--family',required=True,choices=('btn32','sb40'));p.add_argument('--run-id',required=True)
    p.add_argument('--count',required=True,type=int);p.add_argument('--seconds',type=int,default=17000)
    args=p.parse_args(argv);started=time.monotonic()
    while time.monotonic()-started<args.seconds:
        release=api('releases/tags/'+args.tag);ready=set()
        for asset in release['assets']:
            match=re.fullmatch(r'windows-'+args.family+r'-case-([0-9]+)-'+re.escape(args.run_id)+r'-a[0-9]+\.json',asset['name'])
            if match and asset['state']=='uploaded':ready.add(int(match[1]))
        if ready==set(range(1,args.count+1)):
            print('All requested actual Windows receipts published:',len(ready));return 0
        run=api('actions/runs/'+args.run_id)
        if run['status']=='completed':raise SystemExit('WINDOWS_RUN_FINISHED_WITH_MISSING_RECEIPTS: '+str(sorted(set(range(1,args.count+1))-ready)))
        print(f'{args.family}: {len(ready)}/{args.count} Windows receipts; elapsed={time.monotonic()-started:.0f}s',flush=True)
        time.sleep(30)
    raise SystemExit('WINDOWS_RECEIPTS_WAIT_TIMEOUT')


if __name__=='__main__':raise SystemExit(main())
