"""Reuse the complete 171-iteration export; repair import, never rerun the solve."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_jobs import atomic_json,case_id,checked_plan,cleanup_attempt,preserve_diagnostics
from strategy.blind_war import SB40_TAG
from strategy.campaign import checked_campaign_plan
from strategy.campaign_download import PLANS
from strategy.hu_engine import load_game
from strategy.native_stream import compact_stream,query_probe
from strategy.state_contract import StrategyError,digest
from strategy.texassolver_backend import SOURCE_COMMIT,file_hash,input_commands
from run_hu_reference_pilot import package_study,progress,notice,post_progress_status

SOURCE_RUN=43769679234
RAW_ARTIFACT=14186865931
RAW_ARTIFACT_ZIP_SHA256='67cfb02929707347af4489caa20d60db49576d73e87e8db6387c5e5088427b18'


def one_file(root,name):
    values=[p for p in Path(root).rglob(name) if p.is_file() and not p.is_symlink()]
    if len(values)!=1:raise StrategyError('ONE_RECOVERED_SOURCE_REQUIRED:'+name)
    return values[0]


def worker(request):
    import resource
    budget=request['settings']['memory_budget_mb']*1024**2
    resource.setrlimit(resource.RLIMIT_AS,(budget,budget))
    attempt=Path(request['attempt']);context,root,ranges,menu=load_game(attempt/'game.json')
    started=time.monotonic();metrics=[json.loads(line) for line in (attempt/'native/tmp_log.txt').read_text().splitlines() if line.strip()]
    if metrics[-1]['iteration']!=170 or metrics[-1]['exploitibility']>.5:raise StrategyError('SOURCE_171_ITERATION_TARGET_REQUIRED')
    result=compact_stream(attempt/'native/strategy.jsonl.gz',attempt/'policy.sqlite',context,root,ranges,menu,
        request['settings'],request['provenance'],metrics,
        progress=lambda stage,details:atomic_json(attempt/'stage.json',dict(stage=stage,**details)))
    result.update(lookup_validation=query_probe(attempt/'policy.sqlite'),elapsed_seconds=time.monotonic()-started,
        file_sha256=file_hash(attempt/'policy.sqlite'),policy_file_bytes=(attempt/'policy.sqlite').stat().st_size,
        source_export_gzip_bytes=(attempt/'native/strategy.jsonl.gz').stat().st_size)
    atomic_json(attempt/'result.json',result)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--export-dir');p.add_argument('--diagnostics-dir')
    p.add_argument('--output');p.add_argument('--worker-request');args=p.parse_args(argv)
    if args.worker_request:worker(json.loads(Path(args.worker_request).read_text()));return 0
    if not all((args.export_dir,args.diagnostics_dir,args.output)):p.error('export, diagnostics and a new output directory required')
    output=Path(args.output).resolve()
    if output.exists():raise StrategyError('RECOVERY_OUTPUT_MUST_BE_NEW')
    campaign=checked_campaign_plan('docs/software-hu-close32-sb40-20261115/sb40-plan.json')
    if campaign['plan_sha256']!=PLANS[SB40_TAG][1]:raise StrategyError('PINNED_SB40_CAMPAIGN_REQUIRED')
    export_root=Path(args.export_dir).resolve()
    owner=json.loads((export_root/'owned-recovery-download.json').read_text())
    if owner!=dict(schema='software.hu-sb40-recovery-download.v1',source_run=SOURCE_RUN,artifact_id=RAW_ARTIFACT):
        raise StrategyError('ONLY_THIS_WORKFLOWS_OWNED_RECOVERY_DOWNLOAD_MAY_BE_CLEANED')
    plans=[]
    for path in Path(args.diagnostics_dir).rglob('plan.json'):
        value=json.loads(path.read_text())
        if value.get('schema')=='software.hu-batch-plan.v1':plans.append(checked_plan(path))
    if not plans or any(v!=plans[0] for v in plans):raise StrategyError('ONE_UNCHANGED_SOURCE_BATCH_PLAN_REQUIRED')
    plan=plans[0]
    if digest(plan['game'])!=digest(campaign['game']) or plan.get('profile_settings')!=campaign['profile_settings']:
        raise StrategyError('RECOVERY_GAME_OR_ANTE_DIFFERS_FROM_ORIGINAL_PLAN')
    raw=one_file(args.export_dir,'strategy.jsonl.gz');source_input=one_file(args.diagnostics_dir,'input.txt')
    if not raw.resolve().is_relative_to(export_root):raise StrategyError('RECOVERY_EXPORT_OUTSIDE_OWNED_DOWNLOAD')
    source_metrics=one_file(args.diagnostics_dir,'tmp_log.txt');source_log=one_file(args.diagnostics_dir,'solver.log')
    raw_sha=file_hash(raw);output.mkdir(parents=True);bank=output/'bank';cid=case_id(plan['game']['root']['board'])
    for name in ('policies','reports','temporary','delivery'):(output/name if name=='delivery' else bank/name).mkdir(parents=True,exist_ok=True)
    atomic_json(bank/'plan.json',plan);atomic_json(output/'plan.json',plan)
    attempt=bank/'temporary'/('reused-'+cid);(attempt/'native').mkdir(parents=True)
    atomic_json(attempt/'owned-by-batch.json',dict(plan_sha256=plan['plan_sha256']))
    atomic_json(attempt/'game.json',campaign['game']);context,root,ranges,menu=load_game(attempt/'game.json')
    commands,settings=input_commands(context,root,ranges,menu,iterations=plan['settings']['iterations'],
        threads=plan['settings']['threads'],accuracy_pct=plan['settings']['accuracy_pct'],dump_rounds=3,
        native_raise_limit=max(1,menu.max_raises))
    commands=commands.replace('dump_result strategy.json','dump_result_stream strategy.jsonl.gz')
    if source_input.read_text()!=commands:raise StrategyError('RECOVERED_INPUT_DIFFERS_FROM_FROZEN_GAME')
    os.link(raw,attempt/'native/strategy.jsonl.gz')
    for source,name in ((source_input,'input.txt'),(source_metrics,'tmp_log.txt'),(source_log,'solver.log')):
        shutil.copyfile(source,attempt/'native'/name)
    settings.update(memory_budget_mb=plan['settings']['memory_mb'],memory_limit_enforced=False,
        export_format='street_jsonl_gzip',recovery_converter_memory_limit_enforced=True)
    provenance=dict(repository='https://github.com/bupticybee/TexasSolver',tested_source_commit=SOURCE_COMMIT,
        training_repository_commit='be854b58c4f678d5776f4b43b8e0dadc2086543f',training_workflow_run=SOURCE_RUN,
        binary_sha256=None,binary_identity_note='Original executable hash was not retained in failure artifacts; no substitute hash is claimed.',
        command_sha256=hashlib.sha256(commands.encode()).hexdigest(),native_export_sha256=raw_sha,
        reused_export=True,source_artifact_id=RAW_ARTIFACT,source_artifact_zip_sha256=RAW_ARTIFACT_ZIP_SHA256,
        hu_chance_denominator_cards=4,decoder_fix='EFFECTIVE_COVERING_SHOVE_TO_PHYSICAL_ALL_IN_WITH_UNCALLED_REFUND',
        decoder_repository_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),license='AGPL-3.0; native source installed separately')
    request=output/'worker-request.json';atomic_json(request,dict(attempt=str(attempt),settings=settings,provenance=provenance))
    started=time.monotonic();peak=0;last=0
    import psutil
    with (attempt/'worker.log').open('w') as log:
        process=subprocess.Popen([sys.executable,__file__,'--worker-request',str(request)],stdout=log,stderr=subprocess.STDOUT,
            env={k:v for k,v in os.environ.items() if k not in ('GH_TOKEN','GITHUB_TOKEN')})
        while process.poll() is None:
            try:peak=max(peak,psutil.Process(process.pid).memory_info().rss)
            except psutil.NoSuchProcess:pass
            elapsed=time.monotonic()-started
            if elapsed-last>=60:
                value=dict(elapsed_seconds=round(elapsed),**progress(bank));notice(value);post_progress_status(value);last=elapsed
            time.sleep(2)
    if process.returncode:raise StrategyError('RECOVERY_CONVERTER_FAILED:'+ (attempt/'worker.log').read_text()[-8000:])
    result=json.loads((attempt/'result.json').read_text());target=bank/'policies'/(cid+'.sqlite')
    (attempt/'policy.sqlite').replace(target)
    result['diagnostics']=preserve_diagnostics(bank,cid,attempt)
    result['peak_process_tree_rss_bytes']=peak
    result['recovery']=dict(source_run=SOURCE_RUN,source_raw_artifact=RAW_ARTIFACT,raw_export_sha256=raw_sha,
        native_solve_repeated=False,source_iterations=171,worker_exited=True,
        measured_peak_rss_scope='RECOVERY_CONVERTER_ONLY; original native peak RSS was not retained',
        original_training_binary_hash_retained=False)
    shutil.copytree(args.diagnostics_dir,bank/'reports'/(cid+'-initial-failure-source'))
    atomic_json(bank/'reports'/(cid+'.json'),result)
    entry=dict(case_id=cid,board=list(root.board),path='policies/'+cid+'.sqlite',
        file_sha256=result['file_sha256'],policy_sha256=result['policy_sha256'],quality=result['quality'])
    atomic_json(bank/'library.json',dict(schema='software.hu-policy-library.v1',plan_sha256=plan['plan_sha256'],
        context=campaign['game']['context'],root_template=campaign['game']['root'],profile_settings=campaign['profile_settings'],
        entries=[entry],complete_flops=1,planned_flops=1,max_simultaneous_workers=1))
    atomic_json(bank/'progress.json',dict(plan_sha256=plan['plan_sha256'],counts=dict(COMPLETE=1)))
    cleanup_attempt(bank,attempt,plan['plan_sha256'])
    # The immutable source remains in GitHub's recovery artifact. Release only
    # this workflow's downloaded export after the full bank and receipt exist.
    raw.unlink()
    atomic_json(output/'recovered-study.json',dict(campaign_plan_sha256=campaign['plan_sha256'],native_solve_repeated=False))
    package_study(output,_game_copy(output,campaign['game']),campaign['archive_filename'],time.monotonic()-started)
    return 0


def _game_copy(output,game):
    path=Path(output)/'game.json';atomic_json(path,game);return path


if __name__=='__main__':raise SystemExit(main())
