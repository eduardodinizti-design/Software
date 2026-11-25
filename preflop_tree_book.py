"""Read solved, context-specific external trees without inventing an EV.

Current provider: bounded GTOpen calculation evidence. The solver optimizes its
disclosed continuation model, not the full multiway game. Nodes stay reference
policies. Unknown contexts/hands leave the continuous NVT policy available.
"""
import hashlib
import json
import math
from pathlib import Path

from preflop_study import hand_key

DEFAULT_DIRECTORY=Path(__file__).resolve().parent/'strategy_data/preflop_trees'
_RANKS='AKQJT98765432'
HAND_LABELS={r+r for r in _RANKS}|{a+b+s for i,a in enumerate(_RANKS) for b in _RANKS[i+1:] for s in ('s','o')}


def _finite(v):return type(v) in (int,float) and math.isfinite(v)


def _family(identity):
    for prefix,scenario,hero,aggressor,limpers,callers in (
        ('two_limps_BTN_','limped','BTN',None,['UTG','HJ'],[]),
        ('open_two_callers_BB_','open_with_callers','BB','UTG',[],['HJ','CO']),
        ('CO_vs_SB_3bet_','vs_3bet','CO','SB',[],[]),
        ('SB_vs_CO_4bet_','vs_4bet','SB','CO',[],[])):
        if identity.startswith(prefix):return dict(scenario=scenario,hero_position=hero,aggressor=aggressor,limpers=limpers,callers=callers)
    return None


def _action(kind,scenario):
    if kind in ('fold','call','check'):return kind
    if kind in ('jam','all_in'):return 'all_in'
    if kind in ('raise','bet'):
        return {'vs_3bet':'four_bet','vs_4bet':'five_bet','open_with_callers':'three_bet'}.get(scenario,'raise')
    raise ValueError('Unknown external action kind.')


class TreeBook:
    def __init__(self,records=()):
        self.records=list(records);self.errors=[]

    @classmethod
    def from_directory(cls,path=DEFAULT_DIRECTORY):
        book=cls()
        for filename in sorted(Path(path).glob('*.json')):
            try:
                raw=filename.read_bytes()
                if len(raw)>4_000_000:raise ValueError('Oversized reference node.')
                record=cls.decode(json.loads(raw),hashlib.sha256(raw).hexdigest(),filename.name)
                if record:book.records.append(record)
            except (OSError,ValueError,KeyError,TypeError) as exc:
                book.errors.append(dict(file=filename.name,reason=str(exc)))
        return book

    @staticmethod
    def decode(data,digest,name):
        if not isinstance(data,dict):raise ValueError('Reference must be a JSON object.')
        context=_family(data.get('id',''));node=data.get('node') or {};cfg=data.get('config') or {}
        if not isinstance(node,dict) or not isinstance(cfg,dict):raise ValueError('Invalid reference node/config.')
        if context is None:return None
        if node.get('kind')!='action' or node.get('strategy_note') or node.get('low_reach'):
            return None
        if node.get('actor_pos')!=context['hero_position'] or int((data.get('status') or {}).get('iteration',0))<1:
            return None
        hands=data.get('hand_order');matrix=node.get('strategy');acts=node.get('actions');reach=node.get('reach')
        if not isinstance(hands,list) or len(hands)!=169 or set(hands)!=HAND_LABELS:
            raise ValueError('169 unique hand labels required.')
        if not isinstance(acts,list) or not acts or len(matrix or [])!=169*len(acts) or len(reach or [])!=169:
            raise ValueError('Invalid action/strategy dimensions.')
        if not all(_finite(v) and 0<=v<=1.00001 for v in [*matrix,*reach]):
            raise ValueError('Nonfinite/invalid frequencies or reach.')
        if cfg.get('icm') is not None or cfg.get('rake_pct',0)!=0 or cfg.get('ante',0)!=0:
            return None # this adapter currently declares regular, zero-rake chip-EV
        if not _finite(cfg.get('stack')) or cfg['stack']<=0:raise ValueError('Invalid tree depth.')
        pos=node['positions'];bets=node['invested'];hero=pos.index(context['hero_position'])
        if len(pos)!=len(bets) or not all(_finite(v) and v>=0 for v in bets):raise ValueError('Invalid tree money.')
        top=max(bets);own=bets[hero]
        options=[]
        for j,a in enumerate(acts):
            action=_action(a['kind'],context['scenario']);target=a.get('to')
            if action not in ('fold','check','call') and (not _finite(target) or not top<target<=cfg['stack']+.001):
                raise ValueError('Invalid external raise target.')
            options.append(dict(id=f'{data["id"]}:{j}',action=action,to_bb=target,
                                preset_mult=(target/top if top>0 else target) if action not in ('fold','check','call') else None,
                                all_in=action=='all_in',label=a['label']))
        values=data.get('action_values') or {};ev_rows={}
        if not isinstance(values,dict):raise ValueError('Invalid action EV document.')
        if values.get('hands') and values.get('units')!='original bb relative to folding here':
            raise ValueError('Unknown EV unit or baseline.')
        for row in values.get('hands') or []:
            if row.get('hand') in ev_rows:raise ValueError('Duplicate action-EV hand.')
            ev_rows[row.get('hand')]=row.get('actions') or []
        if ev_rows:
            if values.get('path')!=data.get('path') or values.get('actor')!=context['hero_position']:
                raise ValueError('Action EV belongs to another node.')
            if set(ev_rows)!=set(hands):raise ValueError('Action EV hand labels differ.')
            for hand,rows in ev_rows.items():
                if len(rows)!=len(acts) or any(r.get('label')!=acts[j]['label'] or not _finite(r.get('ev_bb')) for j,r in enumerate(rows)):
                    raise ValueError('Action EV dimensions/labels/values differ.')
        rows={};worst_regret=0.;weighted_regret=weight=0.
        for i,hand in enumerate(hands):
            if reach[i]<=1e-8:continue
            freq=[matrix[j*169+i] for j in range(len(acts))];total=sum(freq)
            if abs(total-1)>.002:raise ValueError('Action mixture is not normalized.')
            rows[hand]=[dict(option,frequency=freq[j]/total,
                            reference_ev_bb=ev_rows[hand][j]['ev_bb'] if hand in ev_rows else None)
                        for j,option in enumerate(options)]
            if hand in ev_rows:
                values=[a['ev_bb'] for a in ev_rows[hand]]
                regret=max(0.,max(values)-sum(f*v/total for f,v in zip(freq,values)))
                mass=reach[i]*(6 if len(hand)==2 else 4 if hand.endswith('s') else 12)
                worst_regret=max(worst_regret,regret);weighted_regret+=mass*regret;weight+=mass
        status=data.get('status') or {}
        current_accuracy=(status.get('accuracy_iteration') is not None and
                          status.get('accuracy_iteration')==status.get('iteration')==status.get('published_iteration') and
                          status.get('state')=='done')
        quality=dict(current_complete_snapshot=current_accuracy,
                     max_reached_action_regret_bb=worst_regret if ev_rows else None,
                     mean_reached_action_regret_bb=weighted_regret/weight if weight else None,
                     conditional_reference_tolerance_bb=.02,
                     meaning='Local root action agreement against the saved continuation; not Nash/HRC/real-game validation.')
        research_only=not (current_accuracy and ev_rows and worst_regret<=.02)
        context.update(effective_stack_bb=cfg['stack'],hero_bet=own,to_beat=top,to_call=top-own,
                       hero_stack=cfg['stack']-own,pot=node['pot'],players=len(pos))
        return dict(id=data['id'],file=name,sha256=digest,context=context,hands=rows,
                    quality=quality,research_only=research_only,
                    source=dict(provider='GTOpen',upstream_commit='5c2989397abf314f229d293c16f96ea783c7ca5b',
                                model=(data.get('status') or {}).get('multiway_equity_model'),
                                realization=cfg.get('realization'),status=data.get('status'),
                                locks=data.get('locks'),path=data.get('path'),
                                meaning='Solved configured approximation with explicit prefix priors; not independent HRC/full-game validation.'))

    def lookup(self,cards,context):
        if context.get('facing_all_in'):return None
        hand=hand_key(cards);choices=[]
        for node in self.records:
            if context.get('reference_tree_id') and context['reference_tree_id']!=node['id']:continue
            if node.get('research_only') and not context.get('reference_tree_study'):continue
            c=node['context']
            if any(context.get(k)!=c[k] for k in ('scenario','hero_position','aggressor')):continue
            if any(list(context.get(k) or [])!=c[k] for k in ('limpers','callers')):continue
            if context.get('mode','chip_ev')!='chip_ev' or context.get('stage','mid')!='mid':continue
            profile=context.get('tournament_profile') or {}
            if profile.get('kind','regular')!='regular':continue
            if hand not in node['hands']:continue
            depth=context.get('effective_stack_bb')
            if not _finite(depth) or depth<=0:continue
            score=abs(math.log(depth/c['effective_stack_bb']))
            if _finite(context.get('to_beat')) and context['to_beat']>0 and c['to_beat']>0:
                score+=abs(math.log(context['to_beat']/c['to_beat']))
            choices.append((score,node))
        if not choices:return None
        node=min(choices,key=lambda x:(x[0],x[1]['id']))[1]
        result=dict(node,options=node['hands'][hand]);differences=[]
        for field in ('effective_stack_bb','players','hero_stack','hero_bet','to_call','to_beat','pot'):
            observed=context.get(field);reference=node['context'].get(field)
            if observed!=reference:differences.append(dict(field=field,observed=observed,source=reference))
        differences.append(dict(field='continuation_model',source=node['source']['model'],
                                meaning='Approximate continuation and explicit assumed opponent arrival ranges; not a full-game solution.'))
        result['reference_reasons']=differences
        return result

    def manifest(self):
        return dict(nodes=len(self.records),errors=self.errors,
                    cases=[dict(id=n['id'],context=n['context'],sha256=n['sha256'],covered_hands=len(n['hands']),source=n['source'],quality=n.get('quality'),research_only=n.get('research_only')) for n in self.records])


def startup_line(advisor):
    book=getattr(getattr(advisor,'policy',None),'tree_book',None)
    if not isinstance(book,TreeBook):return None
    active=[r for r in book.records if not r.get('research_only')]
    return '[ARVORES] referencias_condicionais=%d estudo=%d | %s' % (
        len(active),len(book.records)-len(active),', '.join(r['id']+'('+r['sha256'][:8]+'..)' for r in active))
