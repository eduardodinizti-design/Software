"""Wait for both the complete reference ZIP and its manifest to be uploaded."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.reference_download import REPOSITORY,TAG


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=3000)
    args=p.parse_args(argv)
    if not 1<=args.seconds<=7200:p.error('Use 1..7200 seconds')
    deadline=time.monotonic()+args.seconds
    required={'btn-bb-As7d2c-nvt-reference.zip','download-manifest.json'}
    while time.monotonic()<deadline:
        result=subprocess.run(['gh','api',f'repos/{REPOSITORY}/releases/tags/{TAG}'],
            capture_output=True,text=True,timeout=30)
        if result.returncode==0:
            assets=json.loads(result.stdout)['assets']
            ready={a['name'] for a in assets if a['state']=='uploaded' and a['size']>0}
            if required.issubset(ready):
                print('Complete reference ZIP and manifest are uploaded.',flush=True);return 0
        print('Waiting for the complete reference release; existing calculations are preserved.',flush=True)
        time.sleep(30)
    raise SystemExit('Reference publication is not ready; no bank was guessed or substituted.')


if __name__=='__main__':raise SystemExit(main())
