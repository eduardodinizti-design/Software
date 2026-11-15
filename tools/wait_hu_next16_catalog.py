"""Wait for one immutable complete catalog, without occupying a Windows worker."""
import argparse
from pathlib import Path
import sys
import time
from urllib.error import HTTPError,URLError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import BATCH_TAG
from strategy.batch_download import ASSET_BASE,load_catalog,read_json,safe_name
from strategy.batch_jobs import atomic_json
from strategy.state_contract import StrategyError


def wait_catalog(asset,seconds):
    if not safe_name(asset):raise StrategyError('SAFE_CATALOG_ASSET_NAME_REQUIRED')
    started=time.monotonic()
    while time.monotonic()-started<seconds:
        try:value=read_json(ASSET_BASE+BATCH_TAG+'/'+asset)
        except HTTPError as exc:
            if exc.code not in (404,429,500,502,503,504):raise
        except URLError:pass
        else:
            if (value.get('schema')!='software.hu-batch-catalog.v1' or value.get('status')!='COMPLETE'
                    or value.get('native_target_met_flops')!=16):
                raise StrategyError('IMMUTABLE_CATALOG_IS_PARTIAL_INSPECT_NATIVE_FAILURES_AND_USE_A_NEW_COMPLETE_CATALOG')
            catalog,name=load_catalog(asset)
            return dict(status='PASS',catalog_asset=name,plan_sha256=catalog['plan_sha256'],
                published_new_flops=catalog['published_new_flops'],native_target_met_flops=catalog['native_target_met_flops'])
        elapsed=time.monotonic()-started
        print(f'Awaiting complete immutable catalog: {asset}; elapsed={elapsed:.0f}s',flush=True)
        time.sleep(max(0,min(30,seconds-elapsed)))
    raise StrategyError('COMPLETE_CATALOG_WAIT_TIMEOUT')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--catalog-asset',required=True)
    p.add_argument('--seconds',type=int,default=10800);p.add_argument('--output',required=True);args=p.parse_args(argv)
    if args.seconds<1:p.error('Positive timeout required')
    result=wait_catalog(args.catalog_asset,args.seconds);atomic_json(args.output,result)
    print('All sixteen native policies are published and ready for Windows transfer.');return 0


if __name__=='__main__':raise SystemExit(main())
