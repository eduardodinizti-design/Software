"""Executable preflop policy, explicitly requested by the user on 2026-11-13.

NVT is the source for normal nodes. Continuous depth and shorter tables use
declared references, not a refusal. Missing action trees use versioned derived
rules with their own authority, never a fabricated validated solver result.
No input or capture here. Observation failures remain observation failures.
"""
from collections import OrderedDict
import hashlib
import json
import math
from pathlib import Path

from preflop_study import hand_key
from preflop_advisor import SHOVE_ZONE_MAX_BB,infer_spread,_icm_risk_premium
from preflop_equity import range_from_node,equity_vs_range
from strategy.scenarios import classify, from_table_state, ORDER
from sizing import in_position
from tournament_profiles import resolve as tournament_profile, cash_call_ev, for_target

VERSION='preflop-continuous-v2'
SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
AGGRESSIVE={'raise','bet','open_raise','three_bet','four_bet','five_bet','six_bet','all_in','open_shove','three_bet_shove','four_bet_shove'}
ALLOWED={'fold','check','call','limp',*AGGRESSIVE}
RANKS='23456789TJQKA'


def finite(value, minimum=0):
    return type(value) in (int,float) and math.isfinite(value) and value>=minimum


def missing(reason):
    return dict(status='ABSTAIN',phase='preflop',recommended=None,reason=reason,
                policy_version=VERSION,validated=False,execution_allowed=False)


def observation(state, *, mode='chip_ev',stage='mid'):
    structure=classify(from_table_state(state))
    positions=state.get('positions') or {};seats=state.get('seats') or {}
    hero=positions.get('hero');stack=(seats.get('hero') or {}).get('stack_bb')
    bets={b.get('seat'):b.get('bet_bb') for b in state.get('bets') or [] if finite(b.get('bet_bb'))}
    own=bets.get('hero',1. if hero=='BB' else .5 if hero=='SB' else 0.)
    call=(state.get('to_call') or {}).get('to_call_bb')
    candidates=[]
    for seat,pos in positions.items():
        if seat=='hero' or not (seats.get(seat) or {}).get('occupied') or (seats.get(seat) or {}).get('in_hand') is False:continue
        # First-in: players still to act, not a folded early-position big stack.
        behind=hero in ORDER and pos in ORDER and ORDER.index(pos)>ORDER.index(hero)
        involved=bets.get(seat,0)>1.1 or pos in structure.get('limpers',[])
        remaining=(seats.get(seat) or {}).get('stack_bb')
        if (behind or involved) and finite(remaining):candidates.append(remaining+bets.get(seat,0.))
    effective=min(stack+own,max(candidates)) if finite(stack) and candidates else stack
    scenario=structure['scenario'];opener=structure.get('aggressor')
    unknown_price=False
    if scenario in ('unopened','limped','pending') and finite(call) and call>max(.1,1.1-own):
        if scenario=='pending' and own>1.5:scenario='vs_3bet'
        else:scenario='open'
        unknown_price=True  # Price proves pressure, never the aggressor's position.
    to_beat=max([v for s,v in bets.items() if s!='hero']+[own+(call or 0),1.])
    aggressor_seat=next((s for s,p in positions.items() if p==opener),None)
    vstack=(seats.get(aggressor_seat) or {}).get('stack_bb')
    spread=infer_spread({p:(seats.get(s) or {}).get('stack_bb') for s,p in positions.items()}) if mode in ('icm','pko_icm') else None
    profile=state.get('tournament_profile') or tournament_profile(mode=mode,stage=stage)
    profile=for_target(profile,units=(state.get('bounties') or {}).get(aggressor_seat),
                       fresh=aggressor_seat in (state.get('bounty_fresh_seats') or []),seat=aggressor_seat,
                       unit=(state.get('bounty_units') or {}).get(aggressor_seat,'unknown'))
    return dict(scenario=scenario,hero_position=hero,aggressor=opener,spread=spread,
                limpers=list(structure.get('limpers') or []),callers=list(structure.get('callers') or []),
                raise_levels=list(structure.get('raise_levels') or []),
                hero_stack=stack,hero_bet=own,effective_stack_bb=effective,
                to_call=call,pot=(state.get('pot') or {}).get('pot_bb'),to_beat=to_beat,
                mode=profile['mode'],stage=profile['stage'],tournament_profile=profile,
                players=sum(bool(v.get('occupied')) for v in seats.values()),
                facing_all_in=bool(opener and finite(vstack) and vstack<=.05),
                heads_up_confirmed=sum(1 for seat,v in seats.items() if seat!='hero' and v.get('occupied') and v.get('in_hand') is not False)==1,
                covers_target=bool(finite(vstack) and finite(stack) and stack+own >= vstack+bets.get(aggressor_seat,0)),
                aggressor_inferred_from_price=unknown_price,
                classification_reason=structure.get('reason'))


class PreflopPolicy:
    def __init__(self, source):
        self.source=source
        self._nodes={}
        for n in source.nodes:self._nodes.setdefault((n['spot'],n['hero'],tuple(n.get('vs') or [])),[]).append(n)
        self.cache=OrderedDict()
        self._outcomes=OrderedDict()

    def node(self, spot, hero, vs, context):
        rows=self._nodes.get((spot,hero,tuple(vs)),[])
        if not rows:return None
        depth=context['effective_stack_bb'];mode=context['mode'];stage=context['stage']
        def score(n):
            c=n['context'];fmt='pko' if mode in ('pko','pko_icm') else 'regular'
            return (c['mode']!=mode,c.get('format')!=fmt,c['stage']!=stage,
                    c.get('players')!=context['players'],
                    n.get('spread')!=(context.get('spread') or ('iguais' if mode in ('icm','pko_icm') else None)),
                    abs(math.log(max(.01,c['stack'])/max(.01,depth))),not n.get('validated'),n['id'])
        return min(rows,key=score)

    def _row(self,node,index):
        return {a:float(node['freq'][a][index]) for a in node['actions']} if node and index not in (node.get('outOfRange') or []) else {}

    @staticmethod
    def _best(row, actions):return sum(v for a,v in row.items() if a in actions)

    def decide(self,cards,c):
        try:hand=hand_key(cards)
        except Exception:return missing('CARTAS_PRE_FLOP_ILEGIVEIS')
        if c.get('hero_position') not in ORDER:return missing('POSICAO_PRE_FLOP_ILEGIVEL')
        if not finite(c.get('hero_stack'),.01) or not finite(c.get('effective_stack_bb'),.01):return missing('STACK_PRE_FLOP_ILEGIVEL')
        if c.get('to_call') is not None and not finite(c['to_call']):return missing('PRECO_DA_ACAO_INVALIDO')
        c=dict(c)
        c['tournament_profile']=c.get('tournament_profile') or tournament_profile(mode=c.get('mode'),stage=c.get('stage'))
        c['mode']=c['tournament_profile']['mode'];c['stage']=c['tournament_profile']['stage']
        # Frequencies use the169class, but the execution evidence must retain
        # the EXACT cards of this observation, not another suited combo cached
        # by a previous hand or a browser matrix query.
        cache_key=(tuple(cards),repr(sorted(c.items())))
        if cache_key in self.cache:return dict(self.cache[cache_key])
        pos=c['hero_position'];depth=c['effective_stack_bb'];scenario=c['scenario'];opener=c.get('aggressor')
        short=depth<SHOVE_ZONE_MAX_BB
        index=self.source.hands.index(hand)
        refs=[];rule=None
        def reference(spot,hero=pos,vs=()):
            node=self.node(spot,hero,vs,c)
            if node and node not in refs:refs.append(node)
            return node
        def direct(spot,vs=()):
            n=reference(spot,vs=vs)
            return n,self._row(n,index)
        node=None;row={}
        if scenario in ('vs_4bet','vs_5bet','vs_5bet_or_more','vs_4bet_or_more'):
            # No 3-bet vector is presented as a 4/5-bet solution. This is a
            # disclosed deep-stack response model until a matching tree exists.
            node,row=direct('vs_5bet' if scenario.startswith('vs_5') else 'vs_4bet',vs=(opener,))
            if not row:
                price=c.get('to_call');fraction=(price or 0)/max(depth,.01)
                if hand=='AA':row={'five_bet' if not scenario.startswith('vs_5') else 'six_bet':1.}
                elif hand in ('KK','AKs','QQ') and fraction<=.20:row={'call':1.}
                elif self._playable(hand) and hand[0]==hand[1] and depth>=100 and fraction<=.025:row={'call':1.}
                else:row={'fold':1.}
                rule='deep_four_five_bet_response_v2'
        elif c.get('requested_spot') and not c.get('limpers') and not c.get('callers'):
            node,row=direct(c['requested_spot'],vs=tuple(c.get('requested_vs') or []))
        elif scenario=='pending' and c.get('to_call')==0:
            row={'check':1.};rule='free_option_after_observed_raise'
        elif scenario=='unopened':
            if pos=='BB' and c.get('to_call')==0:row={'check':1.};rule='free_big_blind_option'
            else:
                node,row=direct('open_shove' if short else 'open_raise')
                if not row:node,row=direct('open_raise' if short else 'open_shove')
        elif scenario=='limped':
            if pos=='BB' and c['limpers']==['SB']:
                node,row=direct('vs_limp')
            if not row:
                _,wide=direct('open_shove' if short else 'open_raise')
                tight=reference('open_shove' if short else 'open_raise',hero='UTG')
                narrow=self._row(tight,index)
                premium=hand in ('AA','KK','QQ','AKs','AKo')
                value=premium or (self._best(wide,AGGRESSIVE)>=.5 and self._best(narrow,AGGRESSIVE)>=.5)
                playable=self._playable(hand)
                if value:row={'all_in' if short and c['hero_stack']<=depth+.1 else 'raise':1.}
                elif c.get('to_call')==0:row={'check':1.}
                elif playable and depth>=12 and (c.get('to_call') or 1)<=1.1:row={'call':1.}
                else:row={'fold':1.}
                rule='isolation_value_and_overlimp_v1'
        else:
            spot='vs_3bet' if scenario in ('vs_3bet','threebet_cold','vs_4bet_or_more') else ('vs_open_shove' if c.get('facing_all_in') else 'vs_open')
            node,row=direct(spot,vs=(opener,)) if opener else (None,{})
            if not row and spot=='vs_open_shove' and opener:node,row=direct('vs_open',vs=(opener,))
            if not row and scenario=='pending' and not (c.get('to_call') or 0):
                row={'check':1.};rule='free_option_after_observed_raise'
            if scenario in ('open_with_callers','limp_then_iso'):
                premium=hand in ('AA','KK','QQ','AKs','AKo')
                can_raise=self._best(row,AGGRESSIVE)>=.5 and hand in ('JJ','TT','AQs','AJs','KQs','AQo')
                call=self._best(row,{'call','limp'})>0 and self._playable(hand)
                if premium or can_raise:row={'all_in' if short and c['hero_stack']<=depth+.1 else 'three_bet':1.}
                elif call and depth>=20:row={'call':1.}
                else:row={'fold':1.}
                rule='squeeze_and_overcall_v1'
        if not row or sum(row.values())<=0:
            # A missing export tree is handled by a disclosed class rule, never
            # sold as a solved range or converted to an unknown-state freeze.
            premium=hand in ('AA','KK','AKs','AKo')
            if scenario=='unopened':
                _,opening=direct('open_raise')
                play=self._best(opening,AGGRESSIVE)>0 or self._baseline_open(hand,pos)
                row={'raise' if play else 'fold':1.}
            elif premium:row={'call' if c.get('facing_all_in') else 'four_bet' if scenario in ('vs_3bet','threebet_cold') else 'three_bet':1.}
            elif c.get('to_call')==0:row={'check':1.}
            else:row={'fold':1.}
            rule=rule or 'missing_tree_class_rule_v1'
        # A short-stack shove vector must not become a 5000BB jam. Facing an
        # opponent all-in: call/fold, not a raise into a nonexistent side pot.
        normalized={}
        for action,weight in row.items():
            if action not in ALLOWED or weight<=0:continue
            target=action
            if action in ('all_in','open_shove','three_bet_shove','four_bet_shove'):
                if c.get('facing_all_in'):target='call'
                elif not (node and abs(node['context']['stack']-depth)<.01) or c['hero_stack']>depth+.1:
                    target='raise' if scenario in ('unopened','limped') else 'four_bet' if scenario in ('vs_3bet','threebet_cold','vs_4bet_or_more') else 'three_bet'
            if action in ('raise','bet','open_raise') and scenario not in ('unopened','limped'):target='six_bet' if scenario.startswith('vs_5') else 'five_bet' if scenario in ('vs_4bet','vs_4bet_or_more') else 'four_bet' if scenario in ('vs_3bet','threebet_cold') else 'three_bet'
            if target in ('fold','call','limp') and c.get('to_call')==0:target='check'
            if c.get('facing_all_in') and target in AGGRESSIVE:target='call'
            if target in AGGRESSIVE and c['hero_stack']+c.get('hero_bet',0)<=c.get('to_beat',1):
                target='call' if (c.get('to_call') or 0)>0 else 'check'
            if target!=action and rule is None:rule='source_action_reinterpreted_v2'
            normalized[target]=normalized.get(target,0)+weight
        if not normalized:normalized={'check' if c.get('to_call')==0 else 'fold':1.};rule='outside_arrival_range_v1'
        total=sum(normalized.values());mix=[dict(action=a,frequency=v/total) for a,v in normalized.items()]
        rec=max(mix,key=lambda m:m['frequency'])['action']
        meta=[dict(node_id=n['id'],source_sha256=n.get('_source_sha256') or n.get('_clone_source'),context=n['context'],
                   spot=n['spot'],hero=n['hero'],spread=n.get('spread'),vs=n.get('vs') or [],validated=n.get('validated') is True) for n in refs]
        answer=dict(status='ADVICE',phase='preflop',recommended=rec,mix=mix,
                    policy_version=VERSION,policy_sha256=SHA256,authority='PREFLOP_POLICY',
                    policy_context=dict(c),hand=hand,hero_position=pos,hero_cards=list(cards),
                    stack_bb=c['hero_stack'],effective_stack_bb=depth,
                    stack_bucket=node['context']['stack'] if node else None,
                    bucketed=bool(node and node['context']['stack']!=depth),
                    node_id=node['id'] if node else None,validated=bool(node and node.get('validated') and not rule),
                    solver_validated=False,source_nodes=meta,derived_rule=rule,
                    origin='DERIVED_RULE' if rule else 'NVT_NODE_OR_REFERENCE',
                    spot=node['spot'] if node else scenario,opener=c.get('aggressor'),
                    source_sha256=(node.get('_source_sha256') or node.get('_clone_source')) if node else None,
                    reference_reasons=self._differences(meta,c),execution_allowed=False,
                    reason='Decisão pré-flop por '+(rule or 'range NVT identificado')+'.')
        answer['sizing']=size_for(answer,rec)
        answer['strategic_action']=strategic_action(rec,c)
        answer['source_validated']=bool(node and node.get('validated'))
        if c.get('aggressor_inferred_from_price'):
            answer['reference_reasons'].append(dict(field='aggressor',observed=None,source=None,meaning='Raise inferred only from observed price; no position fabricated.'))
        answer['tournament_profile']=c['tournament_profile']
        if c.get('facing_all_in') and c.get('heads_up_confirmed') and opener and finite(c.get('to_call'),.001) and finite(c.get('pot')):
            shove_spot='3bet_shove' if scenario in ('vs_3bet','threebet_cold','vs_4bet','vs_4bet_or_more','vs_5bet','vs_5bet_or_more') else 'open_shove'
            sn=self.node(shove_spot,opener,(pos,) if shove_spot=='3bet_shove' else (),c)
            combos=range_from_node(sn,self.source.hands,actions=('all_in',)) if sn else []
            if combos:
                ekey=(sn['id'],tuple(cards))
                if ekey not in self._outcomes:
                    self._outcomes[ekey]=equity_vs_range(cards,combos,iters=1600,seed=0,return_details=True)
                    while len(self._outcomes)>256:self._outcomes.popitem(last=False)
                detail=self._outcomes[ekey]
                if detail:
                    call=min(c['hero_stack'],c['to_call'])
                    uncalled=max(0.,c['to_beat']-(c['hero_stack']+c['hero_bet']))
                    pot=max(0.,c['pot']-uncalled)
                    values=cash_call_ev(equity=detail['equity'],win_probability=detail['win_probability'],
                        pot_bb=pot,to_call_bb=call,profile=c['tournament_profile'],
                        covers_target=c.get('covers_target'),heads_up=True)
                    rp=_icm_risk_premium(c['mode'],c['stage'],call,c['hero_stack'])
                    action='call' if values['call_ev_bb']>=rp*(pot+call) else 'fold'
                    answer.update(recommended=action,mix=[dict(action=action,frequency=1.)],
                                  equity=detail['equity'],equity_details=detail,call_evaluation=values,
                                  icm_equity_premium_proxy=rp,contestable_pot_bb=pot,
                                  uncalled_excess_bb=uncalled,derived_rule='terminal_allin_cash_bounty_v2',
                                  origin='MODEL_EV',validated=False)
                    answer['source_nodes'].append(dict(node_id=sn['id'],source_sha256=sn.get('_source_sha256') or sn.get('_clone_source'),
                        context=sn['context'],spot=sn['spot'],hero=sn['hero'],vs=sn.get('vs') or [],validated=sn.get('validated') is True))
                    answer['sizing']=size_for(answer,action)
                    answer['strategic_action']=strategic_action(action,c)
            else:
                answer['reference_reasons'].append(dict(field='allin_equity_range',source=None,meaning='No matching shove prior; no bounty cash EV claimed.'))
        if answer['reference_reasons']:answer['validated']=False
        self.cache[cache_key]=dict(answer)
        if len(self.cache)>1024:self.cache.popitem(last=False)
        return answer

    @staticmethod
    def _playable(hand):
        a,b=RANKS.index(hand[0]),RANKS.index(hand[1])
        return a==b or (hand.endswith('s') and (a==12 or (a>=7 and b>=5) or (a-b<=3 and b>=2)))

    @staticmethod
    def _baseline_open(hand,pos):
        # Transparent last resort if a custom pack omits the position entirely.
        a,b=RANKS.index(hand[0]),RANKS.index(hand[1]);late=pos in ('CO','BTN','SB')
        return a==b or (a==12 and (hand.endswith('s') or b>=8 or late)) or (a>=9 and b>=8) or (late and PreflopPolicy._playable(hand))

    @staticmethod
    def _differences(meta,c):
        out=[]
        for n in meta:
            source=n['context']
            for field,value in (('stack',c['effective_stack_bb']),('players',c['players']),('mode',c['mode']),('stage',c['stage'])):
                if source.get(field)!=value:out.append(dict(node=n['node_id'],field=field,observed=value,source=source.get(field)))
            if not n['validated']:out.append(dict(node=n['node_id'],field='source_validation',source=False))
            if c['mode'] in ('icm','pko_icm') and n.get('spread')!=c.get('spread'):
                out.append(dict(node=n['node_id'],field='spread',observed=c.get('spread'),source=n.get('spread')))
        return out


def size_for(advice,action):
    c=advice['policy_context'];hero=c['hero_stack'];own=c.get('hero_bet') or 0.;scenario=c['scenario']
    if action in ('fold','check'):return dict(size_bb=0.,basis=action)
    if action in ('call','limp'):return dict(size_bb=min(hero,c.get('to_call') or 0),basis='additional_call',unit='BB')
    if action in ('all_in','open_shove','three_bet_shove','four_bet_shove'):
        return dict(size_bb=hero+own,basis='explicit_all_in',all_in=True,unit='BB')
    to_beat=max(c.get('to_beat') or 1.,1.)
    if scenario=='limped':mult=4. if len(c['limpers'])>=2 or c['hero_position'] in ('SB','BB') else 3.;to_beat=1.
    elif action in ('four_bet','five_bet','six_bet'):mult=2. if action in ('five_bet','six_bet') else 2.5 if in_position(c['hero_position'],c.get('aggressor')) else 3.
    elif action=='three_bet' or scenario not in ('unopened','limped'):
        mult=4. if c.get('callers') or not in_position(c['hero_position'],c.get('aggressor')) else 3.
    else:mult=2.5 if c['effective_stack_bb']>40 else 2.;to_beat=1.
    size=round(to_beat*mult,1);cap=hero+own
    return dict(size_bb=min(size,cap),basis='discrete_preflop_preset',preset_mult=mult,
                to_beat_bb=to_beat,unit='BB',all_in=size>=cap-.05)


def strategic_action(action,context):
    scenario=context.get('scenario')
    if scenario=='limped':return 'overlimp' if action in ('call','limp') else 'iso_raise' if action in AGGRESSIVE else action
    if scenario=='open_with_callers':return 'overcall' if action=='call' else 'squeeze' if action in AGGRESSIVE else action
    if scenario=='unopened' and action in ('raise','bet'):return 'open_raise'
    return action


def execution_reasons(advice,cards):
    if advice.get('status')!='ADVICE':return [advice.get('reason') or 'Leitura pré-flop pendente.']
    reasons=[];c=advice.get('policy_context') or {}
    if advice.get('policy_version')!=VERSION or advice.get('policy_sha256')!=SHA256 or advice.get('authority')!='PREFLOP_POLICY':reasons.append('Política pré-flop não reconhecida.')
    try:
        if hand_key(cards)!=advice.get('hand') or list(cards)!=advice.get('hero_cards'):reasons.append('Cartas diferem da decisão.')
    except Exception:reasons.append('Cartas não confirmadas.')
    if c.get('hero_position') not in ORDER or not finite(c.get('hero_stack'),.01):reasons.append('Posição ou stack ilegível.')
    if advice.get('recommended') not in ALLOWED:reasons.append('Ação pré-flop desconhecida.')
    if not advice.get('source_nodes') and not advice.get('derived_rule'):reasons.append('Falta origem da decisão.')
    if not finite(c.get('to_call')):reasons.append('Preço da ação ilegível.')
    if advice.get('recommended') in AGGRESSIVE:
        s=advice.get('sizing') or {}
        if not finite(s.get('size_bb'),.01) or s['size_bb']>c.get('hero_stack',0)+c.get('hero_bet',0)+.11:reasons.append('Tamanho de aposta inválido.')
    return reasons


def resolve_decision(advice, identity):
    """Resolve frequencies once for the hand AND economic context, then size it."""
    answer=dict(advice);mix=answer.get('mix') or []
    if not mix:return answer
    raw=json.dumps([identity,answer.get('policy_context'),answer.get('node_id'),mix],sort_keys=True,default=str).encode()
    roll=int.from_bytes(hashlib.sha256(raw).digest()[:8],'big')/2**64
    weight=sum(m['frequency'] for m in mix);remaining=roll*weight;selected=mix[-1]['action']
    for item in mix:
        remaining-=item['frequency']
        if remaining<0:selected=item['action'];break
    answer.update(dominant_recommended=answer.get('recommended'),recommended=selected,
                  sampling=dict(method='stable_hand_context_frequencies',roll=roll))
    answer['sizing']=size_for(answer,selected)
    answer['strategic_action']=strategic_action(selected,answer['policy_context'])
    return answer


def decision_key(result,table,hand):
    advice=result.get('advice') or {}
    raw=json.dumps([advice.get('policy_context'),advice.get('recommended'),advice.get('sizing')],sort_keys=True,default=str).encode()
    return table,hand,hashlib.sha256(raw).hexdigest()


class RuntimePreflopAdvisor:
    def __init__(self,source):
        self.source=source;self.policy=PreflopPolicy(source);self._confirmed={}
    def __getattr__(self,name):return getattr(self.source,name)
    def advise_from_reading(self,state,cards,**kwargs):
        c=observation(state,mode=kwargs.get('mode'),stage=kwargs.get('stage'))
        key=(state.get('decision_table_id'),state.get('decision_hand_id'))
        prior=self._confirmed.get(key) if all(v is not None for v in key) else None
        if prior and c['to_beat']>prior['raise_to_bb']+.1 and abs(c['hero_bet']-prior['raise_to_bb'])<.15:
            # A confirmed hero 3-bet -> facing at least a 4-bet. Never call an
            # observed amount alone a complete action history.
            level=prior['raise_level']+1
            c['raise_depth_lower_bound']=level
            c['scenario']='vs_5bet_or_more' if level>=4 else 'vs_4bet' if level==3 else 'vs_3bet'
            c['raise_depth_source']='confirmed_hero_action_plus_observed_higher_bet'
        return self.policy.decide(cards,c)

    def record_confirmation(self,table,hand,advice,outcome):
        if hand is None or outcome.get('confirmed') is not True or advice.get('recommended') not in AGGRESSIVE:return
        c=advice.get('policy_context') or {};scenario=c.get('scenario')
        level={'unopened':1,'limped':1,'open':2,'open_with_callers':2,'limp_then_iso':2,'vs_3bet':3,'threebet_cold':3,'vs_4bet':4,'vs_4bet_or_more':4}.get(scenario)
        if scenario in ('vs_5bet','vs_5bet_or_more'):level=max(5,c.get('raise_depth_lower_bound',4)+1)
        if level is None:return
        target=(advice.get('sizing') or {})['size_bb']
        selected=outcome.get('preset')
        if finite(selected,.01):target=min(c['hero_stack']+c['hero_bet'],selected*c['to_beat'])
        outcome['requested_raise_to_bb']=(advice.get('sizing') or {})['size_bb']
        outcome['selected_raise_to_estimate_bb']=target
        outcome['raise_amount_observed']=False
        self._confirmed[(table,hand)]=dict(raise_level=level,raise_to_bb=target)
        while len(self._confirmed)>256:self._confirmed.pop(next(iter(self._confirmed)))
