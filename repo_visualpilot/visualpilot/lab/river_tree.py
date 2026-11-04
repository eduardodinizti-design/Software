"""Finite river best response to an explicit opponent model, NOT equilibrium.

Hero decisions use public history and posterior ranges, never villain hole cards.
One raise allowed per line; no re-raise. No live transport or input automation.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from .postflop import rank7, validate_cards
from .range_state import normalize_range, condition


@dataclass(frozen=True)
class Terminal:
    hero_paid: float
    villain_paid: float
    winner: str = 'showdown'


@dataclass(frozen=True)
class Choice:
    actor: str
    children: dict


def river_tree(stack, bets, raises):
    """Hero OOP, equal effective stacks. Amount labels are total street investment."""
    values=(stack,*bets,*raises)
    if any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in values):
        raise ValueError('Valores inválidos.')
    if any(x>stack for x in (*bets,*raises)): raise ValueError('Sizing acima do stack.')
    if len(set(bets))!=len(bets) or len(set(raises))!=len(raises): raise ValueError('Sizing repetido.')
    def label(action,amount): return f'{action}:{amount:g}'
    def facing_bet(bet, bettor):
        responder='villain' if bettor=='hero' else 'hero'
        children={'fold':Terminal(bet if bettor=='hero' else 0,bet if bettor=='villain' else 0,bettor),
                  'call':Terminal(bet,bet)}
        for raise_to in raises:
            # Short all-in raises legal but do not reopen betting; tree disallows reraises anyway.
            if raise_to<=bet or (raise_to<2*bet and raise_to!=stack): continue
            if bettor=='hero':
                replies={'fold':Terminal(bet,raise_to,'villain'),'call':Terminal(raise_to,raise_to)}
            else:
                replies={'fold':Terminal(raise_to,bet,'hero'),'call':Terminal(raise_to,raise_to)}
            children[label('raise',raise_to)]=Choice(bettor,replies)
        return Choice(responder,children)
    after_check={'check':Terminal(0,0)}
    for bet in bets: after_check[label('bet',bet)]=facing_bet(bet,'villain')
    root={'check':Choice('villain',after_check)}
    for bet in bets: root[label('bet',bet)]=facing_bet(bet,'hero')
    return Choice('hero',root)


def solve_river(hero, board, weights, pot, stack, bets, raises, opponent, model_id):
    if len(hero)!=2 or len(board)!=5: raise ValueError('Árvore disponível apenas no river.')
    validate_cards(tuple(hero)+tuple(board))
    if type(pot) not in (int,float) or not math.isfinite(pot) or pot<=0 or not model_id:
        raise ValueError('Pote e identificação do modelo obrigatórios.')
    weights=normalize_range(weights,tuple(hero)+tuple(board))
    tree=river_tree(stack,bets,raises)
    h=rank7(tuple(hero)+tuple(board))
    scores={c:float(h>rank7(tuple(c)+tuple(board)))+.5*(h==rank7(tuple(c)+tuple(board))) for c in weights}
    decisions=[];responses=[]
    def evaluate(node, belief, history):
        if isinstance(node,Terminal):
            if node.winner=='hero': return pot+node.villain_paid
            if node.winner=='villain': return -node.hero_paid
            return sum(w*scores[c] for c,w in belief.items())*(pot+node.hero_paid+node.villain_paid)-node.hero_paid
        if node.actor=='hero':
            alternatives={a:evaluate(child,belief,history+(a,)) for a,child in node.children.items()}
            chosen=max(alternatives,key=alternatives.get)
            decisions.append(dict(history=list(history),range=[[*c,w] for c,w in belief.items()],
                                  alternatives=alternatives,chosen=chosen))
            return alternatives[chosen]
        # Model sees only villain cards and public actions, never actual Hero cards.
        rows={c:opponent(c,tuple(board),history,tuple(node.children)) for c in belief}
        for row in rows.values():
            if set(row)!=set(node.children) or any(type(p) not in (int,float) or not math.isfinite(p)
                    or not 0<=p<=1 for p in row.values()) or abs(sum(row.values())-1)>1e-9:
                raise ValueError('Distribuição de resposta inválida ou incompleta.')
        responses.append(dict(history=list(history),rows=[dict(combo=list(c),probabilities=p) for c,p in rows.items()]))
        value=0.
        for action,child in node.children.items():
            likelihood={c:r[action] for c,r in rows.items()}
            probability=sum(belief[c]*p for c,p in likelihood.items())
            if not probability: continue
            posterior,_=condition(belief,likelihood)
            value+=probability*evaluate(child,posterior,history+(action,))
        return value
    value=evaluate(tree,weights,())
    inputs=dict(hero=list(hero),board=list(board),range=[[*c,w] for c,w in weights.items()],
                pot=pot,stack=stack,bets=list(bets),raises=list(raises),model_id=model_id)
    trace=dict(inputs=inputs,responses=responses)
    digest=hashlib.sha256(json.dumps(trace,sort_keys=True).encode()).hexdigest()
    return dict(status='experimental',laboratory_only=True,method='exact_river_best_response',
                ev=value,chosen=decisions[-1]['chosen'],decisions=decisions,trace=trace,sha256=digest,
                limits=['fixed_opponent_model_not_GTO','heads_up_chip_ev_no_rake',
                        'one_raise_no_reraise','hero_out_of_position','river_only'])


def plan_rivers(hero, turn, weights, pot, stack, bets, raises, opponent, model_id):
    """Exact chance lookahead after turn betting closes, with river best responses.

    Does not choose a turn action. All branches share the same prior information;
    posterior includes card-removal likelihood, not knowledge of villain's cards.
    """
    from .postflop import DECK
    if len(hero)!=2 or len(turn)!=4: raise ValueError('Necessário estado de turn.')
    validate_cards(tuple(hero)+tuple(turn))
    weights=normalize_range(weights,tuple(hero)+tuple(turn))
    branches=[]
    for card in DECK:
        if card in tuple(hero)+tuple(turn): continue
        # With two hidden villain cards, 44 equally likely river cards per combo.
        likelihood={c:float(card not in c)/44 for c in weights}
        probability=sum(weights[c]*p for c,p in likelihood.items())
        if not probability: continue
        posterior,_=condition(weights,likelihood)
        solution=solve_river(hero,list(turn)+[card],posterior,pot,stack,bets,raises,opponent,model_id)
        branches.append(dict(card=card,probability=probability,solution=solution))
    return dict(status='experimental',laboratory_only=True,method='exact_turn_to_river_chance',
                ev_check_to_river=sum(b['probability']*b['solution']['ev'] for b in branches),
                probability_sum=sum(b['probability'] for b in branches),branches=branches,
                limits=['turn_betting_already_closed','not_a_turn_action_recommendation',
                        'fixed_opponent_model_not_GTO','river_tree_limits_apply'])
