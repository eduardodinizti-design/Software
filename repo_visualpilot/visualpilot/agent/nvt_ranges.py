"""Read the NVT Range Lab preflop export without inventing missing contexts/sizing."""
import hashlib
import json
import math
from pathlib import Path
from .connector import canonical_hand

POSITIONS=('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB')
SPREADS={'iguais':[25]*9,'curtos_fim':[35,35,30,30,25,20,15,15,20],
         'curtos_ini':[15,15,20,20,25,30,35,35,30]}

def nearest_spread(stacks):
    if not isinstance(stacks,dict) or any(type(stacks.get(p)) not in (int,float) or
        not math.isfinite(stacks[p]) or stacks[p]<=0 for p in POSITIONS):
        raise ValueError('Stacks das nove posições são necessários.')
    actual=[stacks[p] for p in POSITIONS];mean=sum(actual)/9
    best=None;distance=float('inf')
    for name,values in SPREADS.items():
        refmean=sum(values)/9
        d=sum((a/mean-b/refmean)**2 for a,b in zip(actual,values))
        if d<distance-1e-9:best=name;distance=d
    return best

class NvtRangeBook:
    def __init__(self,path):
        raw=Path(path).read_bytes();data=json.loads(raw)
        if data.get('format')!='nvt-range-export' or data.get('version')!=1:
            raise ValueError('Formato NVT desconhecido.')
        hands=data['hands']
        if len(hands)!=169 or len(set(hands))!=169:raise ValueError('Catálogo de mãos inválido.')
        self.hands={hand:i for i,hand in enumerate(hands)}
        self.provenance=dict(engine_commit=data['engineCommit'],generated_at=data['generatedAt'],
                             validation=data['validation'],package_sha256=hashlib.sha256(raw).hexdigest())
        self.nodes={}
        for node in data['nodes']:
            if not node.get('validated'):continue
            key=self.key(node['context'],node['spot'],node['hero'],node['vs'],node.get('spread'))
            if key in self.nodes:raise ValueError('Contexto NVT duplicado.')
            for action in node['actions']:
                values=node['freq'][action]
                if len(values)!=169 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in values):
                    raise ValueError('Frequências inválidas.')
                if node['ev'] is not None and len(node['ev'][action])!=169:raise ValueError('EVs inválidos.')
            self.nodes[key]=node

    @staticmethod
    def key(context,spot,hero,vs,spread):
        return (context['mode'],context['stack'],context['stage'],context['players'],spot,hero,tuple(vs),spread)

    def recommend(self,reading,context):
        def pending(reason):return dict(status='pending',reason=reason)
        if reading.get('street')!='preflop' or reading.get('board'):
            return pending('Pacote NVT restrito ao pré-flop comprovado.')
        try:
            hand=canonical_hand(reading.get('hero',[]));i=self.hands[hand]
            mode=context['mode'];stack=context['stack'];players=context['players']
            if mode in ('pko','pko_icm') and any(k in context for k in ('bounties','bounty_power','pko_live')):
                return pending('Pacote NVT estático não recalcula bounty power com bounties individuais; motor dinâmico necessário.')
            hero=context['position'];spot=context['spot'];vs=context['vs']
            if type(stack) not in (int,float) or not math.isfinite(stack) or stack<=0 or players!=9:
                raise ValueError('Mesa ou stack não suportado')
            if hero not in POSITIONS or not isinstance(vs,list) or any(p not in POSITIONS for p in vs):raise ValueError('Posições inválidas')
            if mode in ('icm','pko_icm'):
                stage=context['stage'];spread=context.get('spread')
                if spread is None:spread=nearest_spread(context['stacks'])
                if spread not in SPREADS:raise ValueError('Spread inválido')
            elif mode in ('chip_ev','pko'):
                stage=context.get('stage','mid');stage='mid' if stage=='early' else stage;spread=None
            else:raise ValueError('Modo inválido')
            node=self.nodes.get((mode,stack,stage,players,spot,hero,tuple(vs),spread))
        except (KeyError,TypeError,ValueError):return pending('Contexto pré-flop incompleto ou inválido.')
        if node is None:return pending('Nenhum nó validado para o contexto exato; sem aproximação de stack ou fase.')
        trace=dict(self.provenance,node_id=node['id'],source=node['source'],family=node['family'])
        if i in node.get('outOfRange',[]):
            return dict(status='out_of_range',hand=hand,mix=[],provenance=trace,reason='Mão não chega a este spot.')
        mix=sorted([dict(action=a,frequency=node['freq'][a][i]) for a in node['actions'] if node['freq'][a][i]>0],
                   key=lambda x:-x['frequency'])
        raw_ev={a:node['ev'][a][i] for a in node['actions']} if node['ev'] else None
        # Integration document identifies these zeroes as missing, not indifferent.
        ev={a:(None if a!='fold' and v==0 and node['freq'][a][i]==0 else v) for a,v in raw_ev.items()} if raw_ev else None
        return dict(status='found',hand=hand,mix=mix,ev=ev,raw_ev=raw_ev,ev_unit=node['evUnit'],
                    legal_actions=list(node['legalActions']),sizing_status='not_exported',
                    provenance=trace,scope='preflop_reference_table',advisory_only=True)

    def grade(self,reading,context,chosen):
        strategy=self.recommend(reading,context)
        if strategy['status']!='found':return dict(strategy,correct=None)
        if chosen not in strategy['legal_actions']:
            return dict(status='illegal_action',correct=False,provenance=strategy['provenance'])
        ev=strategy['ev'];loss=None
        if ev and ev.get(chosen) is not None:
            loss=max(0,max(v for v in ev.values() if v is not None)-ev[chosen])
        tolerance=.03 if strategy['ev_unit']=='bb' else .01
        in_mix=any(m['action']==chosen for m in strategy['mix'])
        return dict(status='graded',correct=in_mix or (loss is not None and loss<tolerance),
                    in_mix=in_mix,ev_loss=loss,ev_unit=strategy['ev_unit'],provenance=strategy['provenance'])
