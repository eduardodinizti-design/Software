"""Bounded live previews and observational timelines; never execute game actions."""
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from time import monotonic
import json
import cv2
from visualpilot.pppoker.observer.archive import EvidenceArchive


class LiveMonitor:
    def __init__(self, clock=monotonic):
        self.clock=clock; self.lock=RLock(); self.tables={}; self.folder=None
        self.archive=None; self.log_bytes=0; self.log_limit=32*1024*1024
        self.error=None

    def start(self, folder):
        with self.lock:
            self.folder=Path(folder)/'acompanhamento';self.folder.mkdir(parents=True,exist_ok=True)
            self.archive=EvidenceArchive(self.folder,interval=2,max_bytes=64*1024*1024)

    def retain(self, keys):
        with self.lock:
            self.tables={k:v for k,v in self.tables.items() if k in keys}

    def _table(self,key,number=None):
        if key not in self.tables:
            if len(self.tables)>=6:return None
            self.tables[key]=dict(number=number,events=deque(maxlen=30),window=None,last_observed=-1)
        return self.tables[key]

    def frame(self,key,number,rgb):
        now=self.clock()
        with self.lock:
            row=self._table(key,number)
            if row is None:return
            row['received']=now;row['received_at']=datetime.now(timezone.utc).isoformat()
            if now-row.get('preview_stamp',-1e9)<.5:return
            image=rgb
            if rgb.shape[1]>500:
                image=cv2.resize(rgb,(500,round(rgb.shape[0]*500/rgb.shape[1])))
            ok,data=cv2.imencode('.jpg',cv2.cvtColor(image,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,80])
            if ok:row.update(preview=data.tobytes(),preview_stamp=now)

    def _record(self,key,row,event):
        event=dict(event,table=key,at=datetime.now(timezone.utc).isoformat())
        row['events'].append(event)
        if self.folder:
            encoded=json.dumps(event,ensure_ascii=False)+'\n'
            if self.log_bytes+len(encoded.encode())>self.log_limit:
                self.error='Limite do diário de acompanhamento atingido.';return
            try:
                with (self.folder/'eventos.jsonl').open('a',encoding='utf-8') as f:f.write(encoded)
                self.log_bytes+=len(encoded.encode())
            except OSError as exc:self.error=f'Falha ao salvar acompanhamento: {exc}'

    def observe(self,event,rgb):
        with self.lock:
            key=event['table'];row=self._table(key,event.get('number'))
            if row is None:return
            stamp=event['observed']
            if stamp<=row['last_observed']:return
            previous=row['last_observed'];row['last_observed']=stamp
            reading=deepcopy(event['reading']);hand=reading.get('hand_id')
            buttons=reading.get('hero_buttons') or reading.get('actions') or []
            invalid=set(reading.get('invalidated_fields',[]))
            uncertain=(reading.get('status') == 'pending' or
                       (reading.get('status') == 'partial' and not buttons) or bool(invalid))
            context=(tuple(reading.get('hero') or []),tuple(reading.get('board') or []),reading.get('street'))
            window=row['window'];boundary=(stamp-previous>5 or hand!=row.get('hand_id') or context!=row.get('context'))
            if window and (boundary or uncertain):
                self._record(key,row,dict(kind='interval_cancelled',reason='gap_hand_change_or_uncertain_reading'))
                row['window']=None;window=None
            if buttons and not uncertain and window is None:
                row['window']=dict(start=stamp,buttons=deepcopy(buttons))
                self._record(key,row,dict(kind='buttons_visible',observed=stamp,buttons=buttons))
            elif not buttons and window and not uncertain:
                self._record(key,row,dict(kind='buttons_hidden',observed=stamp,
                    seconds=round(stamp-window['start'],3),action_verified=False,
                    meaning='Intervalo observado; não confirma ação nem tempo exato de decisão.'))
                row['window']=None
            row.update(hand_id=hand,context=context,reading=reading,latency=event.get('latency'))
            # Sample the exact image used for this reading, never the newer preview.
            if self.archive and stamp-row.get('saved_stamp',-1e9)>=2:
                evidence=self.archive.save(key,rgb,stamp);row['saved_stamp']=stamp
                self._record(key,row,dict(kind='reading_sample',observed=stamp,
                    reading=reading,evidence=evidence,latency=event.get('latency'),
                    observation=event.get('observation'),timing=event.get('timing')))
                if evidence['status'] in ('limit_reached','error'):
                    self.error='Evidências limitadas ou indisponíveis; consulte o diário.'

    def invalidate(self,key,reason):
        with self.lock:
            row=self.tables.get(key)
            if not row:return
            row['window']=None
            row['reading']=dict(status='pending',hero=[],board=[],street=None,
                                reason='Aguardando leitura da nova imagem.')
            self._record(key,row,dict(kind='reading_invalidated',reason=reason))

    def mark(self,key):
        with self.lock:
            row=self.tables.get(key)
            if not row:return
            now=self.clock()
            self._record(key,row,dict(kind='manual_review_marker',observed=now,
                seconds_since_buttons=round(now-row['window']['start'],3) if row['window'] and now-row.get('received',-1e9)<=5 else None,
                action_verified=False,meaning='Marcação manual para revisão; não executa jogada.'))

    def snapshot(self):
        with self.lock:
            now=self.clock();result={}
            for key,row in self.tables.items():
                copy=deepcopy(row);copy['events']=list(copy['events'])
                copy['frame_age']=max(0,now-row['received']) if 'received' in row else None
                copy['preview_age']=max(0,now-row['preview_stamp']) if 'preview_stamp' in row else None
                copy['reading_age']=max(0,now-row['last_observed']) if row['last_observed']>=0 else None
                fresh=copy['frame_age'] is not None and copy['frame_age']<=5 and copy['reading_age'] is not None and copy['reading_age']<=5
                copy['button_seconds']=max(0,now-row['window']['start']) if row['window'] and fresh else None
                result[key]=copy
            return result
