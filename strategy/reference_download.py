"""Download a published reference bank, verify hashes and optionally replay it.

The ZIP is data only. No downloaded executable is run and no input device is
used. A fresh directory preserves existing banks and local work.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path,PurePosixPath
import shutil
import stat
import urllib.request
import uuid
import zipfile

from strategy.batch_jobs import atomic_json
from strategy.policy_library import PolicyLibrary
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash

REPOSITORY='eduardodinizti-design/Software'
TAG='hu-btn-bb-nvt-reference-20261115'


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Software-HU-reference/1'}),timeout=60)


def safe_extract(archive,destination):
    destination=Path(destination).resolve()
    if destination.exists():raise StrategyError('EXTRACTION_DESTINATION_MUST_BE_NEW')
    with zipfile.ZipFile(archive) as z:
        names=set();members=z.infolist()
        for info in members:
            name=info.filename;posix=PurePosixPath(name)
            if (posix.is_absolute() or '..' in posix.parts or '\\' in name or ':' in name or '\x00' in name
                    or stat.S_ISLNK(info.external_attr>>16) or name in names):
                raise StrategyError('REFERENCE_ZIP_UNSAFE_OR_DUPLICATE_PATH')
            names.add(name)
            if not (destination/name).resolve().is_relative_to(destination):raise StrategyError('REFERENCE_ZIP_ESCAPES_DESTINATION')
        needed=sum(i.file_size for i in members)+512*1024**2
        if needed>shutil.disk_usage(destination.parent).free:raise StrategyError('REFERENCE_EXTRACTION_NEEDS_MORE_DISK_SPACE')
        destination.mkdir()
        for info in members:
            target=destination/info.filename
            if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as source,target.open('xb') as out:shutil.copyfileobj(source,out,1024**2)


def download_reference(output,*,verify=False):
    output=Path(output).resolve()
    if output.exists():raise StrategyError('DOWNLOAD_OUTPUT_MUST_BE_NEW_TO_PRESERVE_EXISTING_BANKS')
    base=f'https://github.com/{REPOSITORY}/releases/download/{TAG}/'
    with fetch(base+'download-manifest.json') as response:
        raw=response.read(1024**2+1)
        if len(raw)>1024**2:raise StrategyError('REFERENCE_MANIFEST_TOO_LARGE')
        manifest=json.loads(raw)
    asset=manifest.get('asset','');size=manifest.get('bytes')
    if (manifest.get('schema')!='software.hu-reference-asset.v1' or Path(asset).name!=asset
            or not asset.endswith('.zip') or type(size) is not int or size<=0
            or len(manifest.get('sha256',''))!=64):
        raise StrategyError('REFERENCE_DOWNLOAD_MANIFEST_INVALID')
    output.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(output.parent).free<size+512*1024**2:raise StrategyError('REFERENCE_DOWNLOAD_NEEDS_MORE_DISK_SPACE')
    output.mkdir();archive=output/'reference.zip';temporary=output/'reference.zip.part'
    received=0;h=hashlib.sha256();last=0
    with fetch(base+asset) as response,temporary.open('xb') as out:
        while True:
            block=response.read(1024**2)
            if not block:break
            received+=len(block)
            if received>size:raise StrategyError('REFERENCE_DOWNLOAD_EXCEEDS_DECLARED_SIZE')
            h.update(block);out.write(block)
            if received-last>=128*1024**2:
                print(f'Download: {received//1024**2} / {size//1024**2} MiB',flush=True);last=received
    if received!=size or h.hexdigest()!=manifest['sha256']:raise StrategyError('REFERENCE_ARCHIVE_CHECKSUM_OR_SIZE_FAILED')
    temporary.replace(archive);bank=output/'bank';safe_extract(archive,bank)
    library=PolicyLibrary(bank/'library.json')
    if len(library.entries)!=1:raise StrategyError('REFERENCE_EXPECTED_ONE_POLICY')
    policy=library.open(next(iter(library.entries)))
    try:
        entry=next(iter(library.entries.values()))
        if policy.fingerprint!=manifest['policy_sha256'] or entry['file_sha256']!=manifest['file_sha256']:
            raise StrategyError('REFERENCE_POLICY_DIFFERS_FROM_RELEASE_MANIFEST')
        receipt=dict(status='PASS',repository=REPOSITORY,tag=TAG,library=str(bank/'library.json'),
            archive_sha256=h.hexdigest(),archive_bytes=received,policy_sha256=policy.fingerprint,
            policy_file_sha256=entry['file_sha256'],native_target_met=policy.quality.get('converged',False),
            scope='DOWNLOADED_REFERENCE_BANK_HASH_AND_FORMAT_VALIDATION',pppoker_windows_validated=False)
        if verify:
            from strategy.reference_validation import verify_reference_hand
            result=verify_reference_hand(policy,output/'verification',library=library)
            receipt['synthetic_hand_validation']=dict(status=result['status'],scope=result['scope'],
                decisions=result['decisions'],event_counts=result['event_counts'],input_devices_used=False)
    finally:policy.close()
    # Only this verified download's temporary archive is removed; bank stays.
    archive.unlink();receipt['download_archive_removed']=True
    atomic_json(output/'download-receipt.json',receipt)
    print('Banco salvo em: '+str(bank),flush=True)
    print('Resultado: '+str(output/'download-receipt.json'),flush=True)
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output');p.add_argument('--verify',action='store_true')
    args=p.parse_args(argv)
    output=args.output or ('runtime/hu/nvt-reference-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    download_reference(output,verify=args.verify);return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (StrategyError,OSError,ValueError,zipfile.BadZipFile) as exc:raise SystemExit('REFERENCE_DOWNLOAD_ERROR: '+str(exc))
