"""Versioned, exact-context laboratory policies; no training or action execution."""
from copy import deepcopy
import hashlib
import json
import math
import re
from pathlib import Path
from .connector import canonical_hand

STREETS={'preflop':0,'flop':3,'turn':4,'river':5}
FIELDS=('street','hero','board','position','effective_stack_bb','pot_bb','action_history')

def state_key(state):
    if any(key not in state for key in FIELDS):
        raise ValueError('Contexto incompleto')
    street=state['street'];hero=state['hero'];board=state['board']
    if street not in STREETS or not isinstance(board,list) or len(board)!=STREETS[street]:
        raise ValueError('Etapa incompatível com board')
    canonical_hand(hero)
    all_cards=hero+board
    if any(not isinstance(c,str) or len(c)!=2 or c[0] not in '23456789TJQKA' or c[1] not in 'shdc' for c in all_cards) or len(set(all_cards))!=len(all_cards):
        raise ValueError('Cartas inválidas ou duplicadas')
    if not isinstance(state['position'],str) or not state['position'].strip() or state['position'].upper()=='UNKNOWN':
        raise ValueError('Posição desconhecida')
    for field in ('effective_stack_bb','pot_bb'):
        value=state[field]
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise ValueError('Valor numérico inválido')
    if not isinstance(state['action_history'],list):
        raise ValueError('Histórico de ações inválido')
    value={key:deepcopy(state[key]) for key in FIELDS}
    value['hero']=sorted(hero)  # Board order remains meaningful across streets.
    value['position']=state['position'].upper()
    for field in ('effective_stack_bb','pot_bb'):value[field]=float(value[field])
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

class LaboratoryRangeBook:
    def __init__(self,path):
        raw=Path(path).read_bytes();data=json.loads(raw)
        if data.get('schema_version')!=1 or not data.get('source') or not data.get('version'):
            raise ValueError('Origem, versão e schema obrigatórios')
        self.source=data['source'];self.version=data['version']
        self.sha256=hashlib.sha256(raw).hexdigest();self.entries={}
        for entry in data['entries']:
            key=state_key(entry['state'])
            if key in self.entries:raise ValueError('Contexto duplicado')
            options=entry['options']
            if not options:raise ValueError('Opções ausentes')
            total=0.
            for option in options:
                if option['action'] not in ('fold','check','call','bet','raise'):
                    raise ValueError('Ação inválida')
                frequency=option['frequency']
                if type(frequency) not in (int,float) or not math.isfinite(frequency) or not 0<=frequency<=1:
                    raise ValueError('Frequência inválida')
                total+=frequency
                if option['action'] in ('call','bet','raise'):
                    sizing=option.get('sizing_bb')
                    if type(sizing) not in (int,float) or not math.isfinite(sizing) or sizing<0:
                        raise ValueError('Sizing em BB obrigatório')
            if not math.isclose(total,1.,abs_tol=1e-6):raise ValueError('Frequências devem somar 1')
            self.entries[key]=deepcopy(options)

    def recommend(self,reading,context):
        if context.get('laboratory') is not True or context.get('fictional') is not True:
            return dict(status='pending',reason='Contexto de laboratório fictício não confirmado.')
        observation=context.get('observation',{})
        if (not observation.get('table') or type(observation.get('generation')) is not int
                or observation['generation'] < 1
                or not re.fullmatch('[0-9a-f]{64}',str(observation.get('frame_sha256','')))):
            return dict(status='pending',reason='Evidência da observação ausente.')
        state={key:context.get(key) for key in FIELDS}
        for key in ('street','hero','board'):state[key]=reading.get(key)
        try:key=state_key(state)
        except (ValueError,TypeError):return dict(status='pending',reason='Leitura ou contexto incompleto.')
        options=self.entries.get(key)
        if options is None:return dict(status='pending',reason='Nenhum range para este contexto exato.')
        return dict(status='found',mode='laboratory_advisory',options=deepcopy(options),
                    observation=deepcopy(observation),
                    provenance=dict(source=self.source,version=self.version,sha256=self.sha256,
                                    state_sha256=hashlib.sha256(key.encode()).hexdigest()))
