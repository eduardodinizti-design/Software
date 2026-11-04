"""Loopback-only visual simulator; no OS clicks, remote control, or game client."""
import argparse
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
import threading
from time import monotonic
import uuid
import webbrowser
from .engine import VisualLaboratory, SimulatedTable
from visualpilot.pppoker.observer.freshness import MAX_SOURCE_AGE

class LaboratorySession:
    def __init__(self,root='sessions/laboratory',engine=None):
        self.engine=engine or VisualLaboratory();self.lock=threading.Lock();self.current=None
        self.ocr_lock=threading.Lock()
        self.clock=monotonic;self.current_observed=None
        self.mode='automatic';self.revision=0;self.capture_revision=0
        self.resolved=set()
        self.folder=Path(root)/(datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
        self.folder.mkdir(parents=True)

    def record(self,kind,event):
        with (self.folder/'events.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),kind=kind,**event),ensure_ascii=False)+'\n')

    def control(self,mode,reset=False):
        if mode not in ('automatic','manual','paused') or type(reset) is not bool:
            raise ValueError('Modo inválido')
        with self.lock:
            self.mode=mode;self.revision+=1;self.current=None
            self.current_observed=None
            if reset:self.resolved.clear()
            event=dict(mode=mode,revision=self.revision,reset=reset,resolved_scenarios=sorted(self.resolved))
            self.record('control',event)
            return event

    def observe(self,index,obscure,revision=None):
        if type(index) is not int or not 0<=index<5 or type(obscure) is not bool:
            raise ValueError('Cenário inválido')
        with self.lock:
            if self.mode=='paused' or (revision is not None and revision!=self.revision):
                return dict(status='cancelled',reason='Controle alterado.')
            started_revision=self.revision
            self.capture_revision+=1;capture_revision=self.capture_revision
            self.current=None;self.current_observed=None
            captured_at=self.clock()
        # OCR must not hold the control lock: taking over cancels its result.
        try:
            with self.ocr_lock:
                with self.lock:
                    if started_revision!=self.revision or capture_revision!=self.capture_revision:
                        return dict(status='cancelled',reason='Captura substituída antes do OCR.')
                event,png=self.engine.observe(index,obscure)
        except Exception as exc:
            with self.lock:
                self.record('capture_failed',dict(index=index,revision=started_revision,
                    error_type=type(exc).__name__,error=str(exc)[:2000]))
            return dict(status='failed',reason='Falha de leitura; nenhuma ação foi liberada. Faça uma nova captura.')
        with self.lock:
            if started_revision!=self.revision or capture_revision!=self.capture_revision:
                self.record('capture_cancelled',dict(index=index,revision=started_revision))
                return dict(status='cancelled',reason='Captura anterior à troca de controle.')
            age=self.clock()-captured_at
            if not 0<=age<=MAX_SOURCE_AGE:
                self.record('capture_cancelled',dict(index=index,reason='expired_source',age_seconds=age))
                return dict(status='cancelled',reason='A leitura venceu durante o processamento. Faça uma nova captura.')
            identity=event.get('observation')
            if not isinstance(identity,dict) or identity.get('frame_sha256')!=hashlib.sha256(png).hexdigest():
                self.record('capture_failed',dict(index=index,error_type='ImageIdentityMismatch'))
                return dict(status='failed',reason='A leitura não corresponde à imagem recebida. Faça uma nova captura.')
            token=uuid.uuid4().hex
            self.current=(token,event,SimulatedTable(index+1))
            self.current_observed=captured_at
            (self.folder/(token+'.png')).write_bytes(png)
            self.record('observation',dict(event,token=token,evidence=token+'.png'))
            return dict(event,token=token,revision=self.revision,image='data:image/png;base64,'+base64.b64encode(png).decode())

    def apply(self,token,actor='engine',action=None):
        with self.lock:
            if (actor not in ('engine','human') or self.mode=='paused'
                    or (actor=='engine')!=(self.mode=='automatic')):
                return dict(status='blocked',reason='Modo de controle não permite esta ação.')
            if not self.current or token!=self.current[0]:
                return dict(status='blocked',reason='Captura substituída ou sessão inválida.')
            age=self.clock()-self.current_observed
            if not 0<=age<=MAX_SOURCE_AGE:
                self.current=None;self.current_observed=None
                outcome=dict(status='blocked',reason='Leitura expirada. Retome com uma nova captura.',
                             cause='expired_source',age_seconds=age,actor=actor)
                self.record('simulated_action',dict(outcome,token=token))
                return outcome
            _,event,table=self.current
            if event['index'] in self.resolved:
                return dict(status='blocked',reason='Cenário já resolvido; avance ou reinicie.')
            buttons=event['reading'].get('hero_buttons',[])
            decision=event['decision']
            if actor=='engine' and decision.get('status')=='found':
                identity=event.get('observation',{})
                reference=decision.get('observation')
                if not isinstance(reference,dict) or any(identity.get(field) is None or reference.get(field)!=identity[field]
                       for field in ('table','generation','frame_sha256')):
                    outcome=dict(status='blocked',reason='Decisão não corresponde à imagem atual.',
                                 cause='observation_conflict',actor=actor)
                    self.record('simulated_action',dict(outcome,token=token))
                    return outcome
            if actor=='human':
                button=next((b for b in buttons if b['action']==action),None)
                if button is None:return dict(status='blocked',reason='Botão indisponível.')
                decision=dict(status='found',observation=event['observation'],options=[dict(
                    action=action,frequency=1,sizing_bb=button.get('amount'))])
            outcome=table.apply(decision,buttons)
            outcome.update(actor=actor,mode=self.mode,revision=self.revision)
            if event.get('grades'):
                outcome['grade']=event['grades'].get(outcome.get('action'))
            if outcome['status']=='applied':self.resolved.add(event['index'])
            self.record('simulated_action',dict(outcome,token=token,observation=event['observation']))
            return outcome

    def answer(self,token,action):
        with self.lock:
            if self.mode!='manual' or not self.current or token!=self.current[0]:
                return dict(status='blocked',reason='Assuma o controle e obtenha uma leitura atual.')
            _,event,_=self.current
            grade=event.get('grades',{}).get(action)
            if grade is None:return dict(status='blocked',reason='Ação não pertence ao nó NVT.')
            outcome=dict(status='evaluated',action=action,actor='human',executed=False,
                         grade=grade,observation=event['observation'],revision=self.revision)
            self.record('manual_answer',dict(outcome,token=token))
            return outcome


def create_server(port=8765,root='sessions/laboratory',engine=None):
    session=LaboratorySession(root,engine)
    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,payload,content='application/json; charset=utf-8'):
            raw=payload if isinstance(payload,bytes) else json.dumps(payload,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',content)
            self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if self.path in ('/','/index.html'):
                page=Path(__file__).with_name('simulator.html').read_text(encoding='utf-8')
                page=page.replace('/*LAB_CONTROLLER*/',Path(__file__).with_name('controller.js').read_text(encoding='utf-8'))
                page=page.replace('/*LAB_CONFIG*/','window.LAB_CONFIG='+json.dumps(getattr(session.engine,'metadata',{})).replace('</','<\\/')+';')
                self.reply(200,page.encode(),'text/html; charset=utf-8')
            elif self.path=='/health':self.reply(200,dict(status='ok',mode='laboratory'))
            else:self.reply(404,dict(error='Não encontrado'))
        def do_POST(self):
            # Only same-origin JSON requests from the local simulator.
            origin=self.headers.get('Origin')
            expected=f'http://{self.headers.get("Host")}'
            if origin and origin!=expected:
                self.reply(403,dict(error='Origem inválida'));return
            try:
                if self.headers.get('Content-Type')!='application/json':raise ValueError('JSON obrigatório')
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<4096:raise ValueError('Corpo inválido')
                body=json.loads(self.rfile.read(size))
                if self.path=='/api/observe':result=session.observe(body['index'],body.get('obscure',False),body.get('revision'))
                elif self.path=='/api/apply':result=session.apply(body['token'],body.get('actor','engine'),body.get('action'))
                elif self.path=='/api/control':result=session.control(body['mode'],body.get('reset',False))
                elif self.path=='/api/answer':result=session.answer(body['token'],body['action'])
                else:self.reply(404,dict(error='Não encontrado'));return
                self.reply(200,result)
            except (ValueError,KeyError,TypeError) as exc:self.reply(400,dict(error=str(exc)))
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.lab_session=session
    return server


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--nvt-ranges',help='Pacote nvt-ranges-validados.json para o laboratório pré-flop')
    parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    engine=None
    if args.nvt_ranges:
        from .nvt_engine import NvtVisualLaboratory
        engine=NvtVisualLaboratory(args.nvt_ranges)
    server=create_server(args.port,engine=engine);url=f'http://127.0.0.1:{server.server_port}'
    print('Laboratório VisualPilot: '+url,flush=True)
    print('Registros: '+str(server.lab_session.folder),flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
