"""Explicit synthetic engineering models. Not trained strategy or NVT postflop."""
from functools import lru_cache
from .hand_rank import rank_hand


@lru_cache(maxsize=50000)
def category(combo,board): return rank_hand(tuple(combo)+tuple(board))[0]


def size_sensitive_model(aggression=.5):
    if not 0<=aggression<=1: raise ValueError('Agressividade inválida.')
    def model(combo,board,history,legal,context):
        strength=(.05,.3,.55,.7,.8,.9,.95,.99,1.)[category(combo,board)]
        attacks=[a for a in legal if a.startswith(('bet:','raise:'))]
        attack=min(.8,aggression*(.15+.6*strength)) if attacks else 0.
        row={a:0. for a in legal}
        if 'check' in legal: row['check']=1-attack
        else:
            last=history[-1].split(':')
            amount=float(last[-1]) if len(last)==3 else 0.
            # Deliberately explicit hypothesis: greater price induces more folds of weaker hands.
            fold=min(1-attack,(1-strength)*(.25+amount/(context['pot']+amount)))
            row['fold']=fold;row['call']=1-attack-fold
        for action in attacks: row[action]=attack/len(attacks)
        return row
    return model
