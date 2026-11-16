"""Check and retain published evidence without downloading multi-GB policies."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import REPOSITORY
from strategy.batch_download import ASSET_BASE,fetch,safe_name
from strategy.batch_jobs import atomic_json
from strategy.blind_war import SB40_TAG
from strategy.campaign import CLOSE32_TAG
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash


def release(tag):
    result=subprocess.run(['gh','api',f'repos/{REPOSITORY}/releases/tags/{tag}'],
        check=True,capture_output=True,text=True,timeout=45)
    return json.loads(result.stdout)


def receive(asset,tag,target):
    if not safe_name(asset['name']):raise StrategyError('EVIDENCE_ASSET_NAME_UNSAFE')
    if not asset.get('digest','').startswith('sha256:'):raise StrategyError('REMOTE_EVIDENCE_SHA256_REQUIRED')
    sha=asset['digest'][7:]
    if target.exists():
        if target.stat().st_size!=asset['size'] or file_hash(target)!=sha:raise StrategyError('EXISTING_EVIDENCE_DIFFERS_PRESERVED')
    else:
        with fetch(ASSET_BASE+tag+'/'+asset['name']) as source:raw=source.read(32*1024**2+1)
        if len(raw)!=asset['size'] or hashlib.sha256(raw).hexdigest()!=sha:raise StrategyError('PUBLISHED_EVIDENCE_BYTES_CHANGED')
        with target.open('xb') as out:out.write(raw)
    return dict(tag=tag,name=asset['name'],bytes=asset['size'],sha256=sha)


def check_history(path,proof):
    with zipfile.ZipFile(path) as archive:
        def read(name):
            matches=[p for p in archive.namelist() if p.replace('\\','/').split('/')[-1]==name]
            if len(matches)!=1:raise StrategyError('ONE_PUBLISHED_HISTORY_FILE_REQUIRED:'+name)
            return json.loads(archive.read(matches[0]))
        decisions=read('decisions.json');hand=read('hand.json');result=read('result.json')
        if (not hand.get('chain_valid') or not result.get('journal_chain_valid')
                or result['policy_sha256']!=proof['policy_sha256'] or result['status']!='PASS'
                or result!=proof['confirmed_hand']
                or {d['street'] for d in decisions}!={'FLOP','TURN','RIVER'}):
            raise StrategyError('PUBLISHED_CONFIRMED_HISTORY_DIFFERS_FROM_WINDOWS_PROOF')
        for street,probe in proof['source_lookup']['probes'].items():
            request=read('request-'+street+'.json');response=read('response-'+street+'.json')
            if (response['policy_sha256']!=proof['policy_sha256'] or response['request']!=request
                    or response['decision']['candidates']!=probe['candidates']):
                raise StrategyError('PUBLISHED_JSON_ACTIONS_FREQUENCIES_OR_SIZES_CHANGED')
        return dict(status='PASS',policy_sha256=proof['policy_sha256'],event_counts=result['event_counts'],
            declared_hero_actions_by_street=result['declared_hero_actions_by_street'],json_streets=3,
            journal_chain_reported_valid=True,pppoker_windows_validated=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--delivery-run',required=True);p.add_argument('--windows-run',required=True)
    p.add_argument('--sb-delivery-run');p.add_argument('--sb-windows-run');args=p.parse_args(argv)
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True);evidence=[];families={}
    for family,tag,count in (('btn32',CLOSE32_TAG,15),('sb40',SB40_TAG,1)):
        delivery_run=(args.sb_delivery_run or args.delivery_run) if family=='sb40' else args.delivery_run
        windows_run=(args.sb_windows_run or args.windows_run) if family=='sb40' else args.windows_run
        remote=release(tag);by_name={a['name']:a for a in remote['assets']};records=[]
        for asset in remote['assets']:
            if (asset['state']=='uploaded' and asset['size']<=32*1024**2
                    and (asset['name'].endswith(('.json','.txt')) or asset['name'].endswith('-json-history.zip'))):
                records.append(receive(asset,tag,output/asset['name']))
        evidence.extend(records)
        matches=[a for a in remote['assets'] if re.fullmatch(r'entrega-'+family+'-'+delivery_run+r'-a[0-9]+\.json',a['name'])]
        if not matches:raise StrategyError('FINAL_DELIVERY_NOT_PUBLISHED:'+family)
        delivery=json.loads((output/max(matches,key=lambda a:a['id'])['name']).read_text())
        if (delivery['status']!='PASS' or delivery['windows_new_policy_pass']!=count
                or delivery['complete_distinct_flop_models']!=(32 if family=='btn32' else 1)):
            raise StrategyError('FINAL_DELIVERY_NOT_COMPLETE')
        histories=[]
        for row in delivery['windows_cases']:
            pattern=rf'windows-{family}-case-{row["ordinal"]:02d}-{windows_run}-a[0-9]+-json-history\.zip'
            options=[a for a in remote['assets'] if re.fullmatch(pattern,a['name'])]
            if not options:raise StrategyError('PUBLISHED_JSON_HISTORY_MISSING')
            histories.append(check_history(output/max(options,key=lambda a:a['id'])['name'],row))
        source_options=[a for a in remote['assets'] if a['name'].startswith('source-manifest-'+family+'-'+delivery_run)]
        source_name=max(source_options,key=lambda a:a['id'])['name']
        source=json.loads((output/source_name).read_text());zip_asset=by_name.get(source['asset'])
        if (zip_asset is None or zip_asset['size']!=source['bytes'] or zip_asset.get('digest')!='sha256:'+source['sha256']):
            raise StrategyError('SOURCE_ZIP_REMOTE_DIGEST_DIFFERS_FROM_MANIFEST')
        families[family]=dict(status='PASS',tag=tag,complete_models=delivery['complete_distinct_flop_models'],
            new_windows_models=count,published_json_histories=histories,source_zip_remote_digest_verified=True,
            source_zip_locally_downloaded=False,source=source)
    atomic_json(output/'publication-proof.json',dict(schema='software.hu-campaign-publication-proof.v1',status='PASS',
        metadata_files_verified=len(evidence),evidence=evidence,families=families,full_policy_data_downloaded_here=False,
        scope='PUBLIC_EVIDENCE_HASHES_AND_JSON_HISTORY_CONTENT; actual policy downloads were validated on Windows',
        pppoker_windows_validated=False))
    print(json.dumps(dict(status='PASS',evidence_files=len(evidence),families={k:v['complete_models'] for k,v in families.items()})));return 0


if __name__=='__main__':raise SystemExit(main())
