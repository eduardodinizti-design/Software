"""One command for laboratory regression; does not open PPPoker or capture desktop."""
import argparse,concurrent.futures,datetime,json,os,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=['test_capture_regressions','test_window_capture_engine','test_window_capture_audit',
 'test_capture_windows_native','test_table_reading','test_rank_confirmation','test_diagnostic_storage',
 'test_continuous_observer','test_capture_review','test_region_presentation','test_action_buttons',
 'test_lab_metrics','test_corner_sampling','test_community_cards','test_detector_batch','test_detector_proposals','test_ocr_runtime','test_rank_templates','test_button_templates','test_roi_geometry','test_template_sample_collection','test_exact_call_template']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'docs/table-reading/batch/regression')
    args=p.parse_args();assets=args.assets.resolve();out=args.output.resolve()
    if not assets.is_dir():p.error('Assets directory missing')
    out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,VISUALPILOT_ASSETS=str(assets),OMP_THREAD_LIMIT="1")
    commands=[('contracts',[sys.executable,'-m','unittest',*CONTRACTS,'-v']),
      ('hero_development',[sys.executable,'tools/evaluate_table_reading.py','--assets',str(assets),'--output',str(out/'hero-results.json')]),
      ('colored_boards',[sys.executable,'tools/evaluate_colored_boards.py','--assets',str(assets)]),
      ('board_transitions',[sys.executable,'tools/replay_board_transitions.py','--assets',str(assets)]),
      ('turn_variants',[sys.executable,'tools/evaluate_turn_variants.py','--assets',str(assets)])]
    commands += [(name,[sys.executable,script,'--assets',str(assets),'--output',str(out/(name+'.json'))]) for name,script in [('hero_extended','tools/hero_batch.py'),('board_extended','tools/board_batch_evaluation.py'),('colored_eight','tools/board_batch_eight.py'),('rank_template_coverage','tools/evaluate_rank_fastpath.py'),('protected_rank_regression','tools/validate_guarded_ranks.py'),('pipeline_integrated','tools/validate_next_block.py'),('detector_extended','scripts/detector_batch.py')]]
    # A bounded worker pool runs independent replay jobs, not live desktop tasks.
    def execute(job):
        name,command=job;started=time.monotonic();log=out/(name+'.log')
        try:
            with log.open('w',encoding='utf8') as stream:
                proc=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
            code=proc.returncode;error=None
        except subprocess.TimeoutExpired:code=124;error='TIMEOUT_300_SECONDS'
        result=dict(name=name,exit_code=code,passed=code==0,seconds=round(time.monotonic()-started,2),log=log.name,error=error)
        print(json.dumps(result),flush=True);return result
    results=[execute(commands[0])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results.extend(pool.map(execute,commands[1:]))
    summary=dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='Laboratory contracts and reused development replays. Windows-native test may be skipped on Linux; inspect contracts.log.',
        all_jobs_passed=all(r['passed'] for r in results),jobs=results)
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    return 0 if summary['all_jobs_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
