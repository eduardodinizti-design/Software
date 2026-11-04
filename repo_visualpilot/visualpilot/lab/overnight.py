"""Bounded unattended LAB experiments; no autonomous code edits or live actions.

Run with python -m visualpilot.lab.overnight --hours 6 --output sessions/overnight.
Same output resumes checkpoints if source fingerprint is unchanged. STOP requests shutdown.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]


def atomic_json(path,data):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,indent=2),encoding='utf-8');os.replace(tmp,path)


def fingerprint():
    digest=hashlib.sha256(sys.version.encode())
    paths=[ROOT/'pyproject.toml',ROOT/'requirements.lock']+list((ROOT/'visualpilot').rglob('*.py'))+list((ROOT/'tests').rglob('*.py'))+list((ROOT/'tests/fixtures').glob('*.json'))
    for path in sorted(paths):digest.update(str(path.relative_to(ROOT)).encode());digest.update(path.read_bytes())
    return digest.hexdigest()


def terminate(proc):
    if proc.poll() is not None:return
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:
        try:os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:return
    try:proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name!='nt':
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        else:proc.kill()
        proc.wait()


def run_process(command,log_path,timeout,stop_path=None):
    """Poll cancellation; kill the job's process tree on timeout/interruption."""
    start=time.monotonic()
    with open(log_path,'w',encoding='utf-8') as log:
        kwargs={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
        proc=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,**kwargs)
        try:
            while proc.poll() is None:
                if stop_path and Path(stop_path).exists():
                    terminate(proc);return {'status':'stopped','seconds':time.monotonic()-start}
                if time.monotonic()-start>=timeout:
                    terminate(proc);return {'status':'timeout','seconds':time.monotonic()-start}
                time.sleep(.1)
            return dict(status='ok' if proc.returncode==0 else 'failed',returncode=proc.returncode,seconds=time.monotonic()-start)
        finally:terminate(proc)


def hero_combinations():
    """Two distinct suit assignments for each of the 169 preflop classes.

    This samples 338 physical hands, not all 1,326 combinations. Stable
    shuffling spreads strength classes early in a time-bounded run.
    """
    from itertools import combinations
    import random
    from ..agent.connector import canonical_hand
    groups={}
    for cards in combinations([r+s for r in '23456789TJQKA' for s in 'hdcs'],2):
        groups.setdefault(canonical_hand(cards),[]).append(list(cards))
    hands=[]
    for key in sorted(groups):
        variants=groups[key]
        hands.extend([variants[0],variants[-1]])
    random.Random(42).shuffle(hands)
    return hands


def manifest(smoke=False):
    from .scenario_matrix import CONTEXTS
    if smoke:return [dict(context='BB_vs_BTN',texture='paired',hero=['Jh','Th'])]
    hands=hero_combinations()
    textures=['paired','four_flush','monotone','flush_draw','top_pair_overcard','connected']
    cells=[(t,c) for t in textures for c in CONTEXTS]
    # Rotate board/position while traversing hands: a short run must not spend
    # its entire budget on a single hand class or board.
    return [dict(context=cells[(i+round_index)%len(cells)][1],
                 texture=cells[(i+round_index)%len(cells)][0],hero=hand)
            for round_index in range(len(cells)) for i,hand in enumerate(hands)]


def work(spec):
    from ..agent.nvt_ranges import NvtRangeBook
    from .scenario_matrix import make_case,condition_on_check
    from .multistreet import SearchConfig,solve_postflop
    from .opponent_models import size_sensitive_model
    book=NvtRangeBook(ROOT/'tests/fixtures/nvt_position_excerpt.json')
    model=size_sensitive_model(.5)
    try:case=make_case(book,spec['case']['context'],spec['case']['texture'],hero=spec['case']['hero'])
    except ValueError as exc:return dict(status='excluded',reason=str(exc))
    cfg=SearchConfig(chance_method='stratified',chance_samples=spec['samples'],exact_turn=spec['exact'],seed=spec['seed'])
    case=condition_on_check(case,model,cfg)
    result=solve_postflop(case['hero'],case['board'],case['range'],case['pot'],case['stack'],model,
        'synthetic-size-sensitive-v1-aggression-.5',cfg,hero_position=case['hero_position'],opponent_checked=case['opponent_checked'])
    # Compact checkpoint; hashes and full inputs allow reproduction without huge overnight files.
    fields=('status','reason','chosen','comparisons','exact_under_model','seconds','nodes','input_sha256','response_sha256','inputs')
    return dict({k:result[k] for k in fields if k in result},provenance=case['provenance'])


def supervise(output,hours=6,smoke=False,resume_stopped=False):
    from .numerical_audit import audit_numerical_case
    if hours not in (6,7,8):raise ValueError('Duração deve ser6,7ou8horas.')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    lock=sqlite3.connect(output/'runner.lock.sqlite',timeout=.1,isolation_level=None)
    try:lock.execute('BEGIN EXCLUSIVE')
    except Exception:lock.close();raise RuntimeError('Já existe executor nesta pasta.')
    deadline=time.monotonic()+(180 if smoke else hours*3600)
    state_path=output/'state.json';code=fingerprint();cases=manifest(smoke)
    identity=dict(source_sha256=code,smoke=smoke,cases=cases)
    state=dict(identity=identity,results={},started_at=datetime.now(timezone.utc).isoformat())
    try:
        if state_path.exists():
            state=json.loads(state_path.read_text())
            if state['identity']!=identity:raise ValueError('Código/plano mudou. Use uma nova pasta para não misturar resultados.')
        if resume_stopped:(output/'STOP').unlink(missing_ok=True)
        def save(status):
            state.update(status=status,updated_at=datetime.now(timezone.utc).isoformat());atomic_json(state_path,state)
            passed=sum(r.get('numerically_accepted',False) for r in state['results'].values())
            report=(f'VisualPilot - laboratorio noturno\nEstado: {status}\nCasos registrados: {len(state["results"])} / {len(cases)}\n'
                    f'Aceitos numericamente sob modelo sintetico: {passed}\n'
                    'Nao equivale a GTO ou validacao estrategica. Nenhum codigo ou cliente foi alterado.\n'
                    'Para retomar, execute o mesmo comando/pasta. Mudanca de codigo exige nova pasta.\n')
            (output/'RELATORIO.txt').write_text(report,encoding='utf-8')
        def available():return time.monotonic()<deadline and not (output/'STOP').exists()
        def checkpoint(name,spec=None,baseline=False):
            path=output/(name+'.json')
            if path.exists():return json.loads(path.read_text())
            if not available():return dict(status='stopped')
            if fingerprint()!=code:raise ValueError('Código mudou durante execução; encerrando para preservar comparações.')
            if baseline:
                command=[sys.executable,'-m','unittest']+(['tests.test_overnight'] if smoke else ['discover','-s','tests'])
            else:
                spec_path=output/(name+'.input.json');atomic_json(spec_path,spec)
                command=[sys.executable,'-m','visualpilot.lab.overnight','--worker',str(spec_path),'--result',str(path)]
            result=run_process(command,output/(name+'.log'),min(600 if baseline else 180,max(0,deadline-time.monotonic())),output/'STOP')
            if result['status']=='stopped' or (result['status']=='timeout' and time.monotonic()>=deadline):
                return dict(status='stopped',reason='budget_or_stop')
            if result['status']=='ok' and not baseline and path.exists():return json.loads(path.read_text())
            atomic_json(path,result);return result
        save('running')
        if checkpoint('baseline',baseline=True)['status']!='ok':save('baseline_failed_or_stopped');return state
        for i,case in enumerate(cases):
            key=f'case-{i:03d}'
            if key in state['results']:continue
            if not available():break
            spec=dict(case=case,samples=6,exact=True,seed=11)
            reference=checkpoint(key+'-reference',spec)
            if reference['status']=='stopped':break
            if reference['status']!='experimental' or not reference.get('exact_under_model'):
                state['results'][key]=dict(case=case,status=reference['status'],reason=reference.get('reason'),numerically_accepted=False)
                save('running');continue
            attempts=[];interrupted=False
            for count in ((6,) if smoke else (6,12,24)):
                runs=[]
                for seed in (11,23,47):
                    run=checkpoint(f'{key}-n{count}-s{seed}',dict(case=case,samples=count,exact=False,seed=seed))
                    if run['status']=='stopped':interrupted=True;break
                    runs.append(run)
                if interrupted:break
                audit=audit_numerical_case(reference,runs)
                attempts.append(dict(samples=count,audit=audit))
                if audit['numerically_accepted']:break
            if interrupted:break
            state['results'][key]=dict(case=case,attempts=attempts,**attempts[-1]['audit'])
            save('running')
        save('completed' if len(state['results'])==len(cases) else 'paused_checkpointed')
        return state
    except KeyboardInterrupt:
        if 'save' in locals():save('paused_checkpointed')
        return state
    except Exception as exc:
        if 'save' in locals():
            state['error']=str(exc);save('failed')
        raise
    finally:
        lock.rollback();lock.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--hours',type=int,choices=(6,7,8),default=6)
    p.add_argument('--output',default='sessions/overnight');p.add_argument('--smoke',action='store_true')
    p.add_argument('--worker');p.add_argument('--result');p.add_argument('--resume-stopped',action='store_true');args=p.parse_args()
    if args.worker:
        if not args.result:raise ValueError('Destino do worker ausente.')
        atomic_json(args.result,work(json.loads(Path(args.worker).read_text())))
    else:
        state=supervise(args.output,args.hours,args.smoke,args.resume_stopped)
        print(state['status'],len(state['results']),flush=True)

if __name__=='__main__':main()
