"""Install immutable published NVT policies with bounded RAM and checked hashes.

The archive is data only. This module never uses the mouse or starts a solver.
"""
import argparse
import copy
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import uuid
import urllib.request
from urllib.parse import urlsplit
import zipfile

from strategy.batch_archive import BATCH_TAG,PILOT_TAG,REPOSITORY,make_catalog
from strategy.batch_jobs import atomic_json,case_id
from strategy.native_stream import query_probe
from strategy.policy_library import PolicyLibrary
from strategy.reference_download import fetch,safe_extract
from strategy.state_contract import BettingState,GameContext,StrategyError,digest

PLAN_SHA256='525df4dc2ac803e28f18adcef79ceb943df2264ffbe154397e21cd822fca7903'
ASSET_BASE=f'https://github.com/{REPOSITORY}/releases/download/'


_JSON_SNAPSHOT=ContextVar('hu_metadata_snapshot',default=None)


@contextmanager
def metadata_snapshot():
    """One bounded ancestry read; no cache survives the enclosing operation."""
    if _JSON_SNAPSHOT.get() is not None:
        yield
        return
    token=_JSON_SNAPSHOT.set(dict(values={},bytes=0))
    try:yield
    finally:_JSON_SNAPSHOT.reset(token)


def read_json(url,limit=4*1024**2):
    cache=_JSON_SNAPSHOT.get();key=(url,limit)
    if cache is not None and key in cache['values']:return copy.deepcopy(cache['values'][key])
    value=_read_json_uncached(url,limit)
    if cache is not None and len(cache['values'])<128:
        size=len(json.dumps(value,separators=(',',':')).encode())
        if cache['bytes']+size<=64*1024**2:
            cache['values'][key]=copy.deepcopy(value);cache['bytes']+=size
    return value


def _read_json_uncached(url,limit=4*1024**2):
    parsed=urlsplit(url);token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token and parsed.scheme=='https' and parsed.netloc=='api.github.com':
        request=urllib.request.Request(url,headers={'User-Agent':'Software-HU-metadata/1',
            'Accept':'application/vnd.github+json','Authorization':'Bearer '+token})
        class MetadataRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,req,fp,code,msg,headers,newurl):
                target=urlsplit(newurl)
                if target.scheme!='https' or target.netloc!='api.github.com':
                    raise StrategyError('AUTHENTICATED_METADATA_REDIRECT_OUTSIDE_API_REFUSED')
                return super().redirect_request(req,fp,code,msg,headers,newurl)
        response=urllib.request.build_opener(MetadataRedirect()).open(request,timeout=60)
    else:response=fetch(url)
    with response:raw=response.read(limit+1)
    if len(raw)>limit:raise StrategyError('BATCH_METADATA_TOO_LARGE')
    return json.loads(raw)


def safe_name(value):
    return isinstance(value,str) and re.fullmatch(r'[a-zA-Z0-9_.-]+',value) and '..' not in value


def valid_sha(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value)


def check_bundle(value):
    if (type(value.get('archive_bytes')) is not int or value['archive_bytes']<=0
            or not valid_sha(value.get('archive_sha256')) or not value.get('parts')):
        raise StrategyError('BATCH_ARCHIVE_MANIFEST_INVALID')
    seen=set()
    for part in value['parts']:
        if (not safe_name(part.get('name')) or part['name'] in seen or not valid_sha(part.get('sha256'))
                or type(part.get('bytes')) is not int or part['bytes']<=0):
            raise StrategyError('BATCH_ARCHIVE_PART_MANIFEST_INVALID')
        seen.add(part['name'])
    if sum(p['bytes'] for p in value['parts'])!=value['archive_bytes']:
        raise StrategyError('BATCH_ARCHIVE_PART_SIZES_DISAGREE')
    return value


def load_catalog(asset=None):
    release=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{BATCH_TAG}')
    assets=[a for a in release['assets'] if a['state']=='uploaded' and
            re.fullmatch(r'batch-catalog-[0-9]+\.json',a['name'])]
    if asset:assets=[a for a in assets if a['name']==asset]
    if not assets:raise StrategyError('NEXT16_CATALOG_NOT_PUBLISHED_YET')
    chosen=max(assets,key=lambda a:a['id'])
    value=read_json(ASSET_BASE+BATCH_TAG+'/'+chosen['name'])
    if (value.get('schema')!='software.hu-batch-catalog.v1' or value.get('tag')!=BATCH_TAG
            or value.get('plan_sha256')!=PLAN_SHA256 or value.get('status')!='COMPLETE'
            or value.get('planned_new_flops')!=16 or value.get('published_new_flops')!=16
            or value.get('native_target_met_flops')!=16 or len(value.get('cases',()))!=16
            or sorted(c['ordinal'] for c in value['cases'])!=list(range(1,17))
            or len({case_id(c['board']) for c in value['cases']})!=16):
        raise StrategyError('NEXT16_COMPLETE_CHECKED_CATALOG_REQUIRED')
    # Bind the received cases to the original immutable plan, not to their own labels.
    p=read_json(ASSET_BASE+BATCH_TAG+'/plan.json');body=dict(p);claimed=body.pop('plan_sha256',None)
    if claimed!=PLAN_SHA256 or digest(body)!=PLAN_SHA256:raise StrategyError('PUBLISHED_BATCH_PLAN_HASH_CHANGED')
    if make_catalog(p,value['cases'])['status']!='COMPLETE':raise StrategyError('NEXT16_PRECISION_TARGET_NOT_MET')
    for c in value['cases']:
        check_bundle(c)
        if (c['case_id']!=case_id(c['board']) or c.get('tag')!=BATCH_TAG
                or not valid_sha(c.get('file_sha256')) or not valid_sha(c.get('policy_sha256'))
                or type(c.get('policy_file_bytes')) is not int or c['policy_file_bytes']<=0):
            raise StrategyError('NEXT16_CASE_IDENTITY_INVALID')
    value['_original_plan']=p
    return value,chosen['name']


def pilot_manifest():
    m=read_json(ASSET_BASE+PILOT_TAG+'/download-manifest.json')
    r=read_json(ASSET_BASE+PILOT_TAG+'/result.json')
    if (m.get('schema')!='software.hu-reference-asset.v1' or not m.get('native_target_met')
            or not valid_sha(m.get('file_sha256')) or not valid_sha(m.get('policy_sha256'))):
        raise StrategyError('PILOT_REFERENCE_MANIFEST_INVALID')
    return check_bundle(dict(ordinal=0,case_id=case_id(r['board']),board=r['board'],tag=PILOT_TAG,
        file_sha256=m['file_sha256'],policy_sha256=m['policy_sha256'],native_target_met=True,
        policy_file_bytes=None,archive_bytes=m['bytes'],archive_sha256=m['sha256'],
        parts=[dict(name=m['asset'],bytes=m['bytes'],sha256=m['sha256'])]))


def receive_archive(manifest,destination):
    """Stream parts directly into one ZIP; never keep parts plus another copy."""
    check_bundle(manifest);destination=Path(destination)
    if destination.exists():raise StrategyError('BATCH_ARCHIVE_DESTINATION_MUST_BE_NEW')
    from strategy.blind_war import SB40_SERIES_TAGS
    if manifest['tag'] not in (BATCH_TAG,PILOT_TAG,'hu-btn-bb-nvt-complete32-20261115','hu-sb-bb40-nvt-pilot-20261115','hu-sb-bb40-nvt-next16-20261116','hu-sb-bb40-nvt-complete34-20261116','hu-sb-bb40-nvt-complete51-20261116',*SB40_SERIES_TAGS.values()):
        raise StrategyError('UNKNOWN_REFERENCE_RELEASE')
    whole=hashlib.sha256();received=0
    with destination.open('xb') as out:
        for part in manifest['parts']:
            sha=hashlib.sha256();size=0
            with fetch(ASSET_BASE+manifest['tag']+'/'+part['name']) as response:
                while True:
                    block=response.read(1024**2)
                    if not block:break
                    size+=len(block);received+=len(block)
                    if size>part['bytes']:raise StrategyError('BATCH_PART_EXCEEDS_DECLARED_SIZE')
                    out.write(block);sha.update(block);whole.update(block)
            if size!=part['bytes'] or sha.hexdigest()!=part['sha256']:
                raise StrategyError('BATCH_PART_CHECKSUM_OR_SIZE_FAILED:'+part['name'])
            print(f"Parte verificada: {part['name']} ({size//1024**2} MiB)",flush=True)
    if received!=manifest['archive_bytes'] or whole.hexdigest()!=manifest['archive_sha256']:
        raise StrategyError('BATCH_FULL_ARCHIVE_CHECKSUM_FAILED')
    return dict(bytes=received,sha256=whole.hexdigest())


def check_bank(bank,manifest,catalog):
    lib=PolicyLibrary(Path(bank)/'library.json')
    if len(lib.entries)!=1:raise StrategyError('BATCH_ARCHIVE_EXPECTED_ONE_POLICY')
    entry=next(iter(lib.entries.values()));policy=lib.open(manifest['board'])
    try:
        if (entry['file_sha256']!=manifest['file_sha256'] or policy.fingerprint!=manifest['policy_sha256']
                or list(policy.root.board)!=manifest['board'] or not policy.quality.get('converged')
                or not policy.quality.get('structurally_complete')):
            raise StrategyError('BATCH_POLICY_DIFFERS_FROM_PUBLISHED_MANIFEST')
        root=policy.root.to_dict();root['board']=catalog['root_template']['board']
        from dataclasses import asdict
        if policy.context!=GameContext(**catalog['context']) or BettingState.from_dict(root)!=BettingState.from_dict(catalog['root_template']):
            raise StrategyError('BATCH_POLICY_GAME_CONTEXT_CHANGED')
        actual=entry['resolved_path'].stat().st_size
        if manifest.get('policy_file_bytes') is not None and actual!=manifest['policy_file_bytes']:
            raise StrategyError('BATCH_POLICY_FILE_SIZE_CHANGED')
        model=digest(dict(context=asdict(policy.context),root=root,
            ranges=[r.to_dict() for r in policy.ranges],menu=asdict(policy.menu)))
        if '_original_plan' in catalog:
            from strategy.range_catalog import ComboRange
            from strategy.action_tree import BetMenu
            g=catalog['_original_plan']['game']
            expected=digest(dict(context=asdict(GameContext(**g['context'])),root=BettingState.from_dict(g['root']).to_dict(),
                ranges=[ComboRange.from_dict(r).to_dict() for r in g['ranges']],menu=asdict(BetMenu(**g['menu']))))
            if model!=expected:raise StrategyError('BATCH_PRIORS_OR_MENU_DIFFER_FROM_ORIGINAL_PLAN')
        if manifest.get('resource_profile'):
            from strategy.campaign_resources import effective_settings
            if '_original_plan' not in catalog:raise StrategyError('RESOURCE_RETRY_REQUIRES_ORIGINAL_CAMPAIGN')
            settings=effective_settings(catalog['_original_plan'],manifest['resource_profile'])
            if policy.quality.get('settings',{}).get('memory_budget_mb')!=settings['memory_mb']:
                raise StrategyError('RESOURCE_RETRY_DIFFERS_FROM_DOWNLOADED_POLICY_BUDGET')
        proof=query_probe(entry['resolved_path'])
        if set(proof['probes'])!={'flop','turn','river'}:raise StrategyError('BATCH_THREE_STREET_LOOKUP_REQUIRED')
        return dict(entry),dict(model_sha256=model,lookup_validation=proof,policy_file_bytes=actual)
    finally:policy.close()


def download_batch(output,*,ordinals=None,include_pilot=True,catalog_asset=None,resume=False):
    if Path(output).exists() and not resume:raise StrategyError('BATCH_OUTPUT_MUST_BE_NEW_OR_EXPLICIT_MANAGED_RESUME')
    catalog,asset=load_catalog(catalog_asset)
    return install_catalog(output,catalog,asset,ordinals=ordinals,include_pilot=include_pilot,resume=resume)


def install_catalog(output,catalog,asset,*,ordinals=None,include_pilot=False,resume=False):
    output=Path(output).resolve()
    if output.exists() and not resume:raise StrategyError('BATCH_OUTPUT_MUST_BE_NEW_OR_EXPLICIT_MANAGED_RESUME')
    maximum=len(catalog['cases']);numbers=sorted(set(range(1,maximum+1) if ordinals is None else ordinals))
    if not numbers or any(type(n) is not int or n not in range(1,maximum+1) for n in numbers):
        raise StrategyError('BATCH_ORDINALS_MUST_BE_WITHIN_1_TO_'+str(maximum))
    cases=[c for c in catalog['cases'] if c['ordinal'] in numbers]
    if include_pilot:cases=[pilot_manifest()]+cases
    owner=dict(schema='software.hu-batch-download.v1',plan_sha256=catalog['plan_sha256'],
        ordinals=numbers,include_pilot=include_pilot)
    marker=output/'owned-download.json'
    if output.exists():
        if not marker.is_file() or json.loads(marker.read_text())!=owner:
            raise StrategyError('EXISTING_FOLDER_IS_NOT_THIS_MANAGED_BATCH_DOWNLOAD')
    else:
        output.mkdir(parents=True);atomic_json(marker,owner)
    bank=output/'bank';(bank/'policies').mkdir(parents=True,exist_ok=True);(bank/'reports').mkdir(exist_ok=True)
    index_path=bank/'library.json'
    index=json.loads(index_path.read_text()) if index_path.exists() else dict(
        schema='software.hu-policy-library.v1',entries=[],context=catalog['context'],
        root_template=catalog['root_template'],plan_sha256=catalog['plan_sha256'])
    settings=catalog.get('profile_settings',{})
    if settings:index['profile_settings']=settings
    existing={e['case_id']:e for e in index['entries']};pending=[m for m in cases if m['case_id'] not in existing]
    if set(existing)-{m['case_id'] for m in cases}:raise StrategyError('RESUMED_BANK_HAS_UNEXPECTED_POLICIES')
    estimate=sum(m.get('policy_file_bytes') or m['archive_bytes']*2 for m in pending)
    if pending:estimate+=max(m['archive_bytes'] for m in pending)+1024**3
    if shutil.disk_usage(output).free<estimate:raise StrategyError('BATCH_NEEDS_MORE_DISK_SPACE:'+str(estimate))
    receipts=[];model=None
    for manifest in cases:
        cid=manifest['case_id'];report_path=bank/'reports'/(cid+'.json')
        if cid in existing:
            lib=PolicyLibrary(index_path);entry=next(e for e in lib.entries.values() if e['case_id']==cid)
            if (entry['file_sha256']!=manifest['file_sha256'] or entry['policy_sha256']!=manifest['policy_sha256']):
                raise StrategyError('RESUMED_BANK_DIFFERS_FROM_CATALOG')
            lib.verify_file(entry);receipt=json.loads(report_path.read_text())
            if receipt.get('status')!='PASS' or receipt.get('policy_sha256')!=manifest['policy_sha256']:
                raise StrategyError('RESUMED_BANK_RECEIPT_CHANGED')
            receipt['lookup_validation']=query_probe(entry['resolved_path'])
        else:
            temp=output/'temporary'/uuid.uuid4().hex;temp.mkdir(parents=True)
            atomic_json(temp/'owned-download.json',owner)
            print('Baixando flop: '+' '.join(manifest['board']),flush=True)
            transfer=receive_archive(manifest,temp/'policy.zip')
            safe_extract(temp/'policy.zip',temp/'bank')
            entry,proof=check_bank(temp/'bank',manifest,catalog)
            if model is not None and proof['model_sha256']!=model:raise StrategyError('BATCH_PRIORS_OR_MENU_CHANGED')
            target=bank/'policies'/(cid+'.sqlite')
            if target.exists():
                from strategy.texassolver_backend import file_hash
                if file_hash(target)!=manifest['file_sha256']:
                    raise StrategyError('BATCH_POLICY_DESTINATION_ALREADY_EXISTS_PRESERVED')
            entry.pop('resolved_path');entry.update(case_id=cid,path='policies/'+cid+'.sqlite')
            if not target.exists():
                (temp/'bank'/next(iter(PolicyLibrary(temp/'bank/library.json').entries.values()))['path']).replace(target)
            receipt=dict(status='PASS',ordinal=manifest['ordinal'],case_id=cid,board=manifest['board'],
                archive=transfer,policy_sha256=manifest['policy_sha256'],file_sha256=manifest['file_sha256'],
                native_target_met=True,pppoker_windows_validated=False,**proof)
            atomic_json(report_path,receipt)
            index['entries'].append(entry);existing[cid]=entry
            index.update(complete_flops=len(index['entries']),planned_flops=len(cases))
            atomic_json(index_path,index)
            # Delete only this owned transfer after the immutable policy and receipt are published.
            shutil.rmtree(temp)
        if model is not None and receipt['model_sha256']!=model:raise StrategyError('BATCH_PRIORS_OR_MENU_CHANGED')
        model=receipt['model_sha256'];receipts.append(receipt)
    temporary=output/'temporary'
    if temporary.exists():
        for child in temporary.iterdir():
            if child.is_symlink() or not child.is_dir():continue
            child_marker=child/'owned-download.json'
            if child_marker.is_file() and json.loads(child_marker.read_text())==owner:shutil.rmtree(child)
    receipt=dict(status='PASS',schema='software.hu-batch-download-receipt.v1',catalog_asset=asset,
        plan_sha256=catalog['plan_sha256'],library=str(index_path),new_flops=len(numbers),
        total_models=len(receipts),pilot_included=include_pilot,policies=receipts,
        scope='PUBLISHED_DATA_TRANSFER_AND_BOT_THREE_STREET_LOOKUP',input_devices_used=False,
        pppoker_windows_validated=False,temporary_transfers_removed=not temporary.exists() or not any(temporary.iterdir()),platform=sys.platform)
    atomic_json(output/'download-receipt.json',receipt)
    print('Banco pronto: '+str(index_path),flush=True)
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output');p.add_argument('--ordinals',nargs='+',type=int)
    p.add_argument('--new-only',action='store_true');p.add_argument('--catalog-asset');p.add_argument('--resume',action='store_true')
    args=p.parse_args(argv)
    output=args.output or ('runtime/hu/nvt-next16-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    download_batch(output,ordinals=args.ordinals,include_pilot=not args.new_only,catalog_asset=args.catalog_asset,resume=args.resume)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (StrategyError,OSError,ValueError,zipfile.BadZipFile) as exc:raise SystemExit('BATCH_DOWNLOAD_ERROR: '+str(exc))
