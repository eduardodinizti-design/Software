"""Calculate/publish full NVT campaign models on isolated GitHub runners."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import (BATCH_TAG,REPOSITORY,checked_batch_plan,make_catalog,
    split_archive,verify_remote_parts)
from strategy.batch_jobs import atomic_json
from strategy.policy_library import PolicyLibrary
from strategy.river_validation import review_reference_river
from strategy.range_catalog import DECK
from strategy.texassolver_backend import file_hash
from strategy.campaign_resources import checked_resource_profile,effective_settings


def gh(*args,body=None):
    result=subprocess.run(['gh',*args],input=json.dumps(body) if body is not None else None,
        text=True,capture_output=True,check=True,timeout=60)
    return json.loads(result.stdout) if result.stdout.strip() else None


def status(case,state,description):
    if not os.environ.get('GITHUB_SHA'):return
    payload=dict(state=state,description=description[:140],context=f"{os.environ.get('HU_GITHUB_STATUS_PREFIX','hu-next16')}/{case['ordinal']:02d}",
        target_url=os.environ.get('HU_GITHUB_RUN_URL',''))
    try:gh('api',f"repos/{REPOSITORY}/statuses/{os.environ['GITHUB_SHA']}",'--method','POST','--input','-',body=payload)
    except (OSError,subprocess.SubprocessError):print('Progress status unavailable; calculation continues.',flush=True)


def release():return gh('api',f'repos/{REPOSITORY}/releases/tags/{BATCH_TAG}')


def remote_manifests(plan):
    value=release();out=[]
    for a in value['assets']:
        if not a['name'].startswith('manifest-case-') or a['state']!='uploaded':continue
        req=urllib.request.Request(a['browser_download_url'],headers={'User-Agent':'Software-HU-next16/1'})
        with urllib.request.urlopen(req,timeout=60) as response:m=json.loads(response.read(4*1024**2))
        if m.get('plan_sha256')==plan['plan_sha256']:
            verify_remote_parts(m,value['assets']);out.append(m)
    return out


def initialize(plan,path):
    label=plan.get('label','BTN/BB NVT: 16 novos flops e politicas completas')
    notes=(label+f"; {len(plan['cases'])} modelos novos, priors NVT de referencia autorizados.\n\n"
        'Os calculos estao em andamento. Cada manifest-case identifica uma politica completa arquivada.\n'
        'O catalogo final informa quantos atingiram o alvo nativo. Nenhum teste PPPoker real e alegado.\n'
        'Os arquivos ZIP sao divididos em partes de ate 1 GiB, com SHA-256 por parte e do arquivo integral.\n')
    note_file=path.parent/'release-notes.txt';note_file.write_text(notes)
    result=subprocess.run(['gh','release','view',BATCH_TAG,'--repo',REPOSITORY],capture_output=True)
    if result.returncode:
        subprocess.run(['gh','release','create',BATCH_TAG,'--repo',REPOSITORY,'--target',os.environ['GITHUB_SHA'],
            '--prerelease','--title',label,'--notes-file',str(note_file)],check=True)
        subprocess.run(['gh','release','upload',BATCH_TAG,'--repo',REPOSITORY,str(path)],check=True)
    else:
        asset=next((a for a in release()['assets'] if a['name']==path.name and a['state']=='uploaded'),None)
        if asset is None:raise SystemExit('Existing release has no original plan; preserve it and inspect before retrying')
        with urllib.request.urlopen(asset['browser_download_url'],timeout=60) as response:old=json.load(response)
        if old.get('plan_sha256')!=plan['plan_sha256']:raise SystemExit('Existing release belongs to another plan; use a new tag')


def run_case(args,plan):
    case=next(c for c in plan['cases'] if c['ordinal']==args.ordinal)
    status(case,'pending','Checking previously saved policies')
    for m in remote_manifests(plan):
        if m['case_id']==case['case_id'] and m['native_target_met']:
            status(case,'success','Existing complete policy and remote hashes verified')
            print(json.dumps(dict(event='REUSED_VALIDATED_REMOTE_POLICY',case=case)),flush=True);return 0
    root=Path(args.output).resolve()
    if root.exists():raise SystemExit('Use a new case output directory to preserve previous work')
    root.mkdir(parents=True);game=dict(plan['game']);game['root']=dict(game['root'],board=case['board'])
    atomic_json(root/'game.json',game);execution=getattr(args,'execution_profile_data',None)
    s=effective_settings(plan,execution)
    os.environ['HU_GITHUB_STATUS_CONTEXT']=f"{os.environ.get('HU_GITHUB_STATUS_PREFIX','hu-next16')}/{case['ordinal']:02d}"
    from run_hu_reference_pilot import main as pilot
    try:
        asset=plan.get('archive_filename','btn-bb-As7d2c-nvt-reference.zip')
        extra=[]
        if plan.get('profile_settings'):
            atomic_json(root/'profile-settings.json',plan['profile_settings'])
            extra=['--profile-settings',str(root/'profile-settings.json')]
        if getattr(args,'ready_study',None):
            study=Path(args.ready_study).resolve();marker=json.loads((study/'recovered-study.json').read_text())
            if marker.get('campaign_plan_sha256')!=plan['plan_sha256']:raise SystemExit('Recovered study belongs to a different campaign')
        else:
            pilot(['--game',str(root/'game.json'),'--output',str(root/'study'),'--binary',args.binary,
            '--resources',args.resources,'--iterations',str(s['iterations']),'--threads',str(s['threads']),
            '--accuracy-pct',str(s['accuracy_pct']),'--memory-mb',str(s['memory_mb']),
            '--work-disk-mb',str(s['work_disk_mb']),'--timeout-seconds',str(s['timeout_seconds']),'--asset-name',asset]+extra)
            study=root/'study'
        bank=study/'bank';delivery=study/'delivery'
        result=json.loads((delivery/'result.json').read_text());archive=delivery/asset
        if getattr(args,'ready_study',None):
            from strategy.batch_download import check_bank
            manifest=dict(board=case['board'],file_sha256=result['file_sha256'],policy_sha256=result['policy_sha256'],policy_file_bytes=result['policy_file_bytes'])
            check_bank(bank,manifest,dict(context=game['context'],root_template=game['root'],_original_plan=plan))
        status(case,'pending','Complete tree verified; reviewing conditional river')
        lib=PolicyLibrary(bank/'library.json');policy=lib.open(case['board'])
        try:
            runout=[]
            for card in ('Ts','2h')+DECK:
                if card not in policy.root.board and card not in runout:runout.append(card)
                if len(runout)==2:break
            river=review_reference_river(policy,tuple(runout))
            atomic_json(delivery/'river-independent.json',river)
        finally:policy.close()
        checksum=file_hash(archive);prefix=f"case-{case['ordinal']:02d}-{case['case_id']}-{checksum[:12]}"
        bundle=split_archive(archive,delivery/'parts',prefix)
        if bundle['archive_sha256']!=checksum:raise SystemExit('Archive changed while splitting')
        status(case,'pending','Uploading complete policy parts and verifying remote SHA-256')
        for part in bundle['parts']:
            subprocess.run(['gh','release','upload',BATCH_TAG,'--repo',REPOSITORY,str(delivery/'parts'/part['name'])],check=True)
        manifest=dict(schema='software.hu-batch-case.v1',plan_sha256=plan['plan_sha256'],
            ordinal=case['ordinal'],case_id=case['case_id'],board=case['board'],tag=BATCH_TAG,
            policy_sha256=result['policy_sha256'],file_sha256=result['file_sha256'],
            policy_file_bytes=result['policy_file_bytes'],native_target_met=result['native_target_met'],
            global_gap_bb=result['global_gap_bb'],iterations=result['iterations'],quality=result['quality'],
            lookup_streets=sorted(result['lookup_validation']['probes']),
            measurements={k:result[k] for k in ('elapsed_seconds','policy_file_bytes','source_export_gzip_bytes','peak_process_tree_rss_bytes')},
            coverage=result['coverage'],independent_river=dict(nash_conv_bb=river['nash_conv_bb'],
                joint_private_deals=river['joint_private_deals'],runout=runout,scope=river['scope']),
            source_commit=os.environ['GITHUB_SHA'],worker_exited=result['worker_exited'],
            temporary_cleanup_verified=result['temporary_cleanup_verified'],**bundle)
        if result.get('recovery'):manifest['recovery']=result['recovery']
        if execution:
            manifest['resource_profile']=execution
            manifest['effective_execution_settings']=s
        for _ in range(6):
            try:verify_remote_parts(manifest,release()['assets']);break
            except ValueError:time.sleep(5)
        else:raise SystemExit('Remote parts did not pass SHA-256 verification')
        stamp=f"{prefix}-{os.environ.get('GITHUB_RUN_ATTEMPT','1')}"
        atomic_json(delivery/('manifest-'+stamp+'.json'),manifest)
        atomic_json(delivery/('result-'+stamp+'.json'),result)
        atomic_json(delivery/('river-'+stamp+'.json'),river)
        # The manifest is published LAST, after the complete policy is durable.
        for name in ('result-','river-','manifest-'):
            subprocess.run(['gh','release','upload',BATCH_TAG,'--repo',REPOSITORY,str(delivery/(name+stamp+'.json'))],check=True)
        status(case,'success' if manifest['native_target_met'] else 'failure',
            'Complete policy archived; native target met' if manifest['native_target_met'] else 'Policy archived; native precision target not met')
        print('::notice title=Next16 published case::'+json.dumps({k:manifest[k] for k in
            ('ordinal','board','policy_sha256','iterations','global_gap_bb','native_target_met','policy_file_bytes')}),flush=True)
        return 0 if manifest['native_target_met'] else 1
    except BaseException:
        status(case,'failure','Case failed; preserved diagnostics or archive, see job');raise


def check_existing(args,plan):
    case=next(c for c in plan['cases'] if c['ordinal']==args.ordinal)
    matches=[m for m in remote_manifests(plan) if m['case_id']==case['case_id'] and m['native_target_met']]
    for manifest in matches:make_catalog(plan,[manifest])
    reused=bool(matches)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('reused='+str(reused).lower()+'\n')
    if reused:status(case,'success','Previously published complete policy and remote hashes reused; no CFR repeated')
    value=dict(reused=reused,ordinal=args.ordinal)
    atomic_json(args.output,value)
    print(json.dumps(value))
    return 0


def catalog(plan,output):
    result=make_catalog(plan,remote_manifests(plan));folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    atomic_json(folder/'batch-catalog.json',result)
    count=len(plan['cases'])
    lines=[plan.get('label','LOTE NVT — 16 NOVOS FLOPS'),f"Estado: {result['status']}",
        f"Politicas completas publicadas: {result['published_new_flops']}/{count}",
        f"Alvo nativo atingido: {result['native_target_met_flops']}/{count}",'']
    for m in result['cases']:
        lines.append(f"{m['ordinal']:02d}. {' '.join(m['board'])} | iteracoes={m['iterations']} | gap={m['global_gap_bb']:.9f} BB | alvo={m['native_target_met']}")
    lines.extend(['','NVT de referencia; precisao nativa nao e certificacao GTO independente ou PPPoker real.'])
    report=f'RELATORIO_LOTE_{count}.txt'
    (folder/report).write_text('\n'.join(lines)+'\n')
    for name in ('batch-catalog.json',report):
        # Catalogs are new run-specific evidence, never overwrite previous ones.
        attempt=('-a'+os.environ.get('GITHUB_RUN_ATTEMPT','1')) if plan.get('catalog_protocol')=='run-attempt-v1' else ''
        unique=folder/(Path(name).stem+'-'+os.environ['GITHUB_RUN_ID']+attempt+Path(name).suffix)
        shutil.copyfile(folder/name,unique)
        subprocess.run(['gh','release','upload',BATCH_TAG,'--repo',REPOSITORY,str(unique)],check=True)
        if name=='batch-catalog.json' and os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as target:target.write('catalog_asset='+unique.name+'\n')
    print('::notice title=Next16 batch result::'+json.dumps({k:result[k] for k in
        ('status','planned_new_flops','published_new_flops','native_target_met_flops')}),flush=True)
    return 0 if result['status']=='COMPLETE' else 1


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cmd',choices=('init','case','catalog','check'))
    p.add_argument('--plan',required=True);p.add_argument('--ordinal',type=int);p.add_argument('--binary')
    p.add_argument('--resources');p.add_argument('--output',default='runtime/hu-next16')
    p.add_argument('--ready-study',help='Previously recovered, complete checked study; no native solve is started')
    p.add_argument('--execution-profile',help='Hashed resource-only retry; cannot change ranges, menu or strategic solver settings')
    args=p.parse_args(argv)
    raw=json.loads(Path(args.plan).read_text())
    if raw.get('schema')=='software.hu-campaign-plan.v1':
        from strategy.campaign import checked_campaign_plan
        plan=checked_campaign_plan(args.plan)
    else:plan=checked_batch_plan(args.plan)
    global BATCH_TAG
    BATCH_TAG=plan['tag']
    args.execution_profile_data=None
    if args.execution_profile:
        args.execution_profile_data=checked_resource_profile(json.loads(Path(args.execution_profile).read_text()),plan)
    if args.cmd=='init':
        initialize(plan,Path(args.plan))
        if args.execution_profile_data:
            path=Path(args.execution_profile)
            old=next((a for a in release()['assets'] if a['name']==path.name and a['state']=='uploaded'),None)
            if old:
                with urllib.request.urlopen(old['browser_download_url'],timeout=60) as response:value=json.load(response)
                if value!=args.execution_profile_data:raise SystemExit('Existing resource profile is different; preserve it')
            else:subprocess.run(['gh','release','upload',BATCH_TAG,'--repo',REPOSITORY,str(path)],check=True)
        return 0
    if args.cmd=='catalog':return catalog(plan,args.output)
    if args.cmd=='check':
        if args.ordinal not in range(1,len(plan['cases'])+1):p.error('Check requires a planned ordinal')
        return check_existing(args,plan)
    if args.ordinal not in range(1,len(plan['cases'])+1) or (not args.ready_study and (not args.binary or not args.resources)):
        p.error('Case requires a planned ordinal and a native solver or recovered complete study')
    return run_case(args,plan)


if __name__=='__main__':raise SystemExit(main())
