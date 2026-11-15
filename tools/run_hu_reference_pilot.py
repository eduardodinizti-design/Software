"""Compute and package one full NVT reference on a GitHub runner, without input."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_jobs import atomic_json,make_plan
from strategy.texassolver_backend import file_hash


def notice(value):
    value=json.dumps(value,sort_keys=True,allow_nan=False)
    print('::notice title=HU reference progress::'+value.replace('%','%25').replace('\n','%0A').replace('\r','%0D'),flush=True)


def post_progress_status(value):
    context=os.environ.get('HU_GITHUB_STATUS_CONTEXT')
    if not context:return
    stage=(value.get('stage') or {}).get('stage','STARTING')
    if stage=='SOLVING' and value.get('native_export_gzip_bytes',0)>0:stage='EXPORTING'
    metric=value.get('last_native_metric') or {}
    description=stage+(' i='+str(metric['iteration']+1) if 'iteration' in metric else '')
    if 'public_nodes' in (value.get('stage') or {}):description+=' nodes='+str(value['stage']['public_nodes'])
    if 'exploitibility' in metric:description+=' exploit='+format(metric['exploitibility'],'.4f')+'%'
    payload=dict(state='pending',context=context,description=description[:140],
        target_url=os.environ.get('HU_GITHUB_RUN_URL',''))
    try:
        result=subprocess.run(['gh','api',f"repos/{os.environ['GITHUB_REPOSITORY']}/statuses/{os.environ['GITHUB_SHA']}",
            '--method','POST','--input','-'],input=json.dumps(payload),text=True,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,timeout=30)
        if result.returncode:print('Commit progress status unavailable; calculation continues.',flush=True)
    except (OSError,subprocess.TimeoutExpired):
        print('Commit progress status unavailable; calculation continues.',flush=True)


def progress(bank):
    out={}
    try:out.update(json.loads((bank/'progress.json').read_text()))
    except FileNotFoundError:pass
    for attempt in (bank/'temporary').glob('*'):
        stage=attempt/'stage.json';metrics=attempt/'native/tmp_log.txt'
        try:out['stage']=json.loads(stage.read_text())
        except FileNotFoundError:pass
        try:
            lines=metrics.read_text().splitlines()
            if lines:out['last_native_metric']=json.loads(lines[-1])
        except (FileNotFoundError,json.JSONDecodeError):pass
        export=attempt/'native/strategy.jsonl.gz'
        try:out['native_export_gzip_bytes']=export.stat().st_size
        except FileNotFoundError:pass  # a successful worker may already have cleaned its export
    return out


def report_worker_failure(output,bank):
    paths=[output/'driver.txt',*sorted((bank/'temporary').glob('*/worker.log'))[:3]]
    records=[]
    for path in paths:
        try:
            with path.open('rb') as source:
                source.seek(0,2);source.seek(max(0,source.tell()-5000));tail=source.read().decode(errors='replace')
            records.append(dict(path=str(path.relative_to(output)),tail=tail))
        except FileNotFoundError:pass
    notice(dict(event='WORKER_FAILED',diagnostics=records))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',required=True);p.add_argument('--resources',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--game',default='docs/software-hu-engine-20261115/game-flop-btn-bb.json')
    p.add_argument('--iterations',type=int,default=501);p.add_argument('--threads',type=int,default=4)
    p.add_argument('--accuracy-pct',type=float,default=.5)
    p.add_argument('--memory-mb',type=int,default=8192)
    p.add_argument('--work-disk-mb',type=int,default=10240)
    p.add_argument('--timeout-seconds',type=int,default=7200)
    p.add_argument('--asset-name',default='btn-bb-As7d2c-nvt-reference.zip')
    p.add_argument('--profile-settings',help='Explicit arrival/ante settings JSON; does not change the solved policy')
    args=p.parse_args(argv)
    if Path(args.asset_name).name!=args.asset_name or not args.asset_name.endswith('.zip'):p.error('Safe ZIP asset name required')
    output=Path(args.output).resolve()
    if output.exists():p.error('Use a new output directory; previous calculations are preserved')
    output.mkdir(parents=True)
    bank=output/'bank';delivery=output/'delivery';delivery.mkdir()
    game=json.loads(Path(args.game).read_text())
    plan=make_plan(args.game,boards=[game['root']['board']],iterations=args.iterations,
        accuracy_pct=args.accuracy_pct,threads=args.threads,memory_mb=args.memory_mb,
        timeout_seconds=args.timeout_seconds,work_disk_mb=args.work_disk_mb,batch_size=1)
    if args.profile_settings:
        from strategy.operational_profile import OperationalProfile
        from strategy.state_contract import digest
        settings=json.loads(Path(args.profile_settings).read_text())
        OperationalProfile('profile-configuration-check',**settings)
        plan.pop('plan_sha256');plan['profile_settings']=settings;plan['plan_sha256']=digest(plan)
    atomic_json(output/'plan.json',plan)
    command=[sys.executable,'-m','strategy.batch_jobs','run','--plan',str(output/'plan.json'),
        '--output',str(bank),'--binary',str(Path(args.binary).resolve()),'--resources',str(Path(args.resources).resolve())]
    started=time.monotonic()
    with (output/'driver.txt').open('w') as log:
        worker=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
            env={k:v for k,v in os.environ.items() if k not in ('GH_TOKEN','GITHUB_TOKEN')})
        try:
            last=0
            while worker.poll() is None:
                elapsed=time.monotonic()-started
                if elapsed-last>=60 or last==0:
                    state=dict(elapsed_seconds=round(elapsed),**progress(bank))
                    notice(state);post_progress_status(state);last=max(1,elapsed)
                time.sleep(5)
        except BaseException:
            from strategy.batch_jobs import terminate_tree
            terminate_tree(worker);raise
    if worker.returncode:
        report_worker_failure(output,bank)
        raise SystemExit('Pilot failed; reports and diagnostics retained at '+str(output))
    return package_study(output,args.game,args.asset_name,time.monotonic()-started)


def package_study(output,game_path,asset_name,elapsed_seconds):
    output=Path(output);bank=output/'bank';delivery=output/'delivery';delivery.mkdir(exist_ok=True)
    game=json.loads(Path(game_path).read_text())
    index=json.loads((bank/'library.json').read_text())
    if len(index['entries'])!=1:raise SystemExit('Expected exactly one complete policy')
    entry=index['entries'][0];report=json.loads((bank/'reports'/(entry['case_id']+'.json')).read_text())
    if not report['coverage']['structurally_complete'] or set(report['lookup_validation']['probes'])!={'flop','turn','river'}:
        raise SystemExit('Missing complete tree or bot lookup proof')
    if list((bank/'temporary').iterdir()):raise SystemExit('Successful attempt was not cleaned up')
    summary=dict(schema='software.hu-reference-delivery.v1',created_at=datetime.now(timezone.utc).isoformat(),
        scope='NVT_REFERENCE_FULL_TREE_NATIVE_REPORTED_PRECISION_NOT_INDEPENDENT_GTO_OR_PPPOKER_VALIDATION',
        policy_sha256=entry['policy_sha256'],file_sha256=entry['file_sha256'],
        board=entry['board'],quality=entry['quality'],coverage=report['coverage'],
        lookup_validation=report['lookup_validation'],
        native_target_met=bool(entry['quality'].get('converged')),iterations=entry['quality'].get('iterations'),
        global_gap_bb=entry['quality'].get('global_gap_bb'),source_game_sha256=file_hash(game_path),
        prior_ranges_confirmed_as='User approved available NVT ranges as reference; no direct HRC export certification',
        elapsed_seconds=elapsed_seconds,temporary_cleanup_verified=True,worker_exited=True,
        policy_file_bytes=report['policy_file_bytes'],source_export_gzip_bytes=report['source_export_gzip_bytes'],
        peak_process_tree_rss_bytes=report['peak_process_tree_rss_bytes'],
        pppoker_windows_validated=False,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
    if report.get('recovery'):summary['recovery']=report['recovery']
    atomic_json(delivery/'result.json',summary)
    readme=('REFERENCIA NVT '+ ' x '.join(game['context']['positions'])+' — banco completo de flop/turn/river.\n'
        'Precisao nativa atingida: '+str(summary['native_target_met'])+'\n'
        'Gap global nativo (BB): '+str(summary['global_gap_bb'])+'\n'
        'O indicador nativo nao substitui validacao independente ou no PPPoker Windows.\n'
        'Extraia em pasta nova. Consulte pelo Software com --postflop-library library.json.\n'
        'Modelo exato: '+json.dumps(dict(context=game['context'],root=game['root'],menu=game['menu']))+'\n')
    (delivery/'LEIA_PRIMEIRO.txt').write_text(readme,encoding='utf-8')
    archive=delivery/asset_name
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for folder in ('policies','reports'):
            for path in sorted((bank/folder).rglob('*')):
                if path.is_file():z.write(path,str(path.relative_to(bank)))
        for name in ('library.json','plan.json','progress.json'):z.write(bank/name,name)
        z.write(delivery/'result.json','result.json');z.write(delivery/'LEIA_PRIMEIRO.txt','LEIA_PRIMEIRO.txt')
    manifest=dict(schema='software.hu-reference-asset.v1',asset=archive.name,bytes=archive.stat().st_size,
        sha256=file_hash(archive),file_sha256=entry['file_sha256'],policy_sha256=entry['policy_sha256'],
        native_target_met=summary['native_target_met'])
    atomic_json(delivery/'download-manifest.json',manifest)
    notice(dict(event='PACKAGED',**manifest))
    return 0


if __name__=='__main__':raise SystemExit(main())
