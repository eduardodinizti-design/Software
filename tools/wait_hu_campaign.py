"""Await a run-specific catalog, then verify its pinned plan and remote hashes."""
import argparse
from pathlib import Path
import sys
import time
from urllib.error import HTTPError,URLError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_download import ASSET_BASE,read_json,safe_name
from strategy.batch_jobs import atomic_json
from strategy.campaign_download import load_campaign
from strategy.state_contract import StrategyError


def wait_catalog(tag,asset,seconds):
    if not safe_name(asset):raise StrategyError('SAFE_CATALOG_ASSET_NAME_REQUIRED')
    started=time.monotonic()
    while time.monotonic()-started<seconds:
        try:value=read_json(ASSET_BASE+tag+'/'+asset)
        except HTTPError as exc:
            if exc.code not in (404,429,500,502,503,504):raise
        except URLError:pass
        else:
            if value.get('status')!='COMPLETE':raise StrategyError('IMMUTABLE_CAMPAIGN_CATALOG_IS_PARTIAL_INSPECT_FAILURES')
            catalog,name=load_campaign(tag,asset)
            return dict(status='PASS',tag=tag,catalog_asset=name,plan_sha256=catalog['plan_sha256'],
                complete_native_models=len(catalog['cases']))
        elapsed=time.monotonic()-started
        print(f'Awaiting {tag}/{asset}; elapsed={elapsed:.0f}s',flush=True)
        time.sleep(max(0,min(30,seconds-elapsed)))
    raise StrategyError('COMPLETE_CAMPAIGN_WAIT_TIMEOUT')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True)
    p.add_argument('--catalog-asset',required=True);p.add_argument('--output',required=True)
    p.add_argument('--seconds',type=int,default=14400);args=p.parse_args(argv)
    if args.seconds<1:p.error('Positive timeout required')
    atomic_json(args.output,wait_catalog(args.tag,args.catalog_asset,args.seconds));return 0


if __name__=='__main__':raise SystemExit(main())
