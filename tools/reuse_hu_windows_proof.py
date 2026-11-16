"""Reuse only a complete immutable Windows proof of this exact native policy."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import REPOSITORY
from strategy.batch_download import ASSET_BASE,read_json
from strategy.batch_jobs import atomic_json
from strategy.campaign_download import load_family
from strategy.state_contract import StrategyError
from finalize_hu_campaign import checked_results


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--family',required=True,choices=('btn32','sb40','sb40-next16','sb40-34','sb40-51','sb40-68','sb40-85','sb40-102'))
    p.add_argument('--ordinal',required=True,type=int);p.add_argument('--catalog-asset',required=True)
    p.add_argument('--output',required=True);args=p.parse_args(argv)
    catalog,_=load_family(args.family,args.catalog_asset,new_only=True);tag=catalog['tag']
    case=next(c for c in catalog['cases'] if c['ordinal']==args.ordinal)
    release=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}')
    assets={a['name']:a for a in release['assets'] if a['state']=='uploaded'}
    pattern=rf'windows-{args.family}-case-{args.ordinal:02d}-([0-9]+)-a[0-9]+\.json'
    options=sorted((a for a in assets.values() if re.fullmatch(pattern,a['name'])),key=lambda a:a['id'],reverse=True)
    result=dict(reused=False,ordinal=args.ordinal)
    for asset in options:
        name=asset['name'];history=name[:-5]+'-json-history.zip'
        if history not in assets:continue
        row=read_json(ASSET_BASE+tag+'/'+name)
        try:checked_results(dict(catalog,cases=[case]),[row])
        except (StrategyError,KeyError,TypeError,ValueError):continue
        result.update(reused=True,source_workflow_run=re.fullmatch(pattern,name)[1],
            proof_asset=name,history_asset=history,policy_sha256=row['policy_sha256'],
            actual_policy_download_repeated=False);break
    atomic_json(args.output,result)
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('reused='+str(result['reused']).lower()+'\n')
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
