"""One pending frame per table, fair priority, bounded parallel OCR."""
from concurrent.futures import ThreadPoolExecutor,CancelledError
from datetime import datetime
from pathlib import Path
from queue import Queue,Empty
from time import monotonic
import threading
import hashlib
import json
import os
import cv2
import numpy as np
from ..multitable import observe_tables,latest
from ..replay.service import OCRService
from ..roi_engine import frame_signature, region_hashes, REGIONS, scaled_box
from ..scheduler import GenerationBatchConsolidator
from .perception import NORMALIZED_TABLE_WIDTH, action_hint
from .validation import confirmations,validate_latest,confirmation_previous
from .archive import EvidenceArchive,study_record
from .freshness import MAX_SOURCE_AGE, observation, frame_sha256, pending_reading


class Mailbox:
    def __init__(self,limit=6,clock=monotonic):
        self.limit=limit;self.clock=clock;self.lock=threading.Lock();self.pending={};self.served={}
        self.replaced=0;self.overflow=0;self.expired=0;self.highwater=0
        self.remote_epochs={};self.remote_epoch_counter=0

    def set_remote_active(self,active):
        with self.lock:
            self.remote_epochs={k:v for k,v in self.remote_epochs.items() if k in active}
            for key in active:
                if key not in self.remote_epochs:
                    self.remote_epoch_counter+=1
                    self.remote_epochs[key]=self.remote_epoch_counter
            for mapping in (self.pending,self.served):
                for key in list(mapping):
                    if key not in active:mapping.pop(key,None)
            return dict(self.remote_epochs)
    def put(self,item,rgb,stamp=None):
        if rgb.shape[1]>NORMALIZED_TABLE_WIDTH:
            rgb=cv2.resize(rgb,(NORMALIZED_TABLE_WIDTH,round(rgb.shape[0]*NORMALIZED_TABLE_WIDTH/rgb.shape[1])),interpolation=cv2.INTER_CUBIC)
        if rgb.shape[0]>1800:return
        key=item['table_key'];now=self.clock()
        item=dict(item,ingress_observed=now)
        proof=item.get('transport') or {}
        source=proof['not_before_monotonic'] if proof.get('verified') is True else now
        if not 0<=now-source<=MAX_SOURCE_AGE:
            self.expired+=1
            return
        with self.lock:
            if key in self.pending:self.replaced+=1
            elif len(self.pending)>=self.limit:self.overflow+=1;return
            self.served.setdefault(key,now)
            self.pending[key]=(item,rgb.copy(),source,action_hint(rgb))
            self.highwater=max(self.highwater,len(self.pending))
    def take(self,busy=()):
        with self.lock:
            now=self.clock()
            for k in list(self.pending):
                sample=self.pending[k]
                if now-sample[0].get('ingress_observed',sample[2])>3 or now-sample[2]>MAX_SOURCE_AGE:
                    self.pending.pop(k);self.expired+=1
            keys=[k for k in self.pending if k not in busy]
            if not keys:return None
            # Urgency gives a bounded two-second head start; waiting tables age.
            k=max(keys,key=lambda k:now-self.served.get(k,self.pending[k][2])+2*self.pending[k][3])
            self.served[k]=now
            return self.pending.pop(k)
    def retain(self,active):
        with self.lock:
            for mapping in (self.pending,self.served):
                for k in list(mapping):
                    if k not in active:mapping.pop(k,None)


def digest(rgb):
    """Hash exato das regiões que alimentam a leitura publicada."""
    try:
        return frame_signature(rgb)
    except ValueError:
        # Unit fixtures and defensive callers may supply non-table thumbnails.
        top = max(1, round(rgb.shape[0] * .05))
        useful = np.ascontiguousarray(rgb[top:])
        return hashlib.blake2b(useful.tobytes(),digest_size=16).hexdigest()


def evidence_digest(rgb):
    h,w=rgb.shape[:2]
    patches=[rgb[int(h*a):int(h*b),int(w*c):int(w*d)] for a,b,c,d in
             ((.38,.50,.18,.90),(.79,.89,.56,.74),(.93,.99,.02,.98))]
    return hashlib.blake2b(b''.join(p.tobytes() for p in patches),digest_size=16).hexdigest()


class PerceptionSession:
    def __init__(self,root,stop,output,exclusions=lambda:(),workers=None,windows_reader=None,
                 agent_bridge=None,agent_context=lambda table,reading:{},monitor=None):
        self.root=Path(root);self.stop=stop;self.output=output;self.exclusions=exclusions
        self.workers=workers or min(2,max(1,(os.cpu_count() or 2)//2))
        self.windows_reader=windows_reader
        self.monitor=monitor
        self.agent_bridge=agent_bridge;self.agent_context=agent_context
        self.frames=Mailbox();self.captures=Queue(1)
        self.metrics=dict(ocr=0,cached=0,stale=0,errors=0,latencies=[],ocr_latencies=[],cached_latencies=[],tables={},workers=self.workers)
    def run(self,capture=True):
        folder=self.root/datetime.now().strftime('%Y-%m-%d/Sessao_%H%M%S_%f')
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'session.json').write_text(json.dumps(dict(schema_version=1, mode='pppoker_observation_only',
            started_at=datetime.now().astimezone().isoformat(), workers=self.workers,
            layout='portrait_blue_four_colour', source='recovered-perception-consolidated-dev4'), indent=2), encoding='utf-8')
        latest(self.output, dict(kind='started', folder=str(folder)))
        archive=EvidenceArchive(folder)
        if self.monitor:self.monitor.start(folder)
        services=[OCRService(timeout=15) for _ in range(self.workers)]
        slots={};jobs=[];cache={};scheduled={};latest_samples={};roi_states={};generations={}
        previous={};previous_times={};lastrecord={};active=None;epochs={};error=None;thread=None
        consolidator=GenerationBatchConsolidator()
        executor=ThreadPoolExecutor(max_workers=self.workers)
        self.metrics['latency_semantics']='v2: conservative ticket-to-publication capture-age bound; legacy: ingress-only'
        def emit(e):latest(self.output,e)
        def execute(service,job):
            started=monotonic()
            try:
                if job['kind']=='card':
                    return service.read_cards(job['key'],job['generation'],job['region'],job['image'],self.stop)
                return service.call('perception',job['sample'][1],self.stop)
            finally:
                job['timing']=dict(job_kind=job['kind'],region=job.get('region'),queue_seconds=max(0.,started-job['queued_at']),
                                   processing_seconds=max(0.,monotonic()-started))
        def reject(job,reason):
            counts=self.metrics.setdefault('discarded_results',{})
            counts[reason]=counts.get(reason,0)+1
            record=dict(at=datetime.now().astimezone().isoformat(),reason=reason,
                        job_kind=job['kind'],region=job.get('region'),
                        observation=job['observation'],timing=job.get('timing',{}),
                        source_age_seconds=max(0.,monotonic()-job['sample'][2]))
            with (folder/'rejeicoes.jsonl').open('a',encoding='utf-8') as rejected:
                rejected.write(json.dumps(record,ensure_ascii=False)+'\n')
        def reject_reason(job):
            key=job['key']
            if ((active is not None and key not in active) or job['epoch']!=epochs.get(key,0)):
                return 'retired_table'
            if job['generation']!=generations.get(key):return 'superseded_generation'
            if monotonic()-job['sample'][2]>MAX_SOURCE_AGE:return 'expired_source'
            # Check the mailbox too: it may contain a newer capture which has not
            # yet advanced the scheduler generation in this iteration.
            with self.frames.lock:pending=self.frames.pending.get(key)
            if pending is not None and digest(pending[1])!=job['hashed']:
                return 'newer_frame_pending'
            return None
        def emit_current(payload,sample,job):
            # Publication and mailbox ingress share a short critical section:
            # a capture already received cannot slip between validation and emit.
            reason=None
            with self.frames.lock:
                pending=self.frames.pending.get(job['key'])
                remote_epoch=job['sample'][0].get('remote_epoch')
                if self.stop.is_set():reason='stopped_before_publication'
                elif remote_epoch is not None and self.frames.remote_epochs.get(job['key'])!=remote_epoch:
                    reason='retired_remote_table'
                elif monotonic()-sample[2]>MAX_SOURCE_AGE:reason='expired_source'
                elif pending is not None and digest(pending[1])!=job['hashed']:
                    reason='newer_frame_pending'
                if reason is None:
                    if remote_epoch is not None:payload['remote_epoch']=remote_epoch
                    emit(payload)
                    # Keep retirement and monitor publication ordered by the
                    # same lock; a late OCR result must not recreate a preview.
                    if self.monitor and payload.get('kind')=='reading':
                        self.monitor.observe(payload,sample[1])
            if reason:reject(job,reason)
            return reason is None
        try:
            # Model loading begins alongside table discovery, instead of delaying
            # the first table submitted to each worker.
            warmup_started=monotonic()
            for service in services:
                starter=getattr(service,'start',None)
                if starter:starter()
            self.metrics['warmup_start_seconds']=round(monotonic()-warmup_started,4)
            with (folder/'percepcao.jsonl').open('a',encoding='utf-8') as journal:
                if capture:
                    observer_options=dict(interval=.5,frame_sink=self.frames.put,max_tables=6)
                    if self.windows_reader is not None:
                        observer_options['windows_reader']=self.windows_reader
                    thread=threading.Thread(target=observe_tables,daemon=True,args=(self.root/'Observacao',self.stop,self.captures,self.exclusions),kwargs=observer_options);thread.start()
                def publish(sample,reading,cached=False,raw_reading=None,job=None):
                    raw_reading = reading if raw_reading is None else raw_reading
                    identity=job['observation']
                    validation=observation(sample,identity['generation'],identity['epoch'])
                    timing=dict(job.get('timing',{}),source_age_seconds=max(0.,monotonic()-identity['source_observed']))
                    item,rgb,stamp,hint=sample;key=item['table_key'];age=monotonic()-stamp
                    published_at=datetime.now().astimezone()
                    tm=self.metrics['tables'].setdefault(key,dict(published=0,cached=0,expired=0))
                    tm['published']+=1;tm['cached']+=int(cached);tm['last_age_seconds']=round(age,3)
                    if age>MAX_SOURCE_AGE:
                        self.metrics['stale']+=1;tm['expired']+=1;reading=dict(status='pending',reason='Leitura expirada.',hero=[],board=[],street=None)
                    prior=confirmation_previous(reading,previous.get(key),stamp,previous_times.get(key,-100))
                    fields=confirmations(reading,prior)
                    previous_times[key]=stamp
                    stable=fields['hero']['confirmed'] and (fields['board']['confirmed'] or fields['board']['state']=='not_dealt')
                    previous[key]=reading
                    coverage=self.metrics.setdefault('coverage',dict(published=0,hero_read=0,board_read=0,street_unknown=0,hero_confirmed=0,board_confirmed=0))
                    coverage['published']+=1
                    coverage['hero_read']+=int(len(reading.get('hero',[]))==2)
                    coverage['board_read']+=int(len(reading.get('board',[])) in (3,4,5))
                    coverage['street_unknown']+=int(reading.get('street') is None)
                    coverage['hero_confirmed']+=int(fields['hero']['confirmed'])
                    coverage['board_confirmed']+=int(fields['board']['confirmed'])
                    series='cached_latencies' if cached else 'ocr_latencies'
                    self.metrics[series].append(round(age,4));self.metrics[series]=self.metrics[series][-2000:]
                    self.metrics['latencies'].append(round(age,4));self.metrics['latencies']=self.metrics['latencies'][-2000:]
                    payload=dict(kind='reading',table=key,number=item['number'],reading=reading,confirmed=stable,field_confirmation=fields,observed=stamp,latency=age,cached=cached,generation=identity['generation'],
                              observation=identity,validation=validation,timing=timing,action_authorized=False)
                    if not emit_current(payload,sample,job):return
                    record=dict(table=key,reading=reading,confirmed=stable,field_confirmation=fields)
                    encoded=json.dumps(dict(record,raw_reading=raw_reading,generation=identity['generation']),sort_keys=True,ensure_ascii=False)
                    if lastrecord.get(key)!=encoded:
                        evidence=archive.save(key,rgb,stamp)
                        entry=study_record(record,raw_reading,evidence,age,now=published_at)
                        entry.update(cached=cached,observation=identity,validation=validation,timing=timing,
                                     validated_observed=stamp,validated_frame_sha256=frame_sha256(rgb),
                                     action_authorized=False)
                        journal.write(json.dumps(entry,ensure_ascii=False)+'\n');journal.flush();lastrecord[key]=encoded
                        if self.agent_bridge is not None:
                            snapshot=dict(table=key,hand_id=reading.get('hand_id'),
                                          observation=identity,timing=timing,action_authorized=False,
                                          hero_cards=reading.get('hero',[]),
                                          board_cards=reading.get('board',[]))
                            context=self.agent_context(key,reading) or {}
                            snapshot=dict(context.get('snapshot') or {},**snapshot)
                            self.agent_bridge.snapshot_consolidated(snapshot,context)
                def publish_partial(event,sample,job):
                    item,rgb,stamp,hint=sample;key=item['table_key']
                    regions=event['cards']
                    def values(name):
                        reading=regions.get(name) or {}
                        if reading.get('status')!='SUCCESS':return []
                        return [card['card'] for card in reading.get('cards',[])]
                    hero=values('hero_cards')
                    board=values('board_flop')+values('board_turn')+values('board_river')
                    street={3:'flop',4:'turn',5:'river'}.get(len(board))
                    reading=dict(status='partial',hero=hero,board=board,street=street,
                                 hand_id=None,actions=[],observed_actions=[],pot=None,
                                 hero_stack=None,reason='Campos textuais em processamento.',
                                 source='specialized_card_regions')
                    age=monotonic()-stamp
                    identity=job['observation']
                    timing=dict(job.get('timing',{}),source_age_seconds=age)
                    fields={
                        'hero':dict(state='observed' if len(hero)==2 else 'pending',confirmed=False),
                        'board':dict(state='observed' if street else 'pending',confirmed=False),
                    }
                    payload=dict(kind='partial_cards',table=key,number=item['number'],
                                 generation=event['generation'],reading=reading,
                                 field_confirmation=fields,confirmed=False,observed=stamp,
                                 latency=age,cached=False,observation=identity,timing=timing,
                                 hand_identity_verified=False,action_authorized=False)
                    if not emit_current(payload,sample,job):return
                    if self.agent_bridge is not None:
                        context=self.agent_context(key,reading) or {}
                        self.agent_bridge.partial_cards_ready(payload,context)
                    record=dict(table=key,reading=reading,confirmed=False,
                                field_confirmation=fields)
                    entry=study_record(record,reading,dict(status='deferred',path=None),age)
                    entry.update(schema_version=3,event='PARTIAL_CARDS_READY',
                                 generation=event['generation'],regions=regions,
                                 observation=identity,timing=timing,action_authorized=False)
                    journal.write(json.dumps(entry,ensure_ascii=False)+'\n');journal.flush()
                    self.metrics['partial_cards']=self.metrics.get('partial_cards',0)+1
                while not self.stop.is_set():
                    try:status=self.captures.get_nowait()
                    except Empty:status=None
                    if status is not None:
                        if status.get('finished'):
                            if status.get('error'):raise RuntimeError(status['error'])
                            break
                        newactive={x['table_key'] for x in status['tables'] if x['state']=='capturando'}
                        if active is not None:
                            for k in active-newactive:
                                epochs[k]=epochs.get(k,0)+1
                                for m in (cache,scheduled,latest_samples,roi_states,generations,previous,previous_times,lastrecord):m.pop(k,None)
                                consolidator.remove_table(k)
                                if self.agent_bridge is not None:
                                    self.agent_bridge.retire_table(k)
                                jobs[:]=[job for job in jobs if job['key']!=k]
                        active=newactive;self.frames.retain(active);emit(dict(kind='tables',value=status))
                    for index,slot in list(slots.items()):
                        future=slot['future'];sample=slot['sample'];hashed=slot['hashed'];epoch=slot['epoch'];job=slot['job']
                        if not future.done():continue
                        del slots[index];key=sample[0]['table_key']
                        try:result=future.result()
                        except Exception as exc:
                            if self.stop.is_set() and isinstance(exc,(InterruptedError,CancelledError)):
                                self.metrics['cancelled_on_stop']=self.metrics.get('cancelled_on_stop',0)+1
                                break
                            self.metrics['errors']+=1
                            if self.metrics['errors'] <= 1000:
                                # Preserve the actual failure even if freshness
                                # subsequently rejects this job's result.
                                with (folder/'erros_ocr.jsonl').open('a', encoding='utf-8') as errors:
                                    errors.write(json.dumps(dict(at=datetime.now().astimezone().isoformat(),
                                        table=key, generation=job.get('generation'),
                                        job_kind=job['kind'], region=job.get('region'),
                                        error_type=type(exc).__name__, error=str(exc)[:2000]),
                                        ensure_ascii=False)+'\n')
                            if job['kind']=='card':
                                result=dict(kind='card_region',table_key=key,generation=job['generation'],
                                            region=job['region'],reading=dict(status='PENDING',cards=[],reason=str(exc)))
                            else:result=dict(status='pending',reason=str(exc),hero=[],board=[],street=None)
                        if self.stop.is_set():break
                        reason=reject_reason(job)
                        if reason:
                            reject(job,reason)
                            if reason=='expired_source' and generations.get(key)==job['generation']:
                                scheduled.pop(key,None)
                                jobs[:]=[queued for queued in jobs if queued['key']!=key]
                            continue
                        if job['kind']=='card':
                            self.metrics['card_region_ocr']=self.metrics.get('card_region_ocr',0)+1
                            if any(result.get(field)!=job[field] for field in ('generation','region')) or result.get('table_key')!=key:
                                reject(job,'mismatched_result_identity');continue
                            for event in consolidator.inject_card_result(result):
                                if event['stage']=='PARTIAL_CARDS':publish_partial(event,sample,job)
                            continue
                        reading=result;self.metrics['ocr']+=1;raw_reading=reading
                        # Do not expose an old result after the relevant screen changed.
                        with self.frames.lock:pending=self.frames.pending.get(key)
                        if pending is not None:
                            reading=validate_latest(reading,sample[1],pending[1])
                            if reading.get('invalidated_fields'):
                                self.metrics['field_invalidations']=self.metrics.get('field_invalidations',0)+1
                        reusable = (reading.get('hero') or reading.get('board') or
                                    reading.get('actions') or reading.get('observed_actions') or
                                    reading.get('hand_id') or reading.get('pot') or
                                    reading.get('hero_stack'))
                        if reusable and not reading.get('invalidated_fields') and monotonic()-sample[2]<=5:
                            cache[key]=(hashed,reading,0,job)
                        consolidator.inject_text_result(key,job['generation'],reading)
                        publish(sample,reading,raw_reading=raw_reading,job=job)
                    # Convert every newest table frame into generation-bound jobs
                    # before filling workers, so cards from all tables share priority.
                    for _ in range(6):
                        sample=self.frames.take()
                        if sample is None:break
                        key=sample[0]['table_key'];hashed=digest(sample[1])
                        latest_samples[key]=(hashed,sample)
                        if key in cache and cache[key][3]['observation']['frame_sha256']!=frame_sha256(sample[1]):
                            cache.pop(key,None);scheduled.pop(key,None)
                        if key in cache and cache[key][0]==hashed:
                            cached_reading=cache[key][1]
                            if cache[key][2]<20:
                                cache[key]=(hashed,cached_reading,cache[key][2]+1,cache[key][3])
                                self.metrics['cached']+=1;publish(sample,cached_reading,True,job=cache[key][3]);continue
                            cache.pop(key,None);scheduled.pop(key,None)
                            self.metrics['cache_revalidations']=self.metrics.get('cache_revalidations',0)+1
                        if scheduled.get(key)==hashed:
                            continue
                        generations[key]=generations.get(key,0)+1;generation=generations[key]
                        if self.agent_bridge is not None:
                            self.agent_bridge.advance(key,generation,epochs.get(key,0))
                        if generation>1:
                            invalidated=dict(kind='reading_invalidated',table=key,number=sample[0]['number'],
                                             generation=generation,observed=sample[2],confirmed=False,
                                             reading=pending_reading('Nova imagem recebida; aguardando leitura atualizada.'),
                                             field_confirmation={},action_authorized=False,
                                             remote_epoch=sample[0].get('remote_epoch'))
                            emit(invalidated)
                            if self.monitor:self.monitor.invalidate(key,'new_generation')
                        card_regions=[]
                        try:
                            hashes=region_hashes(sample[1])
                            # Uma publicação parcial é um snapshot completo das cartas.
                            # Não tratar regiões não agendadas como cartas ausentes,
                            # nem reutilizar resultados de uma geração cancelada.
                            # Frames idênticos continuam usando scheduled/cache acima.
                            card_regions = ['hero_cards','board_flop','board_turn','board_river']
                            roi_states[key]=hashes
                        except ValueError:
                            pass
                        consolidator.register_capture(key,generation,card_regions,expect_text=True)
                        jobs[:]=[job for job in jobs if job['key']!=key]
                        for region in card_regions:
                            y1,x1,y2,x2=scaled_box(REGIONS[region][0],sample[1].shape[1],sample[1].shape[0])
                            jobs.append(dict(priority=0,kind='card',key=key,generation=generation,
                                             queued_at=monotonic(),region=region,image=sample[1][y1:y2,x1:x2].copy(),
                                             sample=sample,hashed=hashed,epoch=epochs.get(key,0)))
                        jobs.append(dict(priority=1,kind='text',key=key,generation=generation,
                                         sample=sample,hashed=hashed,epoch=epochs.get(key,0),queued_at=monotonic()))
                        scheduled[key]=hashed
                    jobs.sort(key=lambda job:job['priority'])
                    for index in range(self.workers):
                        if index in slots:continue
                        if not jobs:continue
                        job=jobs.pop(0);sample=job['sample'];key=job['key']
                        if job['generation']!=generations.get(key):continue
                        job.setdefault('queued_at',sample[2])
                        job['observation']=observation(sample,job['generation'],job['epoch'])
                        reason=reject_reason(job)
                        if reason:
                            reject(job,reason)
                            if reason=='expired_source':scheduled.pop(key,None)
                            continue
                        future=executor.submit(execute,services[index],job)
                        slots[index]=dict(future=future,sample=sample,hashed=job['hashed'],
                                          epoch=job['epoch'],job=job)
                    self.stop.wait(.02)
        except Exception as exc:error=str(exc)
        finally:
            self.stop.set();executor.shutdown(wait=True,cancel_futures=True)
            for service in services:service.close()
            if thread:thread.join(timeout=7)
            self.metrics.update(evidence_images=archive.count,evidence_bytes=archive.bytes,evidence_limit_bytes=archive.max_bytes)
            self.metrics.update(replaced=self.frames.replaced,overflow=self.frames.overflow,expired=self.frames.expired,highwater=self.frames.highwater)
            (folder/'metricas.json').write_text(json.dumps(self.metrics,indent=2),encoding='utf-8')
            emit(dict(kind='finished',error=error,folder=str(folder),metrics=self.metrics))
