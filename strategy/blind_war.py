"""Reproducible SB/BB arrival from explicit NVT action frequencies, not labels."""
from dataclasses import asdict
import json
import math
from pathlib import Path

from strategy.action_tree import BetMenu
from strategy.range_catalog import ComboRange
from strategy.state_contract import BettingState,GameContext,StrategyError,digest
from strategy.texassolver_backend import file_hash

OPEN_ID='chip_ev|mid|40|open_raise|SB||-'
CALL_ID='chip_ev|mid|40|vs_open|BB|SB|-'
SB40_TAG='hu-sb-bb40-nvt-pilot-20261115'


def extract_reference(path):
    """Keep all 169 class frequencies of the selected actions without rounding."""
    data=json.loads(Path(path).read_text());hands=data['hands'];nodes=data['nodes']
    if len(hands)!=169 or len(set(hands))!=169:raise StrategyError('NVT_169_UNIQUE_CLASSES_REQUIRED')
    ranges={}
    for name,node_id,action in (('sb_open',OPEN_ID,'raise'),('bb_call',CALL_ID,'call')):
        matches=[n for n in nodes if n['id']==node_id]
        if len(matches)!=1:raise StrategyError('ONE_EXACT_NVT_40BB_NODE_REQUIRED:'+node_id)
        node=matches[0];freq=node['freq']
        if action not in freq or any(len(v)!=169 for v in freq.values()):raise StrategyError('NVT_ACTION_VECTOR_MISMATCH')
        for i in range(169):
            values=[v[i] for v in freq.values()]
            if (any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in values)
                    or abs(sum(values)-1)>.0011):raise StrategyError('NVT_ACTION_FREQUENCIES_INVALID')
        ranges[name]=dict(node_id=node_id,selected_action=action,
            class_frequencies=dict(zip(hands,freq[action])),
            all_action_frequencies={a:dict(zip(hands,v)) for a,v in freq.items()},
            exporter_claimed_validated=node.get('validated'),source=node.get('source'),
            context=node['context'],table=node['table'])
    opening=ranges['bb_call']['table'];amounts=opening['actions']
    ante=sum(a['amount'] for a in amounts if a['type']=='post_ante')
    sb_post=sum(a['amount'] for a in amounts if a['position']=='SB' and a['type']=='post_sb')
    raise_paid=sum(a['amount'] for a in amounts if a['position']=='SB' and a['type']=='raise')
    open_to=sb_post+raise_paid
    if (ante!=1 or sb_post!=.5 or open_to!=2 or opening['potBb']!=4
            or opening['potBb']!=1.5+ante+raise_paid):
        raise StrategyError('NVT_BLIND_WAR_GEOMETRY_NOT_OBSERVED_2BB_WITH_BBA1')
    return dict(schema='software.hu-nvt-blind-war-reference.v1',
        source=dict(file=Path(path).name,sha256=file_hash(path),generated_at=data.get('generatedAt'),
            engine_commit=data.get('engineCommit'),reference_kind='USER_APPROVED_NVT_NOT_DIRECT_HRC_EXPORT'),
        geometry=dict(sb_post_bb=.5,bb_post_bb=1.,big_blind_ante_bb=ante,open_to_bb=open_to,
            raise_amount_semantics='ADDITIONAL_SB_CONTRIBUTION_CHECKED_AGAINST_OBSERVED_POT'),
        ranges=ranges,limitations=[
            'Exporter validation/source labels are not independent HRC certification.',
            'Illustrated table stacks differ from the 40 BB context. Both initial stacks are explicitly configured to 40 BB.',
            'No SB limp/BB check arrival ranges were found in this upload; raise and limp ranges are not interchangeable.'])


def game_from_reference(reference,board=('As','7d','2c')):
    if reference.get('schema')!='software.hu-nvt-blind-war-reference.v1':raise StrategyError('SB40_REFERENCE_SCHEMA_REQUIRED')
    if reference['geometry']!={
            'sb_post_bb':.5,'bb_post_bb':1.,'big_blind_ante_bb':1,'open_to_bb':2.,
            'raise_amount_semantics':'ADDITIONAL_SB_CONTRIBUTION_CHECKED_AGAINST_OBSERVED_POT'}:
        raise StrategyError('SB40_EXPLICIT_ARRIVAL_GEOMETRY_REQUIRED')
    context=GameContext(('SB','BB'),dealt_players=9,
        arrival_id='NVT-40bb-before-posts-SB-open2-BB-call-BBA1-'+reference['source']['sha256'][:12])
    root=BettingState(tuple(board),pot_bb=5.,stacks=(38.,37.),actor=0,oop=0)
    ranges=[]
    for name in ('sb_open','bb_call'):
        value=reference['ranges'][name]
        source=digest([reference['source'],value['node_id'],value['selected_action']])
        ranges.append(ComboRange.from_classes(value['class_frequencies'],source).to_dict())
    return dict(schema='software.hu-game.v1',context=asdict(context),root=root.to_dict(),ranges=ranges,
        menu=asdict(BetMenu(fractions=(1/3,),max_raises=2,include_all_in=True)))


def arrival_settings():
    return dict(ante_pot_bb=1.,preflop_aggressor=0,name='SB-BB40-BBA1-open2-reference-v1')
