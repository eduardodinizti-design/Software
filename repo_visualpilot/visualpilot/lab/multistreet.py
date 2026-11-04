"""Bounded offline flop/turn/river planning against an explicit response model.

Public chance sampling approximates future cards; no hidden-card clairvoyance.
Not an equilibrium solver. One raise per street, no rake/ICM or multiway pots.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
import random
import time
from .postflop import DECK, validate_cards
from .hand_rank import rank_hand
from .chance_sampling import sample_indices
from .range_state import normalize_range, condition
from .river_tree import Choice, Terminal, river_tree


@dataclass(frozen=True)
class SearchConfig:
    fractions: tuple = (1/3, 2/3, 1.)
    include_all_in: bool = True
    raise_multiplier: float = 3.
    chance_samples: int = 3  # 0 enumerates all public cards (expensive on flop).
    all_in_samples: int = 500
    max_nodes: int = 100000
    seed: int = 42
    exact_turn: bool = False  # Enumerate every river, including all-in runouts on turn.
    chance_method: str = 'random'

    def validate(self):
        if self.chance_method not in ('random','stratified'): raise ValueError('Método de chance inválido.')
        if not self.fractions or any(type(f) not in (int,float) or not math.isfinite(f) or f<=0 for f in self.fractions):
            raise ValueError('Frações de pote inválidas.')
        if type(self.exact_turn) is not bool: raise ValueError('Flag de turn exato inválida.')
        if type(self.include_all_in) is not bool: raise ValueError('Flag de all-in inválida.')
        if not math.isfinite(self.raise_multiplier) or self.raise_multiplier<2: raise ValueError('Raise inválido.')
        for value,minimum in ((self.chance_samples,0),(self.all_in_samples,2),(self.max_nodes,1)):
            if type(value) is not int or value<minimum: raise ValueError('Orçamento inválido.')
        if type(self.seed) is not int: raise ValueError('Seed inválida.')


def sizes(pot, stack, config):
    """Round to 0.01 units, cap by remaining effective stack, deduplicate."""
    bets={min(stack,round(pot*f,2)) for f in config.fractions}
    if config.include_all_in: bets.add(stack)
    bets=sorted(b for b in bets if b>0)
    raises={min(stack,round(b*config.raise_multiplier,2)) for b in bets}
    if config.include_all_in: raises.add(stack)
    return bets,sorted(raises)


def swap(node):
    if isinstance(node,Terminal):
        return Terminal(node.villain_paid,node.hero_paid,
                        {'hero':'villain','villain':'hero','showdown':'showdown'}[node.winner])
    return Choice('villain' if node.actor=='hero' else 'hero',{a:swap(c) for a,c in node.children.items()})


class BudgetExceeded(Exception): pass


def solve_postflop(hero, board, weights, pot, stack, opponent, model_id,
                   config=SearchConfig(), hero_position='oop', opponent_checked=False, facing_bet=0., pko=None):
    """Unopened street, or a single opponent bet. IP unopened requires observed check.
    With facing_bet, pot includes that bet; stack is Hero remaining effective stack.

    opponent(combo, board, public_history, legal_actions, public_context) returns
    probabilities. It never receives Hero cards. History includes street/card markers.
    EV relative to current decision, not to the start of the hand.
    """
    start=time.perf_counter();config.validate()
    if len(hero)!=2 or len(board) not in (3,4,5): raise ValueError('Estado pós-flop inválido.')
    validate_cards(tuple(hero)+tuple(board));hero=tuple(hero);board=tuple(board)
    if any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in (pot,stack)):
        raise ValueError('Pote/stack inválidos.')
    if hero_position not in ('oop','ip') or type(opponent_checked) is not bool:
        raise ValueError('Posição inválida.')
    if type(facing_bet) not in (int,float) or not math.isfinite(facing_bet) or facing_bet<0 or facing_bet>stack or facing_bet>=pot:
        raise ValueError('Aposta enfrentada inválida.')
    if (facing_bet and opponent_checked) or (not facing_bet and opponent_checked != (hero_position=='ip')):
        raise ValueError('IP exige check observado; OOP deve agir primeiro.')
    if not model_id: raise ValueError('Modelo deve ter identificação.')
    if pko is not None: pko.validate(stack)
    belief=normalize_range(weights,hero+board)
    inputs=dict(hero=list(hero),board=list(board),weights=[[*c,w] for c,w in belief.items()],
                pot=pot,stack=stack,model_id=model_id,config=config.__dict__,
                hero_position=hero_position,opponent_checked=opponent_checked,facing_bet=facing_bet,pko=pko.trace() if pko else None)
    decisions=[];chance_trace=[];model_hash=hashlib.sha256();nodes=0;all_in_used=False;all_in_cache={};sampled_chance=False

    @lru_cache(maxsize=100000)
    def cached_strength(cards): return rank_hand(cards)

    def strength(cards): return cached_strength(tuple(sorted(cards)))

    @lru_cache(maxsize=50000)
    def exact_turn_combo(b,combo):
        deck=[c for c in DECK if c not in hero+b+combo]
        wins=ties=0
        for card in deck:
            h=strength(hero+b+(card,));v=strength(combo+b+(card,))
            wins+=h>v;ties+=h==v
        return (wins+.5*ties)/len(deck),wins/len(deck)

    def showdown(current_board,current_belief):
        h=strength(hero+current_board)
        win=sum(w*float(h>strength(c+current_board)) for c,w in current_belief.items())
        tie=sum(w*float(h==strength(c+current_board)) for c,w in current_belief.items())
        return win+.5*tie,win

    def chance(current_board,current_belief):
        nonlocal sampled_chance
        remaining=48-len(current_board)  # 52 minus Hero2, villain2, board.
        candidates=[]
        for card in DECK:
            if card in hero+current_board: continue
            likelihood={c:float(card not in c)/remaining for c in current_belief}
            probability=sum(current_belief[c]*p for c,p in likelihood.items())
            if probability:
                posterior,_=condition(current_belief,likelihood)
                candidates.append((card,probability,posterior))
        if config.chance_samples==0 or (config.exact_turn and len(current_board)==4): return candidates
        sampled_chance=True
        # Same uniforms across action alternatives reduce sampling noise, without peeking at future cards.
        digest=hashlib.sha256((str(config.seed)+':'+','.join(current_board)).encode()).digest()
        rng=random.Random(int.from_bytes(digest[:8],'big'))
        indices=sample_indices([v[1] for v in candidates],config.chance_samples,rng,config.chance_method)
        chosen=[candidates[i] for i in indices]
        counts={}
        for card,_,posterior in chosen: counts[card]=(counts.get(card,(0,None))[0]+1,posterior)
        return [(card,count/config.chance_samples,posterior) for card,(count,posterior) in counts.items()]

    def street(current_board,current_belief,current_pot,current_stack,history,initial=False):
        bets,raises=sizes(current_pot,current_stack,config)
        tree=river_tree(current_stack,bets,raises)
        if hero_position=='ip':
            if initial: tree=Choice('hero',dict(tree.children,check=Terminal(0,0)))
            else: tree=swap(tree)
        return evaluate(tree,current_board,current_belief,current_pot,current_stack,history)

    def evaluate(node,b,belief,p,s,history):
        nonlocal nodes,all_in_used
        nodes+=1
        if nodes>config.max_nodes: raise BudgetExceeded()
        if isinstance(node,Terminal):
            if node.winner=='hero': return p+node.villain_paid
            if node.winner=='villain': return -node.hero_paid
            paid=node.hero_paid
            if abs(paid-node.villain_paid)>1e-8: raise ValueError('Rua encerrada sem investimentos iguais.')
            new_pot=p+2*paid;new_stack=max(0,s-paid)
            if len(b)==5:
                eq,win=showdown(b,belief)
                bounty=pko.reward(min(1.,win),new_stack<=1e-9)['expected_bb'] if pko else 0.
                return eq*new_pot-paid+bounty
            if new_stack<=1e-9:
                if config.exact_turn and len(b)==4:
                    values={c:exact_turn_combo(b,c) for c in belief}
                    eq=sum(w*values[c][0] for c,w in belief.items())
                    win=sum(w*values[c][1] for c,w in belief.items())
                    bounty=pko.reward(min(1.,win),True)['expected_bb'] if pko else 0.
                    return eq*new_pot-paid+bounty
                all_in_used=True
                key=(b,tuple(belief.items()))
                if key not in all_in_cache:
                    rng=random.Random(config.seed);combos=list(belief)
                    total=0.;wins=0.
                    for combo in rng.choices(combos,weights=list(belief.values()),k=config.all_in_samples):
                        deck=[c for c in DECK if c not in hero+b+combo]
                        runout=tuple(rng.sample(deck,5-len(b)))
                        h=strength(hero+b+runout);v=strength(combo+b+runout)
                        total+=float(h>v)+.5*(h==v);wins+=float(h>v)
                    all_in_cache[key]=(total/config.all_in_samples,wins/config.all_in_samples)
                eq,win=all_in_cache[key]
                bounty=pko.reward(win,True)['expected_bb'] if pko else 0.
                return eq*new_pot-paid+bounty
            branches=chance(b,belief)
            chance_trace.append(dict(history=list(history),board=list(b),
                branches=[dict(card=c,weight=w) for c,w,_ in branches]))
            return sum(prob*street(b+(card,),posterior,new_pot,new_stack,
                       history+(f'board:{card}',)) for card,prob,posterior in branches)-paid
        if node.actor=='hero':
            options={a:evaluate(child,b,belief,p,s,history+(f'hero:{a}',)) for a,child in node.children.items()}
            chosen=max(options,key=options.get)
            decisions.append(dict(history=list(history),board=list(b),pot=p,stack=s,
                combos=len(belief),range_sha256=hashlib.sha256(json.dumps([[*c,w] for c,w in belief.items()]).encode()).hexdigest(),
                alternatives=options,chosen=chosen))
            return options[chosen]
        context=dict(pot=p,stack=s,hero_position=hero_position,pko=pko.trace() if pko else None)
        rows={c:opponent(c,b,history,tuple(node.children),dict(context)) for c in belief}
        for row in rows.values():
            if set(row)!=set(node.children) or any(type(v) not in (int,float) or not math.isfinite(v)
                or not 0<=v<=1 for v in row.values()) or abs(sum(row.values())-1)>1e-9:
                raise ValueError('Modelo adversário inválido.')
        model_hash.update(json.dumps(dict(history=history,board=b,pot=p,stack=s,
                          rows=[[*c,row] for c,row in rows.items()]),sort_keys=True).encode())
        value=0.
        for action,child in node.children.items():
            likelihood={c:row[action] for c,row in rows.items()}
            probability=sum(belief[c]*likelihood[c] for c in belief)
            if probability:
                posterior,_=condition(belief,likelihood)
                value+=probability*evaluate(child,b,posterior,p,s,history+(f'villain:{action}',))
        return value

    try:
        if facing_bet:
            base_pot=pot-facing_bet
            bets,raises=sizes(base_pot,stack,config)
            raises=sorted(set(raises+[min(stack,round(facing_bet*config.raise_multiplier,2))]))
            tree=swap(river_tree(stack,[facing_bet],raises)).children[f'bet:{facing_bet:g}']
            result=evaluate(tree,board,belief,base_pot,stack,(f'villain:bet:{facing_bet:g}',))
        else:
            result=street(board,belief,pot,stack,(),True)
    except BudgetExceeded:
        return dict(status='pending',reason='search_budget_exceeded',chosen=None,inputs=inputs,nodes=nodes,
                    seconds=time.perf_counter()-start,laboratory_only=True)
    return dict(status='experimental',chosen=decisions[-1]['chosen'],ev=result,
        comparisons=decisions[-1]['alternatives'],decisions=decisions,chance_trace=chance_trace,
        inputs=inputs,input_sha256=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest(),
        response_sha256=model_hash.hexdigest(),nodes=nodes,seconds=time.perf_counter()-start,
        laboratory_only=True,utility='chip_ev_plus_immediate_bounty' if pko else 'chip_ev',
        pko=pko.trace() if pko else None,exact_under_model=not sampled_chance and not all_in_used,
        limitations=['fixed_opponent_not_GTO','one_raise_per_street','heads_up_chip_ev_no_rake',
                     'sampled_maximization_can_be_optimistic','unopened_or_single_bet_current_street'],
        requires_independent_seed_validation=sampled_chance or all_in_used,
        computation=dict(rank_cache=cached_strength.cache_info()._asdict(),
                         exact_turn_combo_cache=exact_turn_combo.cache_info()._asdict()))


def compare_seeds(hero, board, weights, pot, stack, opponent, model_id,
                  config=SearchConfig(), seeds=(11,23,47), **position):
    """Repeat whole searches; stability is not a GTO or model-correctness certificate."""
    from dataclasses import replace
    if len(seeds)<3 or len(set(seeds))!=len(seeds): raise ValueError('Use ao menos três seeds distintas.')
    runs=[solve_postflop(hero,board,weights,pot,stack,opponent,model_id,
                        replace(config,seed=seed),**position) for seed in seeds]
    if any(r['status']=='pending' for r in runs):
        return dict(status='pending',reason='search_budget_exceeded',chosen=None,runs=runs)
    actions=runs[0]['comparisons']
    means={a:sum(r['comparisons'][a] for r in runs)/len(runs) for a in actions}
    best=max(means,key=means.get)
    stable=all(r['chosen']==best for r in runs)
    return dict(status='experimental' if stable else 'pending',
                reason='seed_stable_only' if stable else 'unstable_across_seeds',
                chosen=best if stable else None,mean_ev=means,
                observed_ev_range={a:[min(r['comparisons'][a] for r in runs),max(r['comparisons'][a] for r in runs)] for a in actions},
                laboratory_only=True,runs=runs,
                limitation='Shared maximization bias and opponent-model error are not measured by seed stability.')
