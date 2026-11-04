"""Real OCR + versioned demonstration policy + an isolated simulated actuator."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile
from time import perf_counter
import cv2
import numpy as np
from visualpilot.agent.laboratory import LaboratoryRangeBook
from visualpilot.pppoker.observer.perception import CachedReader, read_table
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.roi_engine import REGIONS

ROOT = Path(__file__).resolve().parents[2]
STEPS = [
    ('preflop', [], 'call', 2.5, 9.6, 'Pagar a abertura'),
    ('flop', ['7h','As','Ts'], 'check', None, 12.1, 'Passar no flop'),
    ('turn', ['7h','As','Ts','2h'], 'bet', 4., 12.1, 'Apostar no turn'),
    ('river', ['7h','As','Ts','2h','3c'], 'raise', 8., 24.1, 'Aumentar no river'),
    ('river', ['7h','As','Ts','2h','3c'], 'fold', None, 48.1, 'Desistir após nova aposta'),
]


def scenario(index):
    street, board, action, sizing, pot, title = STEPS[index]
    history = [dict(street=s[0],action=s[2],sizing_bb=s[3]) for s in STEPS[:index]]
    state = dict(street=street,hero=['5c','2s'],board=board,position='BTN',
                 effective_stack_bb=30.,pot_bb=pot,action_history=history)
    return dict(index=index,title=title,state=state,action=action,sizing_bb=sizing)


def render_capture(index, obscure=False):
    """Compose calibrated recorded patches into an explicitly synthetic table."""
    spec = scenario(index)
    image = cv2.cvtColor(cv2.imread(str(ROOT/'tests/fixtures/actions/right_99.png')),cv2.COLOR_BGR2RGB)
    if index:
        source = cv2.cvtColor(cv2.imread(str(ROOT/'tests/fixtures/actions/left_99.png')),cv2.COLOR_BGR2RGB)
        y,x,yy,xx = REGIONS['board_flop'][0]
        image[y:yy,x:xx] = source[y:yy,x:xx]
    for street, card, offset in [('turn','2h',0),('river','3c',100)]:
        if len(spec['state']['board']) >= (4 if street=='turn' else 5):
            source=cv2.cvtColor(cv2.imread(str(ROOT/f'tests/fixtures/synthetic_deck/{card}.png')),cv2.COLOR_BGR2RGB)
            y,x,yy,xx=REGIONS['board_turn'][0]
            image[y:yy,x+offset:xx+offset]=source[y:yy,x:xx]
    # The action row belongs to this fictitious scenario, not the recorded game.
    cv2.rectangle(image,(350,535),(515,576),(40,76,133),-1)
    cv2.putText(image,f"Pot: {spec['state']['pot_bb']:.1f} BB",(354,562),
                cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2,cv2.LINE_AA)
    image[1370:1485] = (22,37,55)
    if spec['action'] in ('check','bet'):
        labels=['Fold','Check','Bet 4 BB']
    else:
        labels=['Fold','Call 2.5 BB','Raise 8 BB']
    for i,label in enumerate(labels):
        x=20+i*275
        cv2.rectangle(image,(x,1390),(x+260,1465),[(128,53,65),(30,115,89),(164,119,35)][i],-1)
        size=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,.85,2)[0]
        cv2.putText(image,label,(x+(260-size[0])//2,1437),cv2.FONT_HERSHEY_SIMPLEX,.85,(255,255,255),2,cv2.LINE_AA)
    if obscure:
        y,x,yy,xx=REGIONS['hero_cards'][0]
        image[y:yy,x:xx]=(29,45,61)
    return image


@dataclass
class SimulatedTable:
    generation: int = 1
    actions: list = None

    def __post_init__(self):
        self.actions=[] if self.actions is None else self.actions
        self.executed=set()

    def apply(self, result, buttons):
        """No OS input or network calls: mutation only in this simulator."""
        if result.get('status')!='found':return dict(status='blocked',reason='Leitura ou política pendente.')
        observed=result.get('observation',{})
        if observed.get('table')!='laboratory-table' or observed.get('generation')!=self.generation:
            return dict(status='blocked',reason='Decisão de outra mesa ou geração.')
        if self.generation in self.executed:return dict(status='blocked',reason='Ação já aplicada.')
        options=result.get('options',[])
        if len(options)!=1 or options[0].get('frequency')!=1:
            return dict(status='blocked',reason='Demonstração exige uma única opção explícita.')
        option=options[0]
        if option['action'] not in {b['action'] for b in buttons}:
            return dict(status='blocked',reason='Botão não reconhecido na imagem.')
        if option['action'] in ('call','bet','raise') and not any(
            b['action']==option['action'] and b.get('unit')=='BB' and b.get('amount')==option.get('sizing_bb') for b in buttons):
            return dict(status='blocked',reason='Valor do botão não corresponde à política.')
        self.executed.add(self.generation)
        event=dict(status='applied',target='simulator_only',generation=self.generation,
                   action=option['action'],sizing_bb=option.get('sizing_bb'))
        self.actions.append(event)
        return event


class VisualLaboratory:
    def __init__(self):
        self.reader=CachedReader(ReplayReader())
        entries=[]
        for i in range(len(STEPS)):
            s=scenario(i);option=dict(action=s['action'],frequency=1)
            if s['sizing_bb'] is not None:option['sizing_bb']=s['sizing_bb']
            entries.append(dict(state=s['state'],options=[option]))
        self.policy=dict(schema_version=1,source='visual-lab-script-NOT-trainer-ranges',version='demo-1',entries=entries)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'policy.json';p.write_text(json.dumps(self.policy))
            self.book=LaboratoryRangeBook(p)

    def observe(self,index,obscure=False):
        start=perf_counter();image=render_capture(index,obscure)
        _,png=cv2.imencode('.png',cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
        sha=hashlib.sha256(png.tobytes()).hexdigest()
        reading=read_table(self.reader,image)
        spec=scenario(index);state=spec['state']
        # Ground truth supplies preflop only in this controlled simulation.
        # Preserve the unmodified optical reading alongside the policy input.
        policy_reading=dict(hero=reading.get('hero'),board=reading.get('board'),street=reading.get('street'))
        if index==0 and reading.get('hero')==state['hero'] and reading.get('board')==[]:
            policy_reading['street']='preflop'
        context=dict(state,laboratory=True,fictional=True,
                     observation=dict(table='laboratory-table',generation=index+1,frame_sha256=sha))
        decision=self.book.recommend(policy_reading,context)
        return dict(index=index,title=spec['title'],state=state,reading=reading,
                    decision=decision,observation=context['observation'],
                    context_source='simulator: position, stacks, pot, history and preflop',
                    optical_seconds=round(perf_counter()-start,3),obscured=obscure),png.tobytes()

    def run(self,index,obscure=False):
        event,png=self.observe(index,obscure)
        table=SimulatedTable(index+1)
        event['execution']=table.apply(event['decision'],event['reading'].get('hero_buttons',[]))
        return event,png
