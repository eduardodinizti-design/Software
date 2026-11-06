"""Bounded passive session: native captures and reports, never gameplay input."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid
import cv2
from table_reading.pipeline import analyze_tables


def identity(meta):
    return tuple(meta.get(k) for k in ('hwnd','pid','process_created','executable'))


def run_session(engine, hwnds, *, minutes=30, interval=2, budget_mb=1024,
                output=Path('logs/sessoes'), analyze=analyze_tables,
                clock=time.monotonic, sleep=time.sleep):
    if not 1<=minutes<=120 or not .25<=interval<=60 or not 1<=budget_mb<=10240:
        raise ValueError('Duracao 1..120 min; intervalo .25..60 s; limite 1..10240 MiB')
    hwnds=list(dict.fromkeys(hwnds))
    if not hwnds or len(hwnds)>6 or any(h<=0 for h in hwnds):raise ValueError('Selecione 1..6 HWNDs validos')
    folder=Path(output)/('sessao-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    start=clock();deadline=start+minutes*60;counts=Counter();known={};used=0;seq=0;stop='DURATION_COMPLETE';durations=[]
    limit=int(budget_mb*1024*1024);reserve=65536
    print('Pasta:',folder.resolve(),flush=True)
    print('Sem cliques. Capturas PNG nativas e leituras; Ctrl+C encerra. Limite:',budget_mb,'MiB.',flush=True)
    try:
        with (folder/'leituras.jsonl').open('wb') as log:
            while clock()<deadline:
                cycle=clock()
                for hwnd in hwnds:
                    if clock()>=deadline:break
                    seq+=1;t=clock();frame=None;png=None
                    record=dict(sequence=seq,hwnd=hwnd,started_utc=datetime.now(timezone.utc).isoformat(),elapsed_s=round(t-start,3),actions_executed=False)
                    try:
                        frame,meta=engine.capture_frame(hwnd=hwnd);record['capture']=meta
                        if frame is None or meta.get('status')!='SUCCESS' or meta.get('hwnd')!=hwnd:
                            record['status']='CAPTURE_FAILED';counts['capture_failures']+=1
                        else:
                            ident=identity(meta)
                            if any(v is None for v in ident) or (hwnd in known and known[hwnd]!=ident):
                                record['status']='SOURCE_CHANGED';stop='SOURCE_CHANGED'
                            else:
                                known[hwnd]=ident
                                ok,encoded=cv2.imencode('.png',frame,[cv2.IMWRITE_PNG_COMPRESSION,3])
                                if not ok:raise RuntimeError('PNG encoding failed')
                                png=encoded.tobytes();record['image']=f'frame-{seq:06d}-hwnd-{hwnd}.png'
                                try:
                                    report=analyze(frame,meta,max_tables=6,read_buttons=True,read_community=True)
                                    record.update(status='ANALYZED',report=report)
                                    counts['analyzed_frames']+=1
                                    if report.get('ocr',{}).get('status')=='UNAVAILABLE':counts['ocr_unavailable']+=1
                                    for row in report.get('tables',[]):
                                        counts['table_regions']+=1
                                        if row.get('status')!='COMPLETE_CANDIDATE':counts['rejected_regions']+=1;continue
                                        counts['complete_table_observations']+=1
                                        counts['hero_complete' if all(row.get('hero_cards',[None,None])) else 'hero_incomplete']+=1
                                        counts['board_'+str(row.get('board',{}).get('status','NOT_READ'))]+=1
                                        counts['buttons_'+str(row.get('action_buttons',{}).get('status','NOT_READ'))]+=1
                                except Exception as exc:
                                    record.update(status='ANALYSIS_ERROR',error=repr(exc));counts['analysis_errors']+=1
                    except Exception as exc:
                        record.update(status='ERROR',error=repr(exc));counts['errors']+=1
                    ms=(clock()-t)*1000;durations.append(ms)
                    record['duration_ms']=round(ms,2)
                    payload=(json.dumps(record,ensure_ascii=False)+'\n').encode('utf8')
                    if used+len(payload)+(len(png) if png else 0)+reserve>limit:
                        stop='STORAGE_LIMIT';counts['unsaved_attempts']+=1;break
                    if png:
                        (folder/record['image']).write_bytes(png);used+=len(png);counts['saved_frames']+=1
                    log.write(payload);log.flush();used+=len(payload);counts['saved_records']+=1
                    print(f"{seq}: HWND {hwnd} | {record['status']} | {ms:.0f} ms | {used/1024/1024:.1f} MiB",flush=True)
                    if 'report' in record:
                        from table_reading.presentation import describe_regions
                        for line in describe_regions(record['report']):print(line,flush=True)
                    if stop=='SOURCE_CHANGED':break
                if stop!='DURATION_COMPLETE':break
                sleep(min(max(0,interval-(clock()-cycle)),max(0,deadline-clock())))
    except KeyboardInterrupt:stop='USER_STOP'
    except Exception as exc:stop='IO_OR_SESSION_ERROR';counts['session_errors']+=1;print(repr(exc))
    finally:
        values=sorted(durations)
        summary=dict(stop_reason=stop,elapsed_s=round(clock()-start,2),requested_minutes=minutes,
                     hwnds=hwnds,interval_s=interval,budget_mib=budget_mb,bytes_written_before_summary=used,
                     counts=dict(counts),capture_and_read_ms=dict(n=len(values),median=values[len(values)//2] if values else None,
                     p95=values[min(len(values)-1,int(len(values)*.95))] if values else None),
                     accuracy_validated=False,actions_executed=False,
                     limitations=['Periodic samples, not video: events between captures can be missed.',
                     'Displayed buttons do not prove which action the user took.',
                     'No persistent table identity across moves; source HWND plus per-frame boxes only.',
                     'Pots, stacks and full action history are not decoded by this reader.',
                     'Counts include attempted processing; saved_records/saved_frames describe persisted evidence.'])
        (folder/'resumo.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
        print('Encerrado:',stop,'| Resultado:',folder.resolve(),flush=True)
    return folder,summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hwnds',nargs='+',type=lambda s:int(s,0))
    p.add_argument('--minutos',type=float,default=30)
    p.add_argument('--intervalo',type=float,default=2)
    p.add_argument('--limite-mb',type=int,default=1024)
    args=p.parse_args()
    from window_capture_engine import WindowCaptureEngine
    engine=WindowCaptureEngine()
    if not args.hwnds:
        windows=engine.locate_target_windows()
        for w in windows:print('HWND:',w['hwnd'],'PID:',w['pid'],'Titulo:',w.get('title'),'Area:',w['client_rect'])
        if not windows:raise SystemExit('Nenhuma janela disponivel. Abra PPPoker e tente novamente.')
        args.hwnds=[int(v,0) for v in input('Digite HWND(s) separados por espacos: ').split()]
        if not set(args.hwnds)<=set(w['hwnd'] for w in windows):raise SystemExit('HWND nao listado')
    from table_reading.pipeline import configure_ocr
    configure_ocr()
    _,summary=run_session(engine,args.hwnds,minutes=args.minutos,interval=args.intervalo,budget_mb=args.limite_mb)
    return 0 if summary['stop_reason'] in ('DURATION_COMPLETE','USER_STOP') else 1

if __name__=='__main__':raise SystemExit(main())
