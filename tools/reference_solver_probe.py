"""Bounded, local-only GTOpen calculations against a pinned external checkout.

Does not vendor or alter the upstream engine. Saves configs, numeric node views,
gap readbacks and provenance; these solve its approximation, not full NLHE/HRC.
The server is owned by this invocation, bound to loopback on a separate port.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

PIN='5c2989397abf314f229d293c16f96ea783c7ca5b'


def labels():
    ranks='23456789TJQKA';out=[]
    for a in range(13):
        for b in range(13):
            out.append(ranks[a]*2 if a==b else ranks[max(a,b)]+ranks[min(a,b)]+('s' if a>b else 'o'))
    return out


def lock_range(hands,kind='call'):
    weights={h:1. for h in hands}
    return dict(call=[weights.get(h,0.) if kind=='call' else 0. for h in labels()],
                **{'raise':[weights.get(h,0.) if kind=='raise' else 0. for h in labels()]},
                jam=[0.]*169,raise_size='min')


def request(port,route,value=None):
    data=None if value is None else json.dumps(value,allow_nan=False).encode()
    req=urllib.request.Request(f'http://127.0.0.1:{port}/api/{route}',data=data,
                               headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'{route}: HTTP {exc.code}: {exc.read().decode()}') from exc


def config(depth,positions):
    return dict(positions=positions,stack=depth,posts=[0.]*(len(positions)-2)+[.5,1.],
                ante=0.,limp=True,open_raises=[2.5,4.],raise_mults=[3.],fourbet_mults=[2.5],
                max_raises=4,add_allin=True,allin_threshold=1.,rake_pct=0.,rake_cap=0.,
                no_flop_no_drop=True,realization='balanced',call_only_seats=[])


def unwrap(value):return value.get('result',value)


def choose(node,kind,target=None):
    candidates=[]
    for i,a in enumerate(node.get('actions') or []):
        k=a.get('kind');label=a.get('label','').lower()
        if k==kind or (kind=='call' and ('call' in label or 'limp' in label)) or (kind=='fold' and label=='fold') or (kind=='raise' and k in ('raise','bet')):
            candidates.append((i,a))
    if not candidates:raise ValueError(f'Missing {kind} in {node.get("actions")}')
    if target is None:return candidates[0][0]
    return min(candidates,key=lambda x:abs(float(x[1].get('to',x[1].get('amount',0.)))-target))[0]


def calculate(port,case,iterations,seconds):
    cfg=case['config'];estimate=request(port,'preflop/estimate',cfg)
    if not estimate.get('ok'):raise ValueError('Tree exceeds bounded laboratory resources: '+str(estimate))
    build=request(port,'preflop/spot',cfg);path=[];locks=[]
    for spec in case['prefix']:
        node=unwrap(request(port,'preflop/node',{'path':path}))
        idx=choose(node,spec['kind'],spec.get('to'))
        if 'range' in spec:
            policy=lock_range(spec['range'],spec['kind'])
            request(port,'preflop/lock',{'path':path,'policy':policy})
            locks.append(dict(path=path.copy(),actor=node.get('actor_pos'),kind=spec['kind'],hands=spec['range']))
        elif spec['kind']=='fold':
            request(port,'preflop/lock',{'path':path,'policy':lock_range([])})
            locks.append(dict(path=path.copy(),actor=node.get('actor_pos'),kind='fold',hands=[]))
        path.append(idx)
    request(port,'preflop/solve',dict(iterations=iterations,check_every=50,target_gap=.02))
    deadline=time.monotonic()+seconds;status={}
    while time.monotonic()<deadline:
        status=request(port,'preflop/status')
        if status.get('state') not in ('running','solving'):break
        time.sleep(.5)
    else:
        request(port,'preflop/stop',{})
        for _ in range(60):
            status=request(port,'preflop/status')
            if status.get('state') not in ('running','solving'):break
            time.sleep(.2)
    node=unwrap(request(port,'preflop/node',{'path':path}))
    if status.get('error'):raise ValueError('Solver worker error: '+str(status['error']))
    return dict(id=case['id'],config=cfg,estimate=estimate,build=build,path=path,locks=locks,
                status=status,node=node,hand_order=labels(),
                scope='CFR for the configured approximate continuation model; fixed prefix hand models are explicit, not empirical/HRC priors.',
                solver_validated=False,independently_validated=False)


def cases(depths):
    pairs=[r*2 for r in '23456789TJQKA']
    limps=pairs+['A2s','A3s','A4s','A5s','A6s','A7s','A8s','A9s','ATs','AJs','AQs','AKs','KQs','KJs','QJs','JTs','T9s','98s','87s','76s','65s','AQo','AJo','KQo']
    opening=pairs+['AKs','AQs','AJs','ATs','A9s','A8s','A7s','A6s','A5s','A4s','A3s','A2s','KQs','KJs','KTs','QJs','QTs','JTs','T9s','98s','AKo','AQo','AJo','KQo']
    calls=['22','33','44','55','66','77','88','99','TT','JJ','QQ','AKs','AQs','AJs','ATs','KQs','KJs','QJs','JTs','T9s','98s','AKo','AQo']
    three=['AA','KK','QQ','JJ','TT','AKs','AQs','AJs','KQs','A5s','A4s','AKo','AQo']
    four=['AA','KK','QQ','AKs','AKo','A5s']
    for depth in depths:
        yield dict(id=f'two_limps_BTN_{depth:g}',config=config(depth,['UTG','HJ','BTN','SB','BB']),
                   prefix=[dict(kind='call',range=limps),dict(kind='call',range=limps)])
        yield dict(id=f'open_two_callers_BB_{depth:g}',config=config(depth,['UTG','HJ','CO','SB','BB']),
                   prefix=[dict(kind='raise',to=2.5,range=opening),dict(kind='call',range=calls),dict(kind='call',range=calls),dict(kind='fold')])
        common=[dict(kind='raise',to=2.5,range=opening),dict(kind='fold'),dict(kind='raise',to=7.5,range=three),dict(kind='fold')]
        yield dict(id=f'CO_vs_SB_3bet_{depth:g}',config=config(depth,['CO','BTN','SB','BB']),prefix=common)
        yield dict(id=f'SB_vs_CO_4bet_{depth:g}',config=config(depth,['CO','BTN','SB','BB']),
                   prefix=common+[dict(kind='raise',to=18.75,range=four)])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--upstream',type=Path,required=True)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--depths',nargs='+',type=float,default=[50.,80.,200.]);p.add_argument('--iterations',type=int,default=1000)
    p.add_argument('--case-seconds',type=int,default=180);p.add_argument('--port',type=int,default=37139)
    args=p.parse_args();root=args.upstream.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if sha!=PIN:raise ValueError('External source revision differs from audited pin.')
    env=dict(os.environ,SOLVER_THREADS='2',SOLVER_MEM_MB='4000',PREFLOP_MAX_ARENA_MB='1800',
             PREFLOP_MAX_NODES='1000000',SOLVER_GPU='0',PORT=str(args.port),GTOPEN_HOST='127.0.0.1')
    with (out/'backend.log').open('w') as log:
        child=subprocess.Popen([str(args.binary.resolve())],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
        results=[]
        try:
            for _ in range(200):
                if child.poll() is not None:raise RuntimeError('Backend exited; inspect backend.log.')
                try:request(args.port,'status');break
                except (OSError,RuntimeError):time.sleep(.1)
            else:raise RuntimeError('Backend startup timed out.')
            for case in cases(args.depths):
                print('Calculating',case['id'],flush=True)
                try:
                    result=calculate(args.port,case,args.iterations,args.case_seconds)
                    (out/(case['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
                    results.append(dict(id=case['id'],status='CALCULATED',solver_status=result['status'],
                                        low_reach=result['node'].get('low_reach'),strategy_note=result['node'].get('strategy_note')))
                except Exception as exc:
                    results.append(dict(id=case['id'],status='FAILED',error=str(exc)))
                    print('Case failed:',exc,flush=True)
        finally:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
    report=dict(upstream='MatthewPDingle/GTOpen',commit=sha,scope='Bounded CPU laboratory calculations, not PPPoker/HRC validation.',cases=results)
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if results and all(r['status']=='CALCULATED' for r in results) else 1


if __name__=='__main__':raise SystemExit(main())
