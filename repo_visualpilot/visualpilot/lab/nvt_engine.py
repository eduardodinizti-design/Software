"""Preflop-only visual lab backed by the user's validated NVT export."""
import hashlib
from pathlib import Path
from time import perf_counter
import cv2
from visualpilot.agent.nvt_ranges import NvtRangeBook
from visualpilot.pppoker.observer.perception import CachedReader,read_table
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.roi_engine import REGIONS
from .engine import ROOT,SimulatedTable

CASES=[
    ('heldout_cards/15_0.png',['7d','3s'],'vs_open','BB',['BTN'],'Defesa no BB · fold'),
    ('heldout_cards/48_0.png',['8h','Jd'],'vs_open','BB',['BTN'],'Defesa no BB · call'),
    ('actions/right_99.png',['5c','2s'],'vs_open','BB',['BTN'],'Defesa no BB · estratégia mista'),
    ('heldout_cards/15_1.png',['Kd','Js'],'open_raise','BTN',[],'Abertura no BTN · sizing pendente'),
    ('heldout_cards/48_0.png',['8h','Jd'],'vs_limp','BB',[],'BB contra limp · check'),
]

def choose_mix(result,seed):
    """Reproducible weighted draw; never reroll an unexecutable recommendation."""
    if result.get('status')!='found':return None
    mix=result['mix'];total=sum(m['frequency'] for m in mix)
    if not mix or abs(total-1)>.002:return None
    draw=int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8],'big')/2**64
    cumulative=0.
    for option in mix:
        cumulative+=option['frequency']/total
        if draw<cumulative:return dict(action=option['action'],draw=draw,seed=seed,frequency_sum=total)
    return dict(action=mix[-1]['action'],draw=draw,seed=seed,frequency_sum=total)

class NvtVisualLaboratory:
    is_nvt=True
    def __init__(self,path):
        self.book=NvtRangeBook(path);self.reader=CachedReader(ReplayReader())
        self.metadata=dict(nvt=True,policy='NVT pré-flop',engine_commit=self.book.provenance['engine_commit'])

    def spec(self,index):
        file,hero,spot,position,vs,title=CASES[index]
        context=dict(mode='chip_ev',stack=25,stage='mid',players=9,position=position,spot=spot,vs=vs)
        node=self.book.nodes.get(('chip_ev',25,'mid',9,spot,position,tuple(vs),None))
        if node is None:raise ValueError('Pacote não contém o nó validado do cenário: '+spot)
        state=dict(hero=hero,board=[],street='preflop',position=position,effective_stack_bb=25,
                   pot_bb=node['table']['potBb'],action_history=node['table']['actions'],players=9,
                   table_stacks=node['table']['stacks'])
        # Call is the amount due in this defined scenario, not a raise sizing.
        buttons=[('fold','Fold')] if spot in ('vs_open','open_raise') else [('check','Check')]
        if spot=='vs_open':
            raises=[a for a in node['table']['actions'] if a['type']=='raise']
            posted=sum(a['amount'] for a in node['table']['actions']
                       if a['position']==position and a['type'] in ('post_bb','post_sb'))
            if len(raises)==1 and raises[0]['amount']>posted:
                due=raises[0]['amount']-posted
                buttons.append(('call',f'Call {due:g} BB'))
        return dict(file=file,title=title,context=context,state=state,node=node,buttons=buttons)

    def capture(self,index,obscure):
        spec=self.spec(index)
        image=cv2.cvtColor(cv2.imread(str(ROOT/'tests/fixtures/actions/right_99.png')),cv2.COLOR_BGR2RGB)
        source=cv2.cvtColor(cv2.imread(str(ROOT/'tests/fixtures'/spec['file'])),cv2.COLOR_BGR2RGB)
        y,x,yy,xx=REGIONS['hero_cards'][0];image[y:yy,x:xx]=source[y:yy,x:xx]
        if obscure:image[y:yy,x:xx]=(29,45,61)
        cv2.rectangle(image,(350,535),(515,576),(40,76,133),-1)
        cv2.putText(image,f"Pot: {spec['state']['pot_bb']:.1f} BB",(354,562),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2,cv2.LINE_AA)
        image[1370:1485]=(22,37,55)
        for i,(_,label) in enumerate(spec['buttons']):
            x=20+i*275;cv2.rectangle(image,(x,1390),(x+260,1465),[(128,53,65),(30,115,89)][i],-1)
            w=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,.85,2)[0][0]
            cv2.putText(image,label,(x+(260-w)//2,1437),cv2.FONT_HERSHEY_SIMPLEX,.85,(255,255,255),2,cv2.LINE_AA)
        return spec,image

    def observe(self,index,obscure=False):
        start=perf_counter();spec,image=self.capture(index,obscure)
        _,png=cv2.imencode('.png',cv2.cvtColor(image,cv2.COLOR_RGB2BGR));png=png.tobytes()
        obs=dict(table='laboratory-table',generation=index+1,frame_sha256=hashlib.sha256(png).hexdigest())
        reading=read_table(self.reader,image)
        policy_reading=dict(hero=reading.get('hero',[]),board=reading.get('board',[]),street='preflop' if not reading.get('board') else reading.get('street'))
        result=self.book.recommend(policy_reading,spec['context'])
        seed=f"{self.book.provenance['package_sha256']}:lab-seed-42:case-{index}"
        selected=choose_mix(result,seed)
        decision=dict(status='pending',reason=result.get('reason','Contexto ou cartas pendentes.'))
        if selected:
            action=selected['action'];button=next((b for b in reading.get('hero_buttons',[]) if b['action']==action),None)
            if action in ('fold','check','call') and button:
                option=dict(action=action,frequency=1)
                if action=='call':option['sizing_bb']=button['amount']
                decision=dict(status='found',options=[option],observation=obs,provenance=result['provenance'])
            else:decision=dict(status='pending',reason='Range recomenda '+action+', mas o sizing não foi exportado ou o botão não foi reconhecido.')
        grades={action:self.book.grade(policy_reading,spec['context'],action) for action in spec['node']['legalActions']}
        return dict(index=index,title=spec['title'],state=spec['state'],reading=reading,decision=decision,
                    observation=obs,range_decision=result,range_selection=selected,grades=grades,
                    nvt_context=spec['context'],legal_range_actions=spec['node']['legalActions'],
                    context_source='simulator: preflop, spot, positions and NVT reference table; cards/buttons from OCR',
                    optical_seconds=round(perf_counter()-start,3),obscured=obscure),png

    def run(self,index,obscure=False):
        event,png=self.observe(index,obscure)
        event['execution']=SimulatedTable(index+1).apply(event['decision'],event['reading'].get('hero_buttons',[]))
        return event,png
