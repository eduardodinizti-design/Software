"""Resumable BTN/BB flop queue. One worker/process tree at a time; no gameplay."""
import argparse
from collections import Counter,defaultdict
from contextlib import contextmanager,closing
from dataclasses import replace
import itertools
import json
import math
import os
from pathlib import Path
import random
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

from strategy.hu_engine import load_game,DEVELOPMENT_FLOPS,HOLDOUT_FLOPS
from strategy.range_catalog import DECK
from strategy.state_contract import StrategyError,cards,digest
from strategy.texassolver_backend import file_hash


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8') as out:
        json.dump(value,out,sort_keys=True,indent=2,allow_nan=False);out.write('\n');out.flush();os.fsync(out.fileno())
    temp.replace(path)


def canonical_flop(board):
    suits='cdhs';board=cards(board,(3,))
    return min(tuple(sorted(c[0]+dict(zip(suits,p))[c[1]] for c in board)) for p in itertools.permutations(suits))


def catalogue_flops(count=100,seed=20261115):
    if type(count) is not int or count<1:raise StrategyError('POSITIVE_FLOP_COUNT_REQUIRED')
    chosen=[];seen=set()
    for text in DEVELOPMENT_FLOPS+HOLDOUT_FLOPS:
        board=tuple(text.split());key=canonical_flop(board)
        if key not in seen:seen.add(key);chosen.append(board)
    groups=defaultdict(list);universe=set()
    for board in itertools.combinations(DECK,3):
        key=canonical_flop(board)
        if key in universe:continue
        universe.add(key)
        if key in seen:continue
        ranks=["23456789TJQKA".index(c[0]) for c in key]
        bucket=(tuple(sorted(Counter(c[0] for c in key).values())),len({c[1] for c in key}),
                max(ranks)>=11,max(ranks)-min(ranks)<=4)
        groups[bucket].append(key)
    if count>len(universe):raise StrategyError('FLOP_COUNT_EXCEEDS_SUIT_DISTINCT_CATALOGUE')
    rng=random.Random(seed)
    for key in sorted(groups):rng.shuffle(groups[key])
    while len(chosen)<count:
        for key in sorted(groups):
            if groups[key]:chosen.append(groups[key].pop())
            if len(chosen)>=count:break
    return [list(b) for b in chosen[:count]]


def make_plan(game_path,*,count=100,batch_size=16,boards=None,iterations=501,accuracy_pct=.5,
              memory_mb=8192,timeout_seconds=3600,work_disk_mb=8192,bank_disk_mb=0,seed=20261115,threads=2):
    game=json.loads(Path(game_path).read_text());context,root,ranges,menu=load_game(game_path)
    if context.positions!=('BTN','BB') or len(root.board)!=3 or root.history or any(root.acted) or root.actor!=root.oop:
        raise StrategyError('BTN_BB_FLOP_STREET_START_TEMPLATE_REQUIRED')
    if type(batch_size) is not int or batch_size<1 or iterations<11 or accuracy_pct<=0:
        raise StrategyError('INVALID_BATCH_OR_SOLVER_BUDGET')
    if min(memory_mb,timeout_seconds,work_disk_mb)<=0 or bank_disk_mb<0:raise StrategyError('POSITIVE_RESOURCE_BUDGETS_REQUIRED')
    if type(threads) is not int or threads<1:raise StrategyError('POSITIVE_THREAD_BUDGET_REQUIRED')
    values=catalogue_flops(count,seed) if boards is None else [list(cards(b.split() if isinstance(b,str) else b,(3,))) for b in boards]
    identities=[canonical_flop(b) for b in values]
    if not values or len(set(identities))!=len(identities):raise StrategyError('DUPLICATE_SUIT_EQUIVALENT_FLOPS')
    plan=dict(schema='software.hu-batch-plan.v1',game=game,boards=values,batch_size=batch_size,
        workers=1,settings=dict(iterations=iterations,accuracy_pct=accuracy_pct,memory_mb=memory_mb,
        timeout_seconds=timeout_seconds,threads=threads,work_disk_mb=work_disk_mb,bank_disk_mb=bank_disk_mb),
        scope='Exact configured chip-EV BTN/BB model; board coverage is not GTO convergence or Windows validation',
        seed=seed)
    plan['plan_sha256']=digest(plan)
    return plan


def checked_plan(path):
    plan=json.loads(Path(path).read_text());content=dict(plan);fingerprint=content.pop('plan_sha256')
    if plan.get('schema')!='software.hu-batch-plan.v1' or digest(content)!=fingerprint:
        raise StrategyError('BATCH_PLAN_HASH_MISMATCH')
    if plan.get('workers')!=1:raise StrategyError('THIS_QUEUE_REQUIRES_ONE_WORKER_AT_A_TIME')
    return plan


def case_id(board):return digest(sorted(board))[:20]


@contextmanager
def queue_lock(folder):
    with (folder/'driver.lock').open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:raise StrategyError('BATCH_DRIVER_ALREADY_RUNNING') from exc
        try:yield
        finally:
            if os.name=='nt':
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


def open_queue(folder,plan,binary,resources):
    folder=Path(folder).resolve()
    if folder.exists() and not (folder/'plan.json').is_file():
        raise StrategyError('BATCH_OUTPUT_MUST_BE_NEW_OR_AN_EXISTING_MANAGED_QUEUE')
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'plan.json').exists():
        if checked_plan(folder/'plan.json')['plan_sha256']!=plan['plan_sha256']:raise StrategyError('EXISTING_QUEUE_HAS_DIFFERENT_PLAN')
    else:atomic_json(folder/'plan.json',plan)
    for name in ('policies','reports','temporary'):(folder/name).mkdir(exist_ok=True)
    execution=digest([plan['plan_sha256'],file_hash(binary),file_hash(Path(resources)/'compairer/card5_dic_sorted.txt')])
    db=sqlite3.connect(folder/'progress.sqlite3');db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    db.executescript('''CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,ordinal INTEGER,board TEXT,state TEXT,attempt TEXT,payload TEXT);
    ''')
    old=db.execute("SELECT value FROM meta WHERE key='execution'").fetchone()
    if old and old[0]!=execution:db.close();raise StrategyError('SOLVER_OR_PLAN_CHANGED_USE_A_NEW_QUEUE')
    with db:
        db.execute('INSERT OR IGNORE INTO meta VALUES(?,?)',('execution',execution))
        for i,board in enumerate(plan['boards']):
            db.execute('INSERT OR IGNORE INTO jobs VALUES(?,?,?,?,?,?)',(case_id(board),i,json.dumps(board),'PENDING',None,'{}'))
    return folder,db


def folder_bytes(folder):return sum(p.stat().st_size for p in Path(folder).rglob('*') if p.is_file() and not p.is_symlink())


def storage_capacity(policy_reference,destination,*,count=100,work_disk_mb=8192,safety_factor=1.25):
    """Measured estimate, not a guarantee that every board has the same tree size."""
    from strategy.policy_disk import DiskPolicy
    if count<1 or work_disk_mb<=0 or not math.isfinite(safety_factor) or safety_factor<1:
        raise StrategyError('INVALID_CAPACITY_ESTIMATE_PARAMETERS')
    reference=Path(policy_reference).resolve();policy=DiskPolicy(reference)
    try:fingerprint=policy.fingerprint
    finally:policy.close()
    destination=Path(destination).resolve()
    while not destination.exists():destination=destination.parent
    available=shutil.disk_usage(destination).free
    per_case=math.ceil(reference.stat().st_size*safety_factor)
    working=work_disk_mb*1024**2;reserve=512*1024**2
    return dict(schema='software.hu-storage-estimate.v1',reference_policy_sha256=fingerprint,
        reference_policy_bytes=reference.stat().st_size,safety_factor=safety_factor,
        estimated_policy_bytes_per_flop=per_case,available_bytes=available,
        working_space_bytes=working,free_space_reserve_bytes=reserve,planned_flops=count,
        estimated_additional_flops_fitting=max(0,(available-working-reserve)//per_case),
        estimated_required_bytes=count*per_case+working+reserve,
        scope='Estimate from one retained policy; board size varies. Cleaning temporary files does not reclaim final policies.')


def preserve_diagnostics(folder,cid,attempt):
    """Keep small reproducibility records before deleting the large native export."""
    from hashlib import sha256
    destination=folder/'reports'/(cid+'-diagnostics');destination.mkdir(exist_ok=True)
    inventory=[];limit=8*1024**2
    for relative in ('game.json','worker.log','stage.json','native/input.txt','native/tmp_log.txt','native/solver.log'):
        source=Path(attempt)/relative
        if not source.is_file():continue
        size=source.stat().st_size
        with source.open('rb') as f:
            if size>limit:f.seek(-limit,os.SEEK_END)
            data=f.read(limit)
        name=relative.replace('/','-');target=destination/name;temp=target.with_name(name+'.tmp')
        temp.write_bytes(data);temp.replace(target)
        inventory.append(dict(path=str(target.relative_to(folder)),source_bytes=size,
            retained_bytes=len(data),tail_only=size>limit,sha256=sha256(data).hexdigest()))
    return inventory


def cleanup_attempt(folder,attempt,plan_sha):
    root=(folder/'temporary').resolve();target=Path(attempt)
    if target.is_symlink() or not target.resolve().is_relative_to(root) or target.resolve()==root:
        raise StrategyError('CLEANUP_PATH_IS_NOT_A_MANAGED_ATTEMPT')
    marker=target/'owned-by-batch.json'
    if not marker.is_file() or json.loads(marker.read_text()).get('plan_sha256')!=plan_sha:
        raise StrategyError('CLEANUP_MARKER_MISSING_OR_WRONG')
    shutil.rmtree(target)


def publish_index(folder,db,plan):
    entries=[]
    for cid,board,payload in db.execute("SELECT id,board,payload FROM jobs WHERE state='COMPLETE' ORDER BY ordinal"):
        data=json.loads(payload)
        entries.append(dict(case_id=cid,board=json.loads(board),path='policies/'+cid+'.sqlite',
            file_sha256=data['file_sha256'],policy_sha256=data['policy_sha256'],quality=data['quality']))
    index=dict(schema='software.hu-policy-library.v1',plan_sha256=plan['plan_sha256'],
        context=plan['game']['context'],root_template=plan['game']['root'],entries=entries,
        complete_flops=len(entries),planned_flops=len(plan['boards']),max_simultaneous_workers=1)
    atomic_json(folder/'library.json',index)
    counts=dict(db.execute('SELECT state,count(*) FROM jobs GROUP BY state'))
    atomic_json(folder/'progress.json',dict(plan_sha256=plan['plan_sha256'],counts=counts,
        quality_counts=dict(native_target_met=sum(bool(e['quality'].get('converged')) for e in entries),
                            native_target_not_met=sum(not e['quality'].get('converged') for e in entries)),
        batches=(len(plan['boards'])+plan['batch_size']-1)//plan['batch_size'],batch_size=plan['batch_size']))
    return counts


def terminate_tree(process):
    import psutil
    try:children=psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:children=[]
    for child in reversed(children):
        try:child.terminate()
        except psutil.NoSuchProcess:pass
    if process.poll() is None:process.terminate()
    _,alive=psutil.wait_procs(children,timeout=3)
    for child in alive:
        try:child.kill()
        except psutil.NoSuchProcess:pass
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:process.kill();process.wait()


def run_worker(plan_path,board,attempt,binary,resources,parent_pid=None):
    plan=checked_plan(plan_path);settings=plan['settings'];attempt=Path(attempt)
    if os.name!='nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(settings['memory_mb']*1024**2,)*2)
        if sys.platform=='linux' and parent_pid:
            import ctypes
            def stop(signum,frame):raise InterruptedError('BATCH_PARENT_EXITED')
            signal.signal(signal.SIGTERM,stop)
            ctypes.CDLL(None).prctl(1,signal.SIGTERM)
            if os.getppid()!=parent_pid:raise InterruptedError('BATCH_PARENT_ALREADY_EXITED')
    from strategy.native_stream import solve_stream
    game_path=attempt/'game.json';game=dict(plan['game']);game['root']=dict(game['root'],board=board)
    atomic_json(game_path,game);context,root,ranges,menu=load_game(game_path)
    result=solve_stream(binary,resources,attempt/'native',attempt/'policy.sqlite',context,root,ranges,menu,
        iterations=settings['iterations'],accuracy_pct=settings['accuracy_pct'],memory_mb=settings['memory_mb'],
        timeout_seconds=settings['timeout_seconds'],threads=settings['threads'],
        progress=lambda stage,details:atomic_json(attempt/'stage.json',dict(stage=stage,**details)))
    result.update(plan_sha256=plan['plan_sha256'],board=board,
                  file_sha256=file_hash(attempt/'policy.sqlite'),range_sha256=[r.fingerprint for r in ranges],
                  policy_file_bytes=(attempt/'policy.sqlite').stat().st_size,
                  source_export_gzip_bytes=(attempt/'native/strategy.jsonl.gz').stat().st_size)
    atomic_json(attempt/'result.json',result)


def promote(folder,db,plan,cid,attempt,data):
    from strategy.policy_disk import DiskPolicy
    from strategy.native_stream import query_probe
    artifact=folder/'policies'/(cid+'.sqlite');source=Path(attempt)/'policy.sqlite'
    if artifact.exists():
        if file_hash(artifact)!=data['file_sha256']:raise StrategyError('EXISTING_POLICY_CHANGED_DO_NOT_OVERWRITE')
    else:
        if not source.is_file() or file_hash(source)!=data['file_sha256']:raise StrategyError('VALIDATED_WORKER_ARTIFACT_CHANGED')
        source.replace(artifact)
    policy=DiskPolicy(artifact)
    try:
        board=next(b for b in plan['boards'] if case_id(b)==cid)
        expected=dict(plan['game']['root'],board=board)
        from strategy.state_contract import BettingState,GameContext
        from strategy.range_catalog import ComboRange
        expected_ranges=tuple(ComboRange.from_classes(r['class_frequencies'],r['source_id']) if 'class_frequencies' in r else ComboRange.from_dict(r) for r in plan['game']['ranges'])
        if (policy.root.key()!=BettingState.from_dict(expected).key() or policy.context!=GameContext(**plan['game']['context'])
                or [r.fingerprint for r in policy.ranges]!=[r.fingerprint for r in expected_ranges]):
            raise StrategyError('WORKER_POLICY_DOES_NOT_MATCH_PLANNED_GAME_AND_RANGES')
    finally:policy.close()
    probe=query_probe(artifact)
    if probe['policy_sha256']!=data['policy_sha256']:raise StrategyError('POLICY_CHANGED_DURING_PUBLICATION')
    diagnostics=preserve_diagnostics(folder,cid,attempt)
    data=dict(data,diagnostics=diagnostics or data.get('diagnostics',[]))
    atomic_json(folder/'reports'/(cid+'.json'),data)
    with db:db.execute('UPDATE jobs SET state=?,payload=? WHERE id=?',('COMPLETE',json.dumps(data),cid))
    publish_index(folder,db,plan)
    cleanup_attempt(folder,attempt,plan['plan_sha256'])


def run_queue(plan_path,output,binary,resources,*,max_cases=None):
    import psutil
    plan=checked_plan(plan_path);folder,db=open_queue(output,plan,binary,resources)
    if max_cases is not None and (type(max_cases) is not int or max_cases<1):
        db.close();raise StrategyError('MAX_CASES_MUST_BE_POSITIVE')
    attempted_this_run=0
    try:
      with queue_lock(folder):
        publish_index(folder,db,plan)
        for cid,ordinal,board,state,old_attempt,payload in db.execute('SELECT * FROM jobs ORDER BY ordinal').fetchall():
            if state=='COMPLETE':
                data=json.loads(payload);artifact=folder/'policies'/(cid+'.sqlite')
                if not artifact.is_file() or file_hash(artifact)!=data['file_sha256']:raise StrategyError('COMPLETED_POLICY_MISSING_OR_CHANGED')
                if old_attempt and Path(old_attempt).exists():cleanup_attempt(folder,old_attempt,plan['plan_sha256'])
                continue
            if state=='VALIDATED':
                promote(folder,db,plan,cid,old_attempt,json.loads(payload));continue
            if state=='FAILED':continue  # retry is explicit; failed evidence is preserved
            if max_cases is not None and attempted_this_run>=max_cases:break
            if state=='RUNNING':
                prior=json.loads(payload)
                try:
                    process=psutil.Process(prior['pid'])
                    if abs(process.create_time()-prior['created'])<.01:raise StrategyError('PREVIOUS_WORKER_STILL_RUNNING')
                except psutil.NoSuchProcess:pass
            if plan['settings']['bank_disk_mb'] and folder_bytes(folder/'policies')>=plan['settings']['bank_disk_mb']*1024**2:
                raise StrategyError('POLICY_BANK_STORAGE_BUDGET_REACHED')
            if folder_bytes(folder/'temporary')>=plan['settings']['work_disk_mb']*1024**2:
                raise StrategyError('PRESERVED_TEMPORARY_STORAGE_BUDGET_REACHED')
            attempt=folder/'temporary'/(cid+'-'+uuid.uuid4().hex);attempt.mkdir()
            atomic_json(attempt/'owned-by-batch.json',dict(plan_sha256=plan['plan_sha256'],case_id=cid))
            print(json.dumps(dict(event='START',flop=ordinal+1,total=len(plan['boards']),
                batch=ordinal//plan['batch_size']+1,board=json.loads(board))),flush=True)
            command=[sys.executable,'-m','strategy.batch_jobs','worker','--plan',str(folder/'plan.json'),
                '--board',board,'--attempt',str(attempt),'--binary',str(Path(binary).resolve()),
                '--resources',str(Path(resources).resolve()),'--parent-pid',str(os.getpid())]
            peak_rss=0;failure=None;started=time.monotonic();last_disk=0
            with (attempt/'worker.log').open('w') as log:
                attempted_this_run+=1
                process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                with db:db.execute('UPDATE jobs SET state=?,attempt=?,payload=? WHERE id=?',
                    ('RUNNING',str(attempt),json.dumps(dict(pid=process.pid,created=psutil.Process(process.pid).create_time())),cid))
                publish_index(folder,db,plan)
                try:
                    while process.poll() is None:
                        try:
                            family=[psutil.Process(process.pid)]+psutil.Process(process.pid).children(recursive=True)
                            rss=sum(p.memory_info().rss for p in family if p.is_running());peak_rss=max(peak_rss,rss)
                            if rss>plan['settings']['memory_mb']*1024**2:failure='PROCESS_TREE_MEMORY_BUDGET_EXCEEDED'
                        except psutil.NoSuchProcess:pass
                        now=time.monotonic()
                        if now-started>plan['settings']['timeout_seconds']*2:failure='WORKER_TIMEOUT'
                        if now-last_disk>1:
                            last_disk=now
                            if folder_bytes(folder/'temporary')>plan['settings']['work_disk_mb']*1024**2:failure='TEMPORARY_DISK_BUDGET_EXCEEDED'
                            staged=attempt/'policy.sqlite'
                            if plan['settings']['bank_disk_mb'] and staged.exists() and folder_bytes(folder/'policies')+staged.stat().st_size>plan['settings']['bank_disk_mb']*1024**2:
                                failure='POLICY_BANK_STORAGE_BUDGET_REACHED'
                            if shutil.disk_usage(folder).free<512*1024**2:failure='LOW_DISK_SPACE'
                        if failure:terminate_tree(process);break
                        time.sleep(.2)
                except BaseException:
                    terminate_tree(process)
                    with db:db.execute('UPDATE jobs SET state=?,payload=? WHERE id=?',('PENDING',json.dumps(dict(reason='INTERRUPTED',previous_attempt=str(attempt))),cid))
                    raise
            result_path=attempt/'result.json'
            if process.returncode==0 and not failure and result_path.is_file():
                data=json.loads(result_path.read_text());data.update(peak_process_tree_rss_bytes=peak_rss,worker_exited=True)
                if data.get('plan_sha256')!=plan['plan_sha256']:raise StrategyError('WORKER_RETURNED_DIFFERENT_PLAN')
                with db:db.execute('UPDATE jobs SET state=?,payload=? WHERE id=?',('VALIDATED',json.dumps(data),cid))
                promote(folder,db,plan,cid,attempt,data)
                print(json.dumps(dict(event='COMPLETE',flop=ordinal+1,board=json.loads(board),
                    policy_sha256=data['policy_sha256'],converged=data['quality']['converged'],peak_rss_mb=peak_rss/1024**2)),flush=True)
            else:
                failure=failure or 'WORKER_FAILED_SEE_PRESERVED_LOG'
                with db:db.execute('UPDATE jobs SET state=?,payload=? WHERE id=?',('FAILED',json.dumps(dict(reason=failure,returncode=process.returncode,peak_rss=peak_rss)),cid))
                print(json.dumps(dict(event='FAILED',flop=ordinal+1,reason=failure,attempt=str(attempt))),flush=True)
            publish_index(folder,db,plan)
        counts=publish_index(folder,db,plan)
        print(json.dumps(dict(event='STOPPED',counts=counts)),flush=True)
        return counts
    finally:db.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='cmd',required=True)
    a=subs.add_parser('plan');a.add_argument('--game',required=True);a.add_argument('--out',required=True)
    a.add_argument('--count',type=int,default=100);a.add_argument('--boards');a.add_argument('--batch-size',type=int,default=16)
    a.add_argument('--iterations',type=int,default=501);a.add_argument('--accuracy-pct',type=float,default=.5)
    a.add_argument('--threads',type=int,default=2)
    a.add_argument('--memory-mb',type=int,default=8192);a.add_argument('--timeout-seconds',type=int,default=3600)
    a.add_argument('--work-disk-mb',type=int,default=8192);a.add_argument('--bank-disk-mb',type=int,default=0,help='0: no artificial bank quota; disk free-space guard remains')
    a=subs.add_parser('run');a.add_argument('--plan',required=True);a.add_argument('--output',required=True)
    a.add_argument('--binary',required=True);a.add_argument('--resources',required=True);a.add_argument('--max-cases',type=int)
    a=subs.add_parser('status');a.add_argument('--output',required=True)
    a=subs.add_parser('capacity');a.add_argument('--policy-reference',required=True)
    a.add_argument('--destination',required=True);a.add_argument('--count',type=int,default=100)
    a.add_argument('--work-disk-mb',type=int,default=8192);a.add_argument('--safety-factor',type=float,default=1.25)
    a=subs.add_parser('retry-failed');a.add_argument('--output',required=True)
    a=subs.add_parser('worker');a.add_argument('--plan',required=True);a.add_argument('--board',required=True)
    a.add_argument('--attempt',required=True);a.add_argument('--binary',required=True);a.add_argument('--resources',required=True)
    a.add_argument('--parent-pid',type=int)
    args=p.parse_args(argv)
    if args.cmd=='plan':
        if Path(args.out).exists():p.error('Plan already exists; use a new output path')
        kw=vars(args).copy();kw.pop('cmd');game=kw.pop('game');out=kw.pop('out');boards=kw.pop('boards')
        kw['boards']=json.loads(Path(boards).read_text()) if boards else None
        atomic_json(out,make_plan(game,**kw));print(str(Path(out).resolve()));return 0
    if args.cmd=='worker':
        run_worker(args.plan,json.loads(args.board),args.attempt,args.binary,args.resources,args.parent_pid);return 0
    if args.cmd=='run':
        result=run_queue(args.plan,args.output,args.binary,args.resources,max_cases=args.max_cases)
        return 1 if result.get('FAILED') else 0
    if args.cmd=='status':
        folder=Path(args.output).resolve();result=json.loads((folder/'progress.json').read_text())
        with closing(sqlite3.connect((folder/'progress.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
            result['active']=[dict(case_id=cid,board=json.loads(board),stage=json.loads((Path(attempt)/'stage.json').read_text()) if (Path(attempt)/'stage.json').exists() else 'STARTING')
                              for cid,board,attempt in db.execute("SELECT id,board,attempt FROM jobs WHERE state='RUNNING'")]
        print(json.dumps(result,indent=2));return 0
    if args.cmd=='capacity':
        print(json.dumps(storage_capacity(args.policy_reference,args.destination,count=args.count,
            work_disk_mb=args.work_disk_mb,safety_factor=args.safety_factor),indent=2));return 0
    folder=Path(args.output).resolve()
    with queue_lock(folder),closing(sqlite3.connect(folder/'progress.sqlite3')) as db,db:
        db.execute("UPDATE jobs SET state='PENDING' WHERE state='FAILED'")
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (StrategyError,OSError,ValueError) as exc:raise SystemExit('HU_BATCH_ERROR: '+str(exc))
